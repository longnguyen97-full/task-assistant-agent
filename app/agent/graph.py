"""
ReAct Agent Core Runner & Workflow Controller (Single-Agent Architecture).
Implements the Reasoning + Acting loop (Thought -> Action -> Observation) using LangGraph StateGraph.
Includes real-time performance telemetry (Latency, Token Usage, Cost Estimation) and Heuristic Fallback.
"""
import json
import time
from typing import Dict, Any, List, Optional, Literal

from langchain_core.messages import SystemMessage, HumanMessage, AIMessage, ToolMessage
from langgraph.graph import StateGraph, START, END

try:
    from langchain_ollama import ChatOllama
except ImportError:
    ChatOllama = None

try:
    from langchain_google_genai import ChatGoogleGenerativeAI
except ImportError:
    ChatGoogleGenerativeAI = None

from app.config import settings
from app.agent.state import AgentState
from app.agent.prompts import REACT_SYSTEM_PROMPT, OLLAMA_SYSTEM_PROMPT
from app.agent.tools import ALL_TOOLS, TOOLS_REGISTRY
from app.agent.guardrails import check_site_scope
from app.agent.fallback import heuristic_fallback_agent, synthesize_tool_summary
from app.agent.telemetry import extract_token_usage, calculate_cost, format_telemetry_badge
from app.database import (
    db_add_chat_message,
    db_get_chat_history,
)

_agent_cancellation_requested = False

def request_agent_cancellation():
    global _agent_cancellation_requested
    _agent_cancellation_requested = True

def reset_agent_cancellation():
    global _agent_cancellation_requested
    _agent_cancellation_requested = False

def is_agent_cancelled() -> bool:
    global _agent_cancellation_requested
    return _agent_cancellation_requested

def _extract_text(content) -> str:
    """Helper to convert str or list of blocks from LangChain to clean markdown string."""
    if not content:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, dict) and "text" in item:
                parts.append(item["text"])
            elif isinstance(item, str):
                parts.append(item)
        return "\n".join(parts)
    return str(content)

def get_configured_llm():
    """Tạo instance LLM tương ứng theo cấu hình hệ thống (Ollama Qwen hoặc Google Gemini)."""
    provider = getattr(settings, "LLM_PROVIDER", "ollama").lower()

    if provider == "ollama" and ChatOllama is not None:
        try:
            return ChatOllama(
                model=getattr(settings, "OLLAMA_MODEL", "qwen2.5:7b"),
                base_url=getattr(settings, "OLLAMA_BASE_URL", "http://localhost:11434"),
                temperature=0.2,
                num_ctx=8192,
            ), getattr(settings, "OLLAMA_MODEL", "qwen2.5:7b"), "ollama"
        except Exception as e:
            print(f"⚠️ Không thể khởi tạo ChatOllama: {e}")

    if provider == "gemini" and settings.GEMINI_API_KEY and ChatGoogleGenerativeAI is not None:
        try:
            return ChatGoogleGenerativeAI(
                model=settings.GEMINI_MODEL,
                google_api_key=settings.GEMINI_API_KEY,
                temperature=0.2,
            ), settings.GEMINI_MODEL, "gemini"
        except Exception as e:
            print(f"[WARN] ChatGoogleGenerativeAI init warning: {e}")

    # Fallback to Ollama if available
    if ChatOllama is not None:
        try:
            return ChatOllama(
                model=getattr(settings, "OLLAMA_MODEL", "qwen2.5:7b"),
                base_url=getattr(settings, "OLLAMA_BASE_URL", "http://localhost:11434"),
                temperature=0.2,
                num_ctx=8192,
            ), getattr(settings, "OLLAMA_MODEL", "qwen2.5:7b"), "ollama"
        except Exception:
            pass

    return None, None, "none"


# ============================================================================
# LANGGRAPH NODES
# ============================================================================

def guardrail_node(state: AgentState) -> Dict[str, Any]:
    """Kiểm tra Site Scope Guardrail: Từ chối nếu nằm ngoài phạm vi các site quản lý."""
    user_message = state["user_message"]
    scope_check = check_site_scope(user_message)
    
    if not scope_check["allowed"]:
        refusal = scope_check.get("refusal_message", "Yêu cầu nằm ngoài phạm vi các site/dự án đang quản lý.")
        return {
            "out_of_scope": True,
            "refusal_message": refusal,
            "final_content": refusal,
            "model_name": "site-scope-guardrail",
            "registered_sites": scope_check.get("registered_sites", []),
        }

    # Nạp System Prompt và Context Memory
    provider = getattr(settings, "LLM_PROVIDER", "ollama").lower()
    base_prompt = OLLAMA_SYSTEM_PROMPT if provider == "ollama" else REACT_SYSTEM_PROMPT

    reg_sites = scope_check.get("registered_sites", [])
    sites_summary = ", ".join(reg_sites)
    dynamic_system_prompt = base_prompt + f"\n\n### 🌐 DANH SÁCH SITE ĐANG QUẢN LÝ:\n{sites_summary}\n"
    if scope_check.get("matched_site"):
        dynamic_system_prompt += f"-> Site đã xác định cho yêu cầu này: **{scope_check['matched_site']}**\n"

    # Context Engineering: nạp short-term memory từ SQLite
    hist_limit = 4 if provider == "ollama" else 8
    history = db_get_chat_history(limit=hist_limit)
    messages = [SystemMessage(content=dynamic_system_prompt)]

    for h in history[:-1]:
        h_text = h["content"]
        if provider == "ollama" and len(h_text) > 300:
            h_text = h_text[:300] + "..."
        if h["role"] == "user":
            messages.append(HumanMessage(content=h_text))
        elif h["role"] == "assistant":
            messages.append(AIMessage(content=h_text))

    messages.append(HumanMessage(content=f"Developer ({state['author']}): {user_message}"))

    return {
        "out_of_scope": False,
        "registered_sites": reg_sites,
        "matched_site": scope_check.get("matched_site"),
        "messages": messages,
        "provider": provider
    }


def reasoning_node(state: AgentState) -> Dict[str, Any]:
    """ReAct Reasoning Step: Gọi LLM (với bind_tools) để sinh ra Thought hoặc Tool Calls."""
    if is_agent_cancelled():
        return {
            "cancelled": True,
            "final_content": "*(Đã dừng luồng suy nghĩ theo yêu cầu)*"
        }

    llm, model_name, provider = get_configured_llm()
    if llm is None:
        return {"fallback_triggered": True}

    llm_with_tools = llm.bind_tools(ALL_TOOLS)
    messages = state["messages"]
    metrics = dict(state.get("metrics", {}))

    t_llm_start = time.perf_counter()
    try:
        ai_response = llm_with_tools.invoke(messages)
    except Exception as e:
        print(f"[WARN] ReAct Agent LLM Error: {e}, falling back to Heuristic Engine.")
        return {"fallback_triggered": True}
        
    llm_duration = (time.perf_counter() - t_llm_start) * 1000.0

    # Token & Cost Telemetry tracking
    tok_usage = extract_token_usage(ai_response)
    metrics["input_tokens"] = metrics.get("input_tokens", 0) + tok_usage["input_tokens"]
    metrics["output_tokens"] = metrics.get("output_tokens", 0) + tok_usage["output_tokens"]
    metrics["total_tokens"] = metrics.get("total_tokens", 0) + tok_usage["total_tokens"]
    metrics["llm_latency_ms"] = round(metrics.get("llm_latency_ms", 0.0) + llm_duration, 2)
    metrics["model"] = model_name
    metrics["provider"] = provider

    updates: Dict[str, Any] = {
        "messages": [ai_response],
        "model_name": model_name,
        "metrics": metrics
    }

    if not ai_response.tool_calls:
        # LLM đã có câu trả lời trực tiếp mà không cần gọi thêm tool
        updates["final_content"] = _extract_text(ai_response.content)

    return updates


def tools_node(state: AgentState) -> Dict[str, Any]:
    """Thực thi danh sách Tool Calls từ LLM, lưu kết quả và ghi nhận độ trễ từng tool."""
    if is_agent_cancelled():
        return {"cancelled": True, "final_content": "*(Đã dừng luồng suy nghĩ theo yêu cầu)*"}

    last_message = state["messages"][-1]
    if not hasattr(last_message, "tool_calls") or not last_message.tool_calls:
        return {}

    executed = list(state.get("executed_tool_calls", []))
    tool_messages = []
    metrics = dict(state.get("metrics", {}))
    tool_exec_latency = 0.0

    for tc in last_message.tool_calls:
        if is_agent_cancelled():
            return {"cancelled": True, "final_content": "*(Đã dừng luồng suy nghĩ theo yêu cầu)*"}

        tool_name = tc["name"]
        tool_args = tc.get("args", {})
        call_id = tc.get("id", f"call_{len(executed)}")

        t_tool_start = time.perf_counter()
        if tool_name in TOOLS_REGISTRY:
            tool_func = TOOLS_REGISTRY[tool_name]
            try:
                tool_result = tool_func.invoke(tool_args)
            except Exception as e:
                tool_result = json.dumps({"error": str(e)}, ensure_ascii=False)
        else:
            tool_result = json.dumps({"error": f"Tool '{tool_name}' không tồn tại"}, ensure_ascii=False)
        
        tool_exec_latency += (time.perf_counter() - t_tool_start) * 1000.0

        executed.append({
            "name": tool_name,
            "args": tool_args,
            "result": tool_result
        })

        tool_messages.append(ToolMessage(
            content=str(tool_result),
            tool_call_id=call_id
        ))

    metrics["tool_latency_ms"] = round(metrics.get("tool_latency_ms", 0.0) + tool_exec_latency, 2)
    turn_count = state.get("turn_count", 0) + 1

    return {
        "executed_tool_calls": executed,
        "messages": tool_messages,
        "turn_count": turn_count,
        "metrics": metrics
    }


def synthesizer_node(state: AgentState) -> Dict[str, Any]:
    """Tổng hợp câu trả lời cuối cùng cho người dùng nếu LLM chưa kịp sinh final text."""
    final_text = state.get("final_content", "")
    if final_text and final_text.strip():
        return {}

    executed = state.get("executed_tool_calls", [])
    if executed:
        summary = synthesize_tool_summary(executed, state["user_message"])
    else:
        summary = "Tôi đã ghi nhận thông tin và cập nhật hệ thống."

    return {"final_content": summary}


def fallback_node(state: AgentState) -> Dict[str, Any]:
    """Bộ điều khiển dự phòng (Rule-based Intent Engine) khi LLM lỗi hoặc chưa bật."""
    metrics = state.get("metrics", {})
    start_time = metrics.get("_start_time")
    fallback_res = heuristic_fallback_agent(
        user_message=state["user_message"],
        author=state["author"],
        start_time=start_time
    )
    return {
        "final_content": fallback_res["content"],
        "executed_tool_calls": fallback_res.get("tool_calls", []),
        "model_name": fallback_res.get("model", "rule-based-fallback"),
        "fallback_triggered": True,
        "metrics": fallback_res.get("metrics", {})
    }


# ============================================================================
# CONDITIONAL ROUTING EDGES
# ============================================================================

def route_guardrail(state: AgentState) -> Literal["reasoning", "__end__"]:
    """Nếu bị chặn ngoài phạm vi -> END ngay; ngược lại -> reasoning."""
    if state.get("out_of_scope"):
        return END
    return "reasoning"

def route_reasoning(state: AgentState) -> Literal["tools", "synthesizer", "fallback", "__end__"]:
    """Điều hướng từ bước suy luận."""
    if state.get("cancelled"):
        return END
    if state.get("fallback_triggered"):
        return "fallback"
    
    last_msg = state["messages"][-1]
    if hasattr(last_msg, "tool_calls") and last_msg.tool_calls:
        return "tools"
    
    # Không còn tool call nào -> chuyển sang tổng kết
    return "synthesizer"

def route_tools(state: AgentState) -> Literal["reasoning", "synthesizer", "__end__"]:
    """Sau khi chạy tool xong: nếu chưa chạm ngưỡng 4 turn -> tiếp tục ReAct."""
    if state.get("cancelled"):
        return END
    if state.get("turn_count", 0) >= 4:
        return "synthesizer"
    return "reasoning"


# ============================================================================
# WORKFLOW GRAPH COMPILATION
# ============================================================================

def build_react_agent_graph():
    """Khởi tạo và biên dịch đồ thị LangGraph StateGraph cho ReAct Agent."""
    workflow = StateGraph(AgentState)

    workflow.add_node("guardrail", guardrail_node)
    workflow.add_node("reasoning", reasoning_node)
    workflow.add_node("tools", tools_node)
    workflow.add_node("synthesizer", synthesizer_node)
    workflow.add_node("fallback", fallback_node)

    workflow.add_edge(START, "guardrail")
    workflow.add_conditional_edges("guardrail", route_guardrail)
    workflow.add_conditional_edges("reasoning", route_reasoning)
    workflow.add_conditional_edges("tools", route_tools)
    workflow.add_edge("synthesizer", END)
    workflow.add_edge("fallback", END)

    return workflow.compile()

react_agent_graph = build_react_agent_graph()


# ============================================================================
# PUBLIC EXECUTION CONTROLLER
# ============================================================================

def execute_react_agent(user_message: str, author: str = "Developer") -> Dict[str, Any]:
    """Single-Agent ReAct Workflow Controller using LangGraph.
    
    Luồng thực thi qua StateGraph:
    1. Guardrail Node: kiểm tra site scope.
    2. Reasoning Node: LLM Thought -> Tool Selection.
    3. Tools Node: Tool Execution -> Observation.
    4. Synthesizer Node: Tóm tắt phản hồi.
    5. Fallback Node: Kích hoạt khi LLM lỗi hoặc chưa bật.
    6. Đo lường Telemetry: Latency, Token Usage, Cost.
    """
    reset_agent_cancellation()
    db_add_chat_message(role="user", content=user_message)

    start_perf = time.perf_counter()

    initial_state: AgentState = {
        "messages": [],
        "author": author,
        "user_message": user_message,
        "out_of_scope": False,
        "registered_sites": [],
        "matched_site": None,
        "refusal_message": "",
        "executed_tool_calls": [],
        "model_name": "",
        "provider": getattr(settings, "LLM_PROVIDER", "ollama").lower(),
        "final_content": "",
        "fallback_triggered": False,
        "turn_count": 0,
        "cancelled": False,
        "metrics": {
            "_start_time": start_perf,
            "latency_ms": 0.0,
            "llm_latency_ms": 0.0,
            "tool_latency_ms": 0.0,
            "input_tokens": 0,
            "output_tokens": 0,
            "total_tokens": 0,
            "cost_usd": 0.0,
            "provider": getattr(settings, "LLM_PROVIDER", "ollama").lower(),
            "model": "agent"
        }
    }

    try:
        final_state = react_agent_graph.invoke(initial_state)
    except Exception as e:
        print(f"[WARN] LangGraph execution exception: {e}, falling back directly.")
        final_state = fallback_node(initial_state)

    total_latency_ms = round((time.perf_counter() - start_perf) * 1000.0, 2)

    # Finalize Metrics
    metrics = final_state.get("metrics", {})
    metrics["latency_ms"] = total_latency_ms
    metrics.pop("_start_time", None)

    # Cost Calculation
    model_name = final_state.get("model_name") or metrics.get("model", "rule-based-fallback")
    provider = final_state.get("provider") or metrics.get("provider", "ollama")
    in_tok = metrics.get("input_tokens", 0)
    out_tok = metrics.get("output_tokens", 0)
    metrics["cost_usd"] = calculate_cost(
        model_name=model_name,
        input_tokens=in_tok,
        output_tokens=out_tok,
        provider=provider
    )
    metrics["model"] = model_name
    metrics["provider"] = provider

    content = final_state.get("final_content", "")
    tool_calls = final_state.get("executed_tool_calls", [])

    # Lưu lịch sử tin nhắn của Assistant
    db_add_chat_message(
        role="assistant",
        content=content,
        tool_calls=json.dumps(tool_calls, ensure_ascii=False) if tool_calls else ""
    )

    # Ghi nhận Telemetry log vào cơ sở dữ liệu
    try:
        from app.database import db_log_telemetry
        executed_tool_names = [t.get("name") for t in tool_calls]
        db_log_telemetry(
            user_prompt=user_message,
            model_name=model_name,
            provider=provider,
            latency_ms=total_latency_ms,
            llm_latency_ms=metrics.get("llm_latency_ms", 0.0),
            tool_latency_ms=metrics.get("tool_latency_ms", 0.0),
            input_tokens=in_tok,
            output_tokens=out_tok,
            total_tokens=in_tok + out_tok,
            cost_usd=metrics["cost_usd"],
            tool_calls_count=len(tool_calls),
            executed_tools=json.dumps(executed_tool_names, ensure_ascii=False),
            out_of_scope=bool(final_state.get("out_of_scope", False)),
            fallback_triggered=bool(final_state.get("fallback_triggered", False))
        )
    except Exception as e:
        print(f"[WARN] Error logging agent telemetry: {e}")

    response_payload = {
        "role": "assistant",
        "content": content,
        "tool_calls": tool_calls,
        "model": model_name,
        "metrics": metrics
    }

    if final_state.get("out_of_scope"):
        response_payload["out_of_scope"] = True
        response_payload["registered_sites"] = final_state.get("registered_sites", [])

    if final_state.get("cancelled"):
        response_payload["cancelled"] = True

    return response_payload

# Backward compatibility alias
execute_chat = execute_react_agent
