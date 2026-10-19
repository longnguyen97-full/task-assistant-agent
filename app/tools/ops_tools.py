import json
from typing import Dict, Any, Optional
from app.db_ops import db_get_all_projects
from app.tools.task_parser import parse_teams_or_email_message
from app.tools.planning_tools import generate_new_project_plan_and_timeline, record_project_change_request

def tool_ingest_teams_email_task(raw_text: str, source: str = "TEAMS") -> str:
    """Tiếp nhận và bóc tách tự động tin nhắn giao việc từ MS Teams hoặc Email thành Task có cấu trúc."""
    res = parse_teams_or_email_message(raw_text=raw_text, source=source)
    return json.dumps(res, ensure_ascii=False)

def tool_create_new_project_plan(project_name: str, requirements: str, target_deadline: str = "") -> str:
    """Lập Kế hoạch Thực hiện (WBS) và Bảng Timeline cho Dự án Mới để nộp sếp / khách hàng."""
    res = generate_new_project_plan_and_timeline(project_name=project_name, requirements=requirements, target_deadline=target_deadline)
    return json.dumps(res, ensure_ascii=False)

def tool_log_project_change_note(project_name: str, title: str, content: str) -> str:
    """Ghi nhận ý thay đổi trong cuộc họp của dự án đang chạy. Đảm bảo KHÔNG CHỈNH SỬA timeline gốc."""
    res = record_project_change_request(project_name=project_name, title=title, content=content)
    return json.dumps(res, ensure_ascii=False)
