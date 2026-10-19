"""
State definition for LangGraph ReAct Single-Agent workflow.
"""
from typing import TypedDict, Annotated, List, Dict, Any, Optional
from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages

class AgentState(TypedDict):
    """Trạng thái luồng thực thi đồ thị Agent."""
    messages: Annotated[List[BaseMessage], add_messages]
    author: str
    user_message: str
    out_of_scope: bool
    registered_sites: List[str]
    matched_site: Optional[str]
    refusal_message: str
    executed_tool_calls: List[Dict[str, Any]]
    model_name: str
    provider: str
    final_content: str
    fallback_triggered: bool
    turn_count: int
    cancelled: bool
    metrics: Dict[str, Any]
