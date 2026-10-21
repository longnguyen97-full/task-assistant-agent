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
from app.tools.design_search_tools import tool_search_design_files_by_image_or_text

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

@tool("analyze_project_plan_and_risks")
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

@tool("import_tasks_from_excel")
def import_tasks_from_excel_tool(file_name_or_path: str) -> str:
    """Đọc file Excel (.xlsx, .xls) hoặc CSV để tự động bóc tách và tạo hàng loạt task vào Kanban."""
    try:
        return tool_import_tasks_from_excel(file_name_or_path=file_name_or_path)
    except Exception as e:
        return json.dumps({"status": "error", "message": str(e)}, ensure_ascii=False)

@tool("delete_project")
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

@tool("evaluate_project_storage_tiers")
def evaluate_project_storage_tiers_tool() -> str:
    """Đánh giá, phân tích hoạt động của các dự án (qua số task đang chạy, độ ưu tiên, hạn chót và trao đổi trong chat) để ĐỀ XUẤT chuyển vùng Hot/Cold Storage.
    QUAN TRỌNG: Tool này CHỈ ĐƯA RA ĐỀ XUẤT và phân tích lý do, TUYỆT ĐỐI KHÔNG tự động chuyển tier của dự án mà không có sự xác nhận của developer."""
    try:
        res = evaluate_project_storage_tiers()
        return json.dumps(res, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"status": "error", "message": str(e)}, ensure_ascii=False)

@tool("set_project_storage_tier")
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

@tool
def search_design_files(folder_path: str, image_path: Optional[str] = None, keywords: Optional[str] = None, max_results: int = 10) -> str:
    """Quét tìm file thiết kế Adobe XD (.xd) trong thư mục chỉ định (hỗ trợ thư mục mạng LAN UNC như \\\\172.16.44.103\\design$ hoặc cục bộ)
    dựa trên hình ảnh chụp màn hình thiết kế (tự động bóc tách đặc trưng bằng AI Vision) hoặc từ khóa do người dùng cung cấp.
    
    Quy tắc an toàn:
    - Tự động kiểm tra Blacklist (chặn các thư mục hệ thống Windows nhạy cảm như C:\\Windows, C:\\Program Files...).
    - Kiểm tra tính truy cập (báo lỗi nếu thư mục không tồn tại, mất kết nối mạng hoặc không có quyền truy cập).
    
    Tham số:
    - folder_path: Đường dẫn thư mục cần quét (ví dụ: '\\\\172.16.44.103\\design$' hoặc 'D:\\Designs').
    - image_path: Đường dẫn file ảnh chụp màn hình nếu người dùng đính kèm hình ảnh.
    - keywords: Từ khóa tìm kiếm nếu người dùng nhập bằng chữ (ngăn cách bằng dấu phẩy).
    - max_results: Số kết quả file tối đa cần lấy."""
    try:
        return tool_search_design_files_by_image_or_text(
            folder_path=folder_path,
            image_path=image_path,
            keywords=keywords,
            max_results=max_results
        )
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
    "search_design_files": search_design_files,
}

ALL_TOOLS = list(TOOLS_REGISTRY.values())

def get_relevant_tools(user_message: str, provider: str = "ollama") -> List[Any]:
    """Dynamic Tool Pruning & Budgeting (Tối ưu hóa Tool Attention cho Single-Agent).
    Lọc và chọn tập 3-5 tools phù hợp nhất với intent của tin nhắn để giải phóng
    tải attention của LLM, đặc biệt giúp mô hình 7B cục bộ (như Ollama Qwen)
    gọi hàm chính xác 100% mà không bị quá tải.
    """
    msg_low = user_message.lower()
    selected_tool_names = set()

    # 1. Quét tìm tệp thiết kế / folder mạng
    if any(k in msg_low for k in ["tìm file", "kiếm file", "quét folder", "scan file", "file xd", ".xd", "hình ảnh", "ảnh", "screenshot"]) or ("\\\\" in user_message or "\\" in user_message):
        selected_tool_names.update(["search_design_files", "create_task", "record_daily_note"])

    # 2. Họp WBS / Lập kế hoạch dự án / Change request
    if any(k in msg_low for k in ["họp dự án", "dự án mới", "kế hoạch", "wbs", "timeline", "thay đổi specs", "change request", "rủi ro", "risk"]):
        selected_tool_names.update(["plan_wbs", "log_change_request", "analyze_project_plan_and_risks", "create_task"])

    # 3. Phân vùng lưu trữ Hot/Cold Storage
    if any(k in msg_low for k in ["hot", "cold", "storage", "advisor", "lưu trữ", "phân vùng", "chuyển vùng"]):
        selected_tool_names.update(["evaluate_project_storage_tiers", "set_project_storage_tier", "get_tasks"])

    # 4. Xuất báo cáo tháng / Excel
    if any(k in msg_low for k in ["báo cáo", "report", "tháng", "export", "excel"]):
        selected_tool_names.update(["export_monthly_report", "record_daily_note", "get_tasks"])

    # 5. Tra cứu specs / tài liệu RAG
    if any(k in msg_low for k in ["specs", "đặc tả", "tài liệu", "hướng dẫn", "quy định", "quy chuẩn", "milestone", "kiến trúc"]):
        selected_tool_names.update(["query_docs", "record_daily_note", "create_task"])

    # 6. Gửi email
    if any(k in msg_low for k in ["gửi mail", "gửi email", "send email", "dispatch mail"]):
        selected_tool_names.update(["dispatch_email", "record_daily_note"])

    # 7. Xóa dự án
    if any(k in msg_low for k in ["xóa dự án", "xoá dự án", "delete project"]):
        selected_tool_names.update(["delete_project", "get_tasks"])

    # 8. Mặc định / Quản lý Task công việc hằng ngày
    if not selected_tool_names or any(k in msg_low for k in ["task", "fix", "clone", "bug", "lỗi", "hoàn thành", "xong", "nghẽn", "blocker"]):
        selected_tool_names.update(["create_task", "update_task", "get_tasks", "ingest_task_from_message", "record_daily_note"])

    # Bổ sung các công cụ nền tảng nếu danh sách quá ngắn
    if len(selected_tool_names) < 3:
        selected_tool_names.add("create_task")
        selected_tool_names.add("record_daily_note")

    result = [TOOLS_REGISTRY[name] for name in selected_tool_names if name in TOOLS_REGISTRY]
    return result


