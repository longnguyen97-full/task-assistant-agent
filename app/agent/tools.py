"""
Agent Tools Module - Standardized LangChain Tool definitions.
Production-ready Single-Agent tools for Task Extraction, WBS Planning, RAG Retrieval, and Report Generation.
"""
import json
from typing import Optional, Dict, Any, List
from langchain_core.tools import tool

from app.database import (
    db_get_all_tasks,
    db_get_task_by_id,
    db_create_task,
    db_update_task,
    db_add_daily_note,
    db_get_daily_notes,
    db_delete_project,
    db_delete_project_by_name
)
from app.rag.vector_store import query_rag
from app.tools.planning_tools import (
    tool_analyze_project_plan_and_risks,
    generate_new_project_plan_and_timeline,
    record_project_change_request
)
from app.tools.task_parser import parse_teams_or_email_message
from app.tools.email_tools import tool_dispatch_email
from app.tools.excel_tools import tool_import_tasks_from_excel
from app.tools.storage_tier_tools import evaluate_project_storage_tiers, tool_set_project_storage_tier

# -------------------------------------------------------------
# 1. TASK EXTRACTOR & STATE MANAGEMENT TOOLS
# -------------------------------------------------------------
@tool
def create_task(
    title: str,
    description: str = "",
    status: str = "TODO",
    priority: str = "MEDIUM",
    assignee: str = "Developer",
    deadline: str = "",
    blocker_reason: str = "",
    tags: str = "",
    source_type: str = "MANUAL",
    website_name: str = ""
) -> str:
    """Tạo mới một công việc (task) vào cơ sở dữ liệu SQLite và đưa lên bảng Kanban.
    DÙNG CHO: Mọi công việc cụ thể, giao việc, clone website sang site mới, sửa lỗi, cắt gọt nội dung, tối ưu web (kể cả khi dev nhắn dạng 'project X, deadline Y, nội dung: Z')."""
    try:
        t = db_create_task(
            title=title,
            description=description,
            status=status,
            priority=priority,
            assignee=assignee,
            deadline=deadline,
            blocker_reason=blocker_reason,
            tags=tags,
            source_type=source_type,
            website_name=website_name
        )
        return json.dumps({
            "status": "success",
            "message": f"Đã tạo task #{t['id']}: {title}",
            "task": t
        }, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"status": "error", "message": str(e)}, ensure_ascii=False)

@tool
def update_task(
    task_id: int,
    status: Optional[str] = None,
    blocker_reason: Optional[str] = None,
    priority: Optional[str] = None,
    deadline: Optional[str] = None,
    description: Optional[str] = None,
    title: Optional[str] = None
) -> str:
    """Cập nhật thông tin hoặc trạng thái (TODO, IN_PROGRESS, BLOCKED, DONE) của một task theo ID."""
    try:
        t = db_update_task(
            task_id=task_id,
            status=status,
            blocker_reason=blocker_reason,
            priority=priority,
            deadline=deadline,
            description=description,
            title=title
        )
        if not t:
            return json.dumps({"status": "error", "message": f"Không tìm thấy task #{task_id}"}, ensure_ascii=False)
        return json.dumps({
            "status": "success",
            "message": f"Đã cập nhật task #{task_id}",
            "task": t
        }, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"status": "error", "message": str(e)}, ensure_ascii=False)

@tool
def get_tasks(status: Optional[str] = None, search: Optional[str] = None) -> str:
    """Tra cứu danh sách các task hiện có từ SQLite để kiểm tra trạng thái hoặc ID."""
    try:
        tasks = db_get_all_tasks(status=status, search=search)
        return json.dumps({
            "status": "success",
            "total": len(tasks),
            "tasks": tasks[:20]
        }, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"status": "error", "message": str(e)}, ensure_ascii=False)

@tool
def ingest_task_from_message(raw_text: str, source: str = "TEAMS") -> str:
    """Tiếp nhận và bóc tách tự động tin nhắn giao việc từ MS Teams hoặc Email thành Task Kanban có cấu trúc."""
    try:
        res = parse_teams_or_email_message(raw_text=raw_text, source=source)
        return json.dumps(res, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"status": "error", "message": str(e)}, ensure_ascii=False)

# -------------------------------------------------------------
# 2. WBS PLANNER & CHANGE TRACKER TOOLS
# -------------------------------------------------------------
@tool
def plan_wbs(project_name: str, requirements: str, target_deadline: str = "") -> str:
    """Lập Kế hoạch Thực hiện (WBS) và Bảng Timeline cho Dự án Mới để nộp sếp/khách hàng.
    CHỈ DÙNG KHI: Dev yêu cầu rõ ràng việc lập kế hoạch/timeline dự án tổng thể (ví dụ: 'họp dự án mới', 'lập kế hoạch WBS'). KHÔNG DÙNG cho các công việc cụ thể (như clone web, sửa lỗi, cắt gọt nội dung) - đối với công việc cụ thể hãy dùng `create_task`."""
    try:
        res = generate_new_project_plan_and_timeline(
            project_name=project_name,
            requirements=requirements,
            target_deadline=target_deadline
        )
        return json.dumps(res, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"status": "error", "message": str(e)}, ensure_ascii=False)

@tool
def log_change_request(project_name: str, title: str, content: str, author: str = "Developer") -> str:
    """Ghi nhận ý thay đổi trong cuộc họp của dự án đang chạy. TUYỆT ĐỐI KHÔNG SỬA TIMELINE GỐC mà ghi nhận thành Change Request riêng."""
    try:
        res = record_project_change_request(
            project_name=project_name,
            title=title,
            content=content,
            author=author
        )
        return json.dumps(res, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"status": "error", "message": str(e)}, ensure_ascii=False)

@tool
def analyze_project_plan_and_risks_tool() -> str:
    """Đối chiếu tiến độ thực tế với kế hoạch từ RAG, tính toán nguy cơ trễ hạn (deadline risks) và đánh giá các blocker."""
    try:
        return tool_analyze_project_plan_and_risks()
    except Exception as e:
        return json.dumps({"status": "error", "message": str(e)}, ensure_ascii=False)

# -------------------------------------------------------------
# 3. RAG RETRIEVER & KNOWLEDGE TOOLS
# -------------------------------------------------------------
@tool
def query_docs(query: str, top_k: int = 4) -> str:
    """Tra cứu kho tài liệu kỹ thuật dự án (.md, .pdf, specs, guidelines) qua ChromaDB Semantic Search."""
    try:
        results = query_rag(query=query, top_k=top_k)
        return json.dumps({
            "status": "success",
            "query": query,
            "results": results
        }, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"status": "error", "message": str(e)}, ensure_ascii=False)

# -------------------------------------------------------------
# 4. REPORT ENGINE & UTILITY TOOLS
# -------------------------------------------------------------
@tool
def export_monthly_report(author: str = "NGUYEN HOANG BAO LONG") -> str:
    """Kích hoạt và cung cấp thông tin xuất báo cáo tháng (.xlsx) chuẩn doanh nghiệp với 1 click."""
    try:
        tasks = db_get_all_tasks()
        done_cnt = sum(1 for t in tasks if t.get("status") == "DONE")
        active_cnt = sum(1 for t in tasks if t.get("status") in ("TODO", "IN_PROGRESS", "BLOCKED"))
        return json.dumps({
            "status": "ready",
            "download_url": "/api/tasks/export-monthly-report",
            "author": author,
            "total_tasks_synced": len(tasks),
            "done_tasks": done_cnt,
            "active_tasks": active_cnt,
            "message": "Báo cáo Excel đã sẵn sàng tải về với đầy đủ phân mục và đánh dấu X trạng thái."
        }, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"status": "error", "message": str(e)}, ensure_ascii=False)

@tool
def record_daily_note(content: str, author: str = "Developer", summary: str = "") -> str:
    """Ghi nhận nhật ký làm việc (daily notes) của developer vào SQLite Database."""
    try:
        n = db_add_daily_note(content=content, author=author, summary=summary)
        return json.dumps({
            "status": "success",
            "message": "Đã ghi nhận nhật ký làm việc",
            "note": n
        }, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"status": "error", "message": str(e)}, ensure_ascii=False)

@tool
def dispatch_email(to_email: str, subject: str, body: str, email_type: str = "daily_report") -> str:
    """Gửi email báo cáo tiến độ hoặc cảnh báo blocker qua SMTP hoặc Outbox mô phỏng."""
    try:
        return tool_dispatch_email(to_email=to_email, subject=subject, body=body, email_type=email_type)
    except Exception as e:
        return json.dumps({"status": "error", "message": str(e)}, ensure_ascii=False)

@tool
def import_tasks_from_excel_tool(file_name_or_path: str) -> str:
    """Đọc file Excel (.xlsx, .xls) hoặc CSV để tự động bóc tách và tạo hàng loạt task vào Kanban."""
    try:
        return tool_import_tasks_from_excel(file_name_or_path=file_name_or_path)
    except Exception as e:
        return json.dumps({"status": "error", "message": str(e)}, ensure_ascii=False)

@tool
def delete_project_tool(project_name_or_id: str, delete_tasks: bool = False) -> str:
    """Xóa một dự án khỏi hệ thống.
    Tham số:
    - project_name_or_id: Tên dự án hoặc ID dự án cần xóa.
    - delete_tasks: True nếu muốn xóa toàn bộ tasks thuộc dự án, False nếu giữ lại tasks."""
    try:
        if str(project_name_or_id).isdigit():
            success = db_delete_project(int(project_name_or_id), delete_tasks=delete_tasks)
        else:
            success = db_delete_project_by_name(project_name_or_id, delete_tasks=delete_tasks)
        if success:
            return json.dumps({
                "status": "success",
                "message": f"Đã xóa thành công dự án '{project_name_or_id}' khỏi hệ thống."
            }, ensure_ascii=False)
        else:
            return json.dumps({
                "status": "error",
                "message": f"Không tìm thấy dự án '{project_name_or_id}' để xóa."
            }, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"status": "error", "message": str(e)}, ensure_ascii=False)

@tool
def evaluate_project_storage_tiers_tool() -> str:
    """Đánh giá, phân tích hoạt động của các dự án (qua số task đang chạy, độ ưu tiên, hạn chót và trao đổi trong chat) để ĐỀ XUẤT chuyển vùng Hot/Cold Storage.
    QUAN TRỌNG: Tool này CHỈ ĐƯA RA ĐỀ XUẤT và phân tích lý do, TUYỆT ĐỐI KHÔNG tự động chuyển tier của dự án mà không có sự xác nhận của developer."""
    try:
        res = evaluate_project_storage_tiers()
        return json.dumps(res, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"status": "error", "message": str(e)}, ensure_ascii=False)

@tool
def set_project_storage_tier_tool(project_name_or_id: str, storage_tier: str) -> str:
    """Chuyển đổi phân vùng lưu trữ cho một dự án sang HOT hoặc COLD.
    CHỈ GỌI KHI: Developer có yêu cầu hoặc xác nhận rõ ràng (ví dụ: 'chuyển dự án X sang Cold', 'đồng ý đưa Y lên Hot').
    Tham số:
    - project_name_or_id: Tên dự án hoặc ID dự án cần chuyển.
    - storage_tier: 'HOT' hoặc 'COLD'."""
    try:
        res = tool_set_project_storage_tier(project_name_or_id=project_name_or_id, storage_tier=storage_tier)
        return json.dumps(res, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"status": "error", "message": str(e)}, ensure_ascii=False)

# Tool Registry for ReAct Agent
TOOLS_REGISTRY = {
    "create_task": create_task,
    "update_task": update_task,
    "get_tasks": get_tasks,
    "ingest_task_from_message": ingest_task_from_message,
    "plan_wbs": plan_wbs,
    "log_change_request": log_change_request,
    "delete_project": delete_project_tool,
    "analyze_project_plan_and_risks": analyze_project_plan_and_risks_tool,
    "evaluate_project_storage_tiers": evaluate_project_storage_tiers_tool,
    "set_project_storage_tier": set_project_storage_tier_tool,
    "query_docs": query_docs,
    "export_monthly_report": export_monthly_report,
    "record_daily_note": record_daily_note,
    "dispatch_email": dispatch_email,
    "import_tasks_from_excel": import_tasks_from_excel_tool,
}

ALL_TOOLS = list(TOOLS_REGISTRY.values())

