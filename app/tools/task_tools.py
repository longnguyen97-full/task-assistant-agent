import json
from typing import Optional, Dict, Any, List
from app.database import (
    db_create_task,
    db_update_task,
    db_get_all_tasks,
    db_get_task_by_id,
    db_add_daily_note
)

def tool_create_task(
    title: str,
    description: str = "",
    status: str = "TODO",
    priority: str = "MEDIUM",
    assignee: str = "Developer",
    deadline: str = "",
    blocker_reason: str = "",
    tags: str = ""
) -> str:
    """Tạo mới một công việc vào cơ sở dữ liệu.
    
    Args:
        title: Tên công việc (ngắn gọn, rõ ràng)
        description: Mô tả chi tiết công việc
        status: Trạng thái (TODO, IN_PROGRESS, BLOCKED, DONE)
        priority: Mức độ ưu tiên (LOW, MEDIUM, HIGH, URGENT)
        assignee: Người phụ trách
        deadline: Hạn hoàn thành (YYYY-MM-DD)
        blocker_reason: Lý do tắc nghẽn nếu status là BLOCKED
        tags: Nhãn phân loại ngăn cách bằng dấu phẩy
    """
    task = db_create_task(
        title=title,
        description=description,
        status=status,
        priority=priority,
        assignee=assignee,
        deadline=deadline,
        blocker_reason=blocker_reason,
        tags=tags
    )
    return json.dumps({
        "message": f"Đã tạo thành công task #{task['id']}: '{task['title']}'",
        "task": task
    }, ensure_ascii=False)

def tool_update_task(
    task_id: int,
    status: Optional[str] = None,
    blocker_reason: Optional[str] = None,
    priority: Optional[str] = None,
    deadline: Optional[str] = None,
    description: Optional[str] = None,
    title: Optional[str] = None
) -> str:
    """Cập nhật trạng thái hoặc thông tin của một task theo ID.
    
    Args:
        task_id: Mã ID của task
        status: Trạng thái mới (TODO, IN_PROGRESS, BLOCKED, DONE)
        blocker_reason: Lý do nếu bị BLOCKED (hoặc để trống nếu đã gỡ blocker)
        priority: Mức độ ưu tiên mới
        deadline: Hạn chót mới
        description: Cập nhật mô tả
        title: Cập nhật tiêu đề
    """
    kwargs = {}
    if status is not None:
        kwargs["status"] = status
    if blocker_reason is not None:
        kwargs["blocker_reason"] = blocker_reason
    if priority is not None:
        kwargs["priority"] = priority
    if deadline is not None:
        kwargs["deadline"] = deadline
    if description is not None:
        kwargs["description"] = description
    if title is not None:
        kwargs["title"] = title

    updated = db_update_task(task_id, **kwargs)
    if not updated:
        return json.dumps({"error": f"Không tìm thấy task với ID #{task_id}"}, ensure_ascii=False)

    return json.dumps({
        "message": f"Đã cập nhật task #{task_id}: status={updated['status']}",
        "task": updated
    }, ensure_ascii=False)

def tool_get_tasks(status: Optional[str] = None, search: Optional[str] = None) -> str:
    """Lấy danh sách các công việc hiện tại trong cơ sở dữ liệu.
    
    Args:
        status: Lọc theo trạng thái ('TODO', 'IN_PROGRESS', 'BLOCKED', 'DONE', hoặc None để lấy tất cả)
        search: Từ khóa tìm kiếm theo tên hoặc tags
    """
    tasks = db_get_all_tasks(status=status, search=search)
    return json.dumps({
        "total": len(tasks),
        "tasks": tasks
    }, ensure_ascii=False)

def tool_record_daily_note(content: str, author: str = "Developer", summary: str = "") -> str:
    """Ghi nhận nhật ký công việc (daily notes) của developer vào cơ sở dữ liệu.
    
    Args:
        content: Nội dung chia sẻ nguyên văn của developer
        author: Tên developer
        summary: Tóm tắt ý chính của ghi chú
    """
    note = db_add_daily_note(content=content, author=author, summary=summary)
    return json.dumps({
        "message": f"Đã ghi nhận nhật ký làm việc của {author} vào lúc {note['created_at']}",
        "note_id": note["id"]
    }, ensure_ascii=False)
