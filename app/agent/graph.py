"""
ReAct Agent Core Runner & Workflow Controller (Single-Agent Architecture).
Implements the Reasoning + Acting loop (Thought -> Action -> Observation) using LangChain / LangGraph.
"""
import json
import re
from typing import Dict, Any, List, Optional
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage, ToolMessage
from langchain_google_genai import ChatGoogleGenerativeAI

from app.config import settings
from app.agent.prompts import REACT_SYSTEM_PROMPT
from app.agent.tools import ALL_TOOLS, TOOLS_REGISTRY
from app.agent.guardrails import check_site_scope
from app.database import (
    db_add_chat_message,
    db_get_chat_history,
    db_create_task,
    db_add_daily_note
)
from app.tools.planning_tools import tool_analyze_project_plan_and_risks
from app.rag.vector_store import query_rag
from app.tools.email_tools import tool_dispatch_email

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

def _synthesize_tool_summary(tool_calls: List[Dict[str, Any]], user_message: str) -> str:
    """Tạo tổng kết Markdown có cấu trúc từ danh sách tool đã gọi."""
    lines = ["Tôi đã xử lý các yêu cầu của bạn theo quy trình ReAct:"]
    for tc in tool_calls:
        name = tc["name"]
        res_str = tc.get("result", "")
        try:
            res_obj = json.loads(res_str) if isinstance(res_str, str) else res_str
        except Exception:
            res_obj = {}

        if name == "create_task":
            t = res_obj.get("task", {})
            lines.append(f"\n📌 **Đã tạo Task:** `#{t.get('id', '?')} {t.get('title', '')}` (Status: `{t.get('status', 'TODO')}`, Priority: `{t.get('priority', 'MEDIUM')}`).")
        elif name == "ingest_task_from_message":
            m = res_obj.get("summary_markdown", "")
            if m:
                lines.append(f"\n{m}")
            else:
                lines.append("\n✅ **Đã bóc tách tin nhắn thành task chuẩn trên Bảng Kanban.**")
        elif name == "plan_wbs":
            p = res_obj.get("project", {})
            cnt = res_obj.get("total_created_tasks", 0)
            lines.append(f"\n🚀 **Đã lập Kế hoạch WBS 4 Pha cho Dự án:** `{p.get('name', '')}`. Tự động sinh `{cnt}` tasks tương ứng theo từng mốc.")
        elif name == "log_change_request":
            lines.append(f"\n📝 **Đã ghi nhận Change Request:** {res_obj.get('message', 'Đã bảo toàn timeline gốc')}.")
        elif name == "delete_project":
            lines.append(f"\n🗑️ **Đã xóa dự án khỏi hệ thống:** {res_obj.get('message', 'Đã xóa dự án thành công')}.")
        elif name == "query_docs":
            matches = res_obj.get("results", [])
            if matches:
                top = matches[0]
                lines.append(f"\n📖 **Tra cứu tài liệu ({top.get('source')}):**\n{top.get('content')[:350]}...")
        elif name == "export_monthly_report":
            lines.append("\n📥 **Báo cáo tháng đã sẵn sàng:** Bấm vào nút **'Xuất Báo Cáo (.xlsx)'** trên thanh công cụ để tải file.")
        elif name == "record_daily_note":
            lines.append("\n📓 **Đã ghi nhận nhật ký làm việc (Daily Note) vào hệ thống.**")
        elif name == "dispatch_email":
            lines.append("\n✉️ **Đã chuyển email báo cáo vào Dispatcher Outbox.**")
        elif name == "evaluate_project_storage_tiers":
            m = res_obj.get("summary_markdown", "")
            if m:
                lines.append(f"\n{m}")
            else:
                lines.append("\n🧠 **Đã đánh giá các dự án và phân tích đề xuất phân vùng Hot/Cold Storage.**")
        elif name == "set_project_storage_tier":
            msg = res_obj.get("message", "Đã cập nhật phân vùng lưu trữ dự án.")
            lines.append(f"\n🏷️ **{msg}**")

    return "\n".join(lines)

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

def execute_react_agent(user_message: str, author: str = "Developer") -> Dict[str, Any]:
    """Single-Agent ReAct Workflow Controller.
    
    Luồng thực thi:
    1. Tiếp nhận message, lưu lịch sử.
    2. Kiểm tra Site Scope Guardrail:
       - Chỉ xử lý khi xác định được site thuộc hệ thống hoặc liên quan trực tiếp.
       - Nếu không dính líu gì đến site đang quản lý -> Từ chối xử lý ngoài phạm vi.
    3. Kiểm tra Gemini API Key:
       - Có API Key: Chạy vòng lặp ReAct lặp tuần tự (Thought -> Tool Calling -> Observation).
       - Không có API Key hoặc lỗi quota: Tự động chuyển đổi sang Heuristic Rule-based Engine.
    4. Lưu phản hồi và trả về payload có cấu trúc.
    """
    reset_agent_cancellation()
    db_add_chat_message(role="user", content=user_message)

    # 1. Site Scope Guardrail Check
    scope_check = check_site_scope(user_message)
    if not scope_check["allowed"]:
        refusal_content = scope_check.get("refusal_message", "Yêu cầu nằm ngoài phạm vi các site/dự án đang quản lý.")
        db_add_chat_message(role="assistant", content=refusal_content)
        return {
            "role": "assistant",
            "content": refusal_content,
            "tool_calls": [],
            "out_of_scope": True,
            "registered_sites": scope_check.get("registered_sites", []),
            "model": "site-scope-guardrail"
        }

    api_key = settings.GEMINI_API_KEY
    executed_tool_calls: List[Dict[str, Any]] = []

    # Dynamic Context: Nạp danh sách site hiện có vào System Prompt
    reg_sites = scope_check.get("registered_sites", [])
    sites_summary = ", ".join(reg_sites)
    dynamic_system_prompt = REACT_SYSTEM_PROMPT + f"\n\n### 🌐 DANH SÁCH SITE ĐANG QUẢN LÝ:\n{sites_summary}\n"
    if scope_check.get("matched_site"):
        dynamic_system_prompt += f"-> Site đã xác định cho yêu cầu này: **{scope_check['matched_site']}**\n"

    if api_key:
        try:
            llm = ChatGoogleGenerativeAI(
                model=settings.GEMINI_MODEL,
                google_api_key=api_key,
                temperature=0.2
            )
            llm_with_tools = llm.bind_tools(ALL_TOOLS)

            # Context Engineering: nạp short-term memory từ SQLite
            history = db_get_chat_history(limit=8)
            messages = [SystemMessage(content=dynamic_system_prompt)]

            for h in history[:-1]:
                if h["role"] == "user":
                    messages.append(HumanMessage(content=h["content"]))
                elif h["role"] == "assistant":
                    messages.append(AIMessage(content=h["content"]))

            messages.append(HumanMessage(content=f"Developer ({author}): {user_message}"))

            final_text = ""
            # ReAct Execution Loop (tối đa 4 vòng lặp Thought -> Action -> Observation)
            for turn in range(4):
                if is_agent_cancelled():
                    return {"role": "assistant", "content": "*(Đã dừng luồng suy nghĩ theo yêu cầu)*", "tool_calls": [], "cancelled": True}

                ai_response = llm_with_tools.invoke(messages)
                messages.append(ai_response)

                if is_agent_cancelled():
                    return {"role": "assistant", "content": "*(Đã dừng luồng suy nghĩ theo yêu cầu)*", "tool_calls": [], "cancelled": True}

                if not ai_response.tool_calls:
                    final_text = _extract_text(ai_response.content)
                    break

                for tc in ai_response.tool_calls:
                    if is_agent_cancelled():
                        return {"role": "assistant", "content": "*(Đã dừng luồng suy nghĩ theo yêu cầu)*", "tool_calls": [], "cancelled": True}

                    tool_name = tc["name"]
                    tool_args = tc["args"]
                    call_id = tc.get("id", f"call_{len(executed_tool_calls)}")

                    if tool_name in TOOLS_REGISTRY:
                        tool_func = TOOLS_REGISTRY[tool_name]
                        try:
                            tool_result = tool_func.invoke(tool_args)
                        except Exception as e:
                            tool_result = json.dumps({"error": str(e)}, ensure_ascii=False)
                    else:
                        tool_result = json.dumps({"error": f"Tool '{tool_name}' không tồn tại"}, ensure_ascii=False)

                    executed_tool_calls.append({
                        "name": tool_name,
                        "args": tool_args,
                        "result": tool_result
                    })

                    messages.append(ToolMessage(
                        content=str(tool_result),
                        tool_call_id=call_id
                    ))

            if not final_text.strip():
                try:
                    messages.append(HumanMessage(content="Dựa vào kết quả các tool đã thực hiện ở trên, hãy tóm tắt kết quả chi tiết cho developer bằng tiếng Việt."))
                    summary_res = llm_with_tools.invoke(messages)
                    final_text = _extract_text(summary_res.content)
                except Exception:
                    pass

            if not final_text.strip():
                if executed_tool_calls:
                    final_text = _synthesize_tool_summary(executed_tool_calls, user_message)
                else:
                    final_text = "Tôi đã ghi nhận thông tin và cập nhật hệ thống."

            db_add_chat_message(
                role="assistant",
                content=final_text,
                tool_calls=json.dumps(executed_tool_calls, ensure_ascii=False)
            )

            return {
                "role": "assistant",
                "content": final_text,
                "tool_calls": executed_tool_calls,
                "model": settings.GEMINI_MODEL
            }

        except Exception as e:
            print(f"⚠️ ReAct Agent Gemini API Warning: {e}, falling back to Heuristic Engine.")

    # Fallback Controller
    fallback_res = _heuristic_fallback_agent(user_message, author)
    db_add_chat_message(
        role="assistant",
        content=fallback_res["content"],
        tool_calls=json.dumps(fallback_res["tool_calls"], ensure_ascii=False)
    )
    return fallback_res

def _heuristic_fallback_agent(user_message: str, author: str) -> Dict[str, Any]:
    """Bộ điều khiển dự phòng (Rule-based Intent Engine) khi chưa có API Key hoặc gặp sự cố mạng."""
    msg_lower = user_message.lower()
    tool_calls: List[Dict[str, Any]] = []
    response_parts: List[str] = []

    # 1. Monthly Report Intent
    if any(w in msg_lower for w in ["xuất báo cáo", "export", "báo cáo hàng tháng", "báo cáo tháng", "tự update file báo cáo", "đem nộp"]):
        response_parts.append(
            "🎯 **Quy trình Báo Cáo Tháng tự động 100%:**\n\n"
            "1. 📝 **Note hằng ngày:** Bất cứ khi nào có task mới, tiến độ hoặc blocker, bạn chỉ cần nhắn với tôi qua khung Chat (hoặc tạo trên Bảng Tasks). Hệ thống tự động ghi nhận vào SQLite.\n"
            "2. 🔄 **Tự động phân nhóm & đồng bộ:** Hệ thống liên tục cập nhật trạng thái các task (`DONE`, `ON GOING`, `NOT STARTED`) theo đúng phân mục Website/Dự án.\n"
            "3. 📥 **Xuất báo cáo 1-click:** Bạn bấm nút **'📥 Xuất Báo Cáo (.xlsx)'** trên Bảng Tasks (hoặc tải tại [đây](/api/tasks/export-monthly-report)) là có ngay file Excel đúng chuẩn mẫu công ty (có sẵn tên Tác giả `NGUYEN HOANG BAO LONG` và dấu tick `X`)!"
        )

    # 2. Teams / Email ingestion & Direct Actionable Task Extraction
    # Handles: "project SVIS Vạn Phúc, deadline ngày 23/10/2026, nội dung: clone từ SIS Vạn Phúc và cắt gọt nội dung"
    elif (
        ("nội dung:" in msg_lower or "nội dung :" in msg_lower or "clone" in msg_lower)
        and ("deadline" in msg_lower or "hạn chót" in msg_lower or "ngày" in msg_lower or "project" in msg_lower)
        and not any(w in msg_lower for w in ["họp dự án mới", "lập kế hoạch wbs", "kế hoạch 4 pha", "wbs nộp sếp", "timeline tổng thể"])
    ) or (any(kw in msg_lower for kw in ["kig", "sis", "svis", "kik", "pegasus", "obv"]) and any(w in msg_lower for w in ["clone", "giao", "lỗi", "sửa", "task", "yêu cầu", "cắt gọt", "nội dung"])):
        # Extract site/project
        detected_project = ""
        p_match = re.search(r"(?:project|dự án|hệ thống)\s+([^,\.\n:]+)", user_message, re.IGNORECASE)
        if p_match:
            detected_project = p_match.group(1).strip()
        else:
            for kw, sname in [("svis", "SVIS Vạn Phúc"), ("sis", "SIS Website"), ("kig", "KIG Website"), ("kik", "KIK Website"), ("pegasus", "Pegasus Website"), ("obv", "OBV Website")]:
                if kw in msg_lower:
                    detected_project = sname
                    break
        if not detected_project:
            detected_project = "Website Dự Án"

        # Extract deadline
        deadline_str = ""
        dl_match = re.search(r"(\d{1,2})[/-](\d{1,2})(?:[/-](\d{4}))?", user_message)
        if dl_match:
            try:
                from datetime import datetime
                d = int(dl_match.group(1))
                m = int(dl_match.group(2))
                y = int(dl_match.group(3)) if dl_match.group(3) else datetime.now().year
                deadline_str = f"{y:04d}-{m:02d}-{d:02d}"
            except Exception:
                pass

        # Extract specific content
        content_candidate = ""
        c_match = re.search(r"(?:nội dung|yêu cầu)\s*:\s*([^,\.\n]+.*)", user_message, re.IGNORECASE)
        if c_match:
            content_candidate = c_match.group(1).strip()
        elif "clone" in msg_lower:
            cl_match = re.search(r"(clone\s+[^,\.\n]+(?:và\s+[^,\.\n]+)?)", user_message, re.IGNORECASE)
            content_candidate = cl_match.group(1).strip() if cl_match else "Clone website và cập nhật nội dung"
        else:
            content_candidate = user_message.strip()

        # Format title cleanly
        title = f"[{detected_project}] {content_candidate[0].upper() + content_candidate[1:] if content_candidate else 'Công việc mới'}"
        if len(title) > 90:
            title = title[:87] + "..."

        t = db_create_task(
            title=title,
            description=user_message,
            status="TODO",
            priority="HIGH" if ("gấp" in msg_lower or "khẩn" in msg_lower) else "MEDIUM",
            assignee=author,
            deadline=deadline_str,
            tags=f"clone, content, {detected_project.lower().replace(' ', '-')}",
            source_type="MANUAL",
            website_name=detected_project
        )
        db_add_daily_note(content=f"Ghi nhận công việc: {title} (Deadline: {deadline_str or 'Linh hoạt'})", author=author)

        tool_calls.append({
            "name": "create_task",
            "args": {"title": title, "deadline": deadline_str, "website_name": detected_project},
            "result": json.dumps({"status": "success", "task": t}, ensure_ascii=False)
        })

        response_parts.append(
            f"✅ **Đã tiếp nhận và tạo công việc trên Bảng Tasks (Kanban):**\n\n"
            f"- 📌 **Tên Task:** `{title}` (Task #{t['id']})\n"
            f"- 🌐 **Dự án / Website:** `{detected_project}`\n"
            f"- ⏰ **Hạn chót:** {f'`{deadline_str}`' if deadline_str else 'Trong tuần / Linh hoạt'}\n"
            f"- ⚡ **Độ ưu tiên:** `MEDIUM`\n"
            f"- 📋 **Trạng thái:** `TODO`\n\n"
            f"*(Hệ thống đã nhận diện đây là công việc trực tiếp và đưa thẳng lên Kanban để bạn theo dõi, không tạo các pha rườm rà).*"
        )


    # 3. Project Deletion
    elif any(w in msg_lower for w in ["xóa dự án", "xoá dự án", "delete project"]):
        p_match = re.search(r"(?:xóa dự án|xoá dự án|delete project)\s+([^,\.\n]+)", user_message, re.IGNORECASE)
        p_target = p_match.group(1).strip() if p_match else ""
        from app.database import db_delete_project_by_name, db_delete_project
        if p_target.isdigit():
            del_ok = db_delete_project(int(p_target))
        else:
            del_ok = db_delete_project_by_name(p_target)
        if del_ok:
            tool_calls.append({"name": "delete_project", "args": {"project_name_or_id": p_target}, "result": json.dumps({"status": "success"})})
            response_parts.append(f"🗑️ **Đã xóa dự án `{p_target}` thành công khỏi hệ thống!** Toàn bộ Change Requests liên quan đã được dọn dẹp.")
        else:
            response_parts.append(f"⚠️ **Không tìm thấy dự án `{p_target}`** trong cơ sở dữ liệu để xóa.")

    # 4. New Project Planning (WBS 4-phase)
    elif any(w in msg_lower for w in ["dự án mới", "kế hoạch dự án", "lập timeline", "wbs", "kế hoạch thực hiện"]):
        match = re.search(r"(?:dự án mới|kế hoạch dự án|dự án)\s+([^,\.\n]+)", user_message, re.IGNORECASE)
        p_name = match.group(1).strip() if match else "Dự Án Mới"
        from app.tools.planning_tools import generate_new_project_plan_and_timeline
        p_res = generate_new_project_plan_and_timeline(project_name=p_name, requirements=user_message)
        tool_calls.append({"name": "plan_wbs", "args": {"project_name": p_name}, "result": json.dumps(p_res, ensure_ascii=False)})
        response_parts.append(f"🚀 **Đã phân rã Kế hoạch 4 giai đoạn (WBS) cho dự án `{p_name}`!**\nCác task của 4 giai đoạn đã được đưa lên Bảng Tasks.")

    # 5. Scope Change Request (Preserve original timeline)
    elif any(w in msg_lower for w in ["họp thay đổi", "phát sinh", "thêm tính năng", "change request", "sửa specs"]):
        from app.tools.planning_tools import record_project_change_request
        cr_res = record_project_change_request(project_name="Dự Án Đang Chạy", title="Yêu cầu thay đổi từ cuộc họp", content=user_message, author=author)
        tool_calls.append({"name": "log_change_request", "args": {"title": "Thay đổi tính năng"}, "result": json.dumps(cr_res, ensure_ascii=False)})
        response_parts.append("📝 **Đã ghi nhận Change Request vào hệ thống!**\n⚠️ *Lưu ý: Mốc timeline gốc đã được bảo toàn 100% để đối chiếu.*")


    # 5. Daily Progress / Blocker Logging
    else:
        is_logging = any(w in msg_lower for w in ["hôm nay", "đã làm", "đang làm", "xong", "nghẽn", "blocker", "kẹt", "bị lỗi", "note", "task"])
        has_blocker = any(w in msg_lower for w in ["blocker", "nghẽn", "kẹt", "bị tắc", "chờ", "lỗi", "thiếu"])

        if is_logging or len(user_message) > 20:
            db_add_daily_note(content=user_message, author=author, summary=user_message[:100])
            tool_calls.append({"name": "record_daily_note", "args": {"content": user_message}, "result": json.dumps({"status": "recorded"})})

        if "xong" in msg_lower or "hoàn thành" in msg_lower:
            match = re.search(r"(?:làm xong|hoàn thành|xong)\s+([^,\.\n]+)", user_message, re.IGNORECASE)
            title = match.group(1).strip() if match else user_message[:40]
            t = db_create_task(title=title, description=user_message, status="DONE", priority="MEDIUM", assignee=author)
            tool_calls.append({"name": "create_task", "args": {"title": title, "status": "DONE"}, "result": json.dumps(t, ensure_ascii=False)})
            response_parts.append(f"✅ **Đã ghi nhận task hoàn thành:** `{title}` (Status: DONE)")

        elif has_blocker:
            match = re.search(r"(?:nghẽn|blocker|kẹt|chờ)\s+([^,\.\n]+)", user_message, re.IGNORECASE)
            reason = match.group(0).strip() if match else "Gặp trở ngại kỹ thuật cần giải quyết"
            title = f"Xử lý vấn đề: {reason[:40]}"
            t = db_create_task(title=title, description=user_message, status="BLOCKED", priority="HIGH", blocker_reason=reason, assignee=author)
            tool_calls.append({"name": "create_task", "args": {"title": title, "status": "BLOCKED"}, "result": json.dumps(t, ensure_ascii=False)})
            response_parts.append(f"⚠️ **Đã ghi nhận Blocker:** `{title}` (Status: BLOCKED)\n- **Lý do:** {reason}\n- Đã gắn nhãn ưu tiên HIGH.")

        elif any(w in msg_lower for w in ["nhắc tôi", "nhắc mình", "nhắc", "lên lịch", "cần làm", "tạo task"]):
            clean_title = re.sub(r"^(?:hãy\s+)?(?:nhắc\s+tôi|nhắc\s+mình|nhắc|lên\s+lịch|tạo\s+task|cần\s+làm)\s+", "", user_message, flags=re.IGNORECASE).strip()
            clean_title = clean_title[0].upper() + clean_title[1:] if clean_title else "Công việc mới"
            t = db_create_task(title=clean_title, description=user_message, status="TODO", priority="MEDIUM", assignee=author)
            tool_calls.append({"name": "create_task", "args": {"title": clean_title, "status": "TODO"}, "result": json.dumps(t, ensure_ascii=False)})
            response_parts.append(f"⏰ **Đã thiết lập công việc:** `{clean_title}` (Status: TODO)")

        # Check for RAG specs lookup
        if any(w in msg_lower for w in ["timeline", "tiến độ", "milestone", "specs", "đặc tả", "hạn chót", "deadline"]):
            rag_res = query_rag(user_message, top_k=2)
            tool_calls.append({"name": "query_docs", "args": {"query": user_message}, "result": json.dumps(rag_res, ensure_ascii=False)})
            if rag_res:
                response_parts.append(f"📖 **Tra cứu tài liệu ({rag_res[0].get('source')}):**\n\n{rag_res[0].get('content')[:450]}...")

    if not response_parts:
        response_parts.append("Tôi đã nhận được thông tin từ bạn và ghi nhận vào hệ thống.")

    tip = "\n\n💡 *Gợi ý: Bạn có thể cập nhật `GEMINI_API_KEY` trong mục Cài đặt (⚙️) để kích hoạt toàn bộ khả năng phân tích ngữ nghĩa và suy luận ReAct sâu.*"
    return {
        "role": "assistant",
        "content": "\n\n".join(response_parts) + tip,
        "tool_calls": tool_calls,
        "model": "rule-based-fallback"
    }

# Backward compatibility alias
execute_chat = execute_react_agent
