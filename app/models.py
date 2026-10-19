from pydantic import BaseModel, Field
from typing import Optional, List, Any

class TaskCreate(BaseModel):
    title: str = Field(..., description="Tên công việc")
    description: Optional[str] = Field("", description="Chi tiết công việc")
    status: Optional[str] = Field("TODO", description="Trạng thái: TODO, IN_PROGRESS, BLOCKED, DONE")
    priority: Optional[str] = Field("MEDIUM", description="Mức độ ưu tiên: LOW, MEDIUM, HIGH, URGENT")
    assignee: Optional[str] = Field("Developer", description="Người phụ trách")
    deadline: Optional[str] = Field("", description="Hạn chót YYYY-MM-DD")
    blocker_reason: Optional[str] = Field("", description="Lý do nghẽn nếu status là BLOCKED")
    tags: Optional[str] = Field("", description="Tags ngăn cách bằng dấu phẩy")
    source_type: Optional[str] = Field("MANUAL", description="ROUTINE_CHECK, ROUTINE_BACKUP, TEAMS_EMAIL, PROJECT_NEW, CHANGE_REQUEST, MANUAL")
    website_name: Optional[str] = Field("", description="Tên website liên quan nếu có")

class TaskUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = None
    priority: Optional[str] = None
    assignee: Optional[str] = None
    deadline: Optional[str] = None
    blocker_reason: Optional[str] = None
    tags: Optional[str] = None
    source_type: Optional[str] = None
    website_name: Optional[str] = None

class TaskStatusChange(BaseModel):
    task_id: int
    status: str

class ChatRequest(BaseModel):
    message: str = Field(..., description="Tin nhắn từ developer")
    author: Optional[str] = Field("Developer", description="Tên dev gửi tin")

class DailyNoteCreate(BaseModel):
    content: str
    author: Optional[str] = "Developer"

class EmailSendRequest(BaseModel):
    to_email: str
    subject: str
    body: str
    email_type: Optional[str] = "manual"

class SettingsUpdateRequest(BaseModel):
    gemini_api_key: Optional[str] = None
    gemini_model: Optional[str] = None
    smtp_host: Optional[str] = None
    smtp_port: Optional[int] = None
    smtp_user: Optional[str] = None
    smtp_password: Optional[str] = None
    smtp_from: Optional[str] = None
    smtp_tls: Optional[bool] = None
    dev_email: Optional[str] = None

class RAGQueryRequest(BaseModel):
    query: str
    top_k: Optional[int] = 4
    category: Optional[str] = None  # 'COMMON' hoặc tên website riêng

# Models specific to user's core workflow pillars
class QuickIngestRequest(BaseModel):

    raw_text: str = Field(..., description="Nội dung paste từ MS Teams hoặc Email")
    source: Optional[str] = Field("TEAMS", description="TEAMS hoặc EMAIL")
    author: Optional[str] = "Developer"

class NewProjectPlanRequest(BaseModel):
    project_name: str = Field(..., description="Tên dự án mới")
    requirements: str = Field(..., description="Nội dung yêu cầu hoặc note cuộc họp")
    target_deadline: Optional[str] = Field("", description="Hạn bàn giao mong muốn")
    storage_tier: Optional[str] = Field("HOT", description="Phân vùng lưu trữ: HOT hoặc COLD")

class ChangeNoteCreateRequest(BaseModel):
    project_id: Optional[int] = None
    project_name: str = Field(..., description="Tên dự án đang chạy")
    title: str = Field(..., description="Tóm tắt nội dung thay đổi")
    content: str = Field(..., description="Chi tiết các ý thay đổi theo cuộc họp")
    author: Optional[str] = "Developer"

class DocumentScopeUpdateRequest(BaseModel):
    filename: str = Field(..., description="Tên file tài liệu cần chuyển phạm vi")
    scope_type: str = Field("GENERAL", description="Phạm vi: GENERAL (Kỹ thuật chung) hoặc PROJECT (Dự án riêng)")
    project_name: Optional[str] = Field("", description="Tên dự án nếu scope_type là PROJECT")

class ProjectStorageTierUpdateRequest(BaseModel):
    storage_tier: str = Field(..., description="HOT hoặc COLD")


