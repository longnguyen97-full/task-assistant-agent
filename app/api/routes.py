import shutil
from pathlib import Path
from datetime import datetime
from typing import Optional
from fastapi import APIRouter, UploadFile, File, HTTPException, Form, Response
from app.config import settings
from app.reports.monthly_report import generate_monthly_report_excel
from app.models import (
    TaskCreate,
    TaskUpdate,
    TaskStatusChange,
    ChatRequest,
    DailyNoteCreate,
    EmailSendRequest,
    SettingsUpdateRequest,
    RAGQueryRequest,
    QuickIngestRequest,
    NewProjectPlanRequest,
    ChangeNoteCreateRequest,
    DocumentScopeUpdateRequest,
    ProjectStorageTierUpdateRequest
)
from app.database import (
    db_get_all_tasks,
    db_create_task,
    db_update_task,
    db_delete_task,
    db_delete_all_tasks,
    db_duplicate_task,
    db_get_task_by_id,
    db_add_daily_note,
    db_get_daily_notes,
    db_get_email_logs,
    db_get_chat_history,
    db_delete_last_chat_message,
    db_get_all_projects,
    db_get_change_notes,
    db_delete_project,
    db_update_document_scope,
    db_get_registered_sites,
    db_update_project_storage_tier
)
from app.tools.storage_tier_tools import evaluate_project_storage_tiers
from app.tools.task_parser import parse_teams_or_email_message
from app.tools.planning_tools import (
    generate_new_project_plan_and_timeline,
    record_project_change_request,
    tool_analyze_project_plan_and_risks
)
from app.tools.email_tools import tool_dispatch_email
from app.agent.graph import execute_react_agent, execute_chat, request_agent_cancellation
from app.rag.vector_store import (
    get_rag_stats,
    index_documents,
    query_rag,
    add_single_document,
    delete_document_file
)
from app.scheduler.worker import get_scheduler_status, run_morning_scan

api_router = APIRouter(prefix="/api")

# --- 1. CHAT ENDPOINTS ---
@api_router.post("/chat")
async def chat_endpoint(req: ChatRequest):
    if not req.message.strip():
        raise HTTPException(status_code=400, detail="Nội dung tin nhắn không được để trống")
    response = execute_chat(user_message=req.message, author=req.author or "Developer")
    return response

@api_router.post("/chat/cancel")
async def cancel_chat_endpoint():
    request_agent_cancellation()
    deleted = db_delete_last_chat_message(role="user")
    return {"success": True, "message": "Đã ngắt luồng suy nghĩ của Agent và xóa tin nhắn gửi nhầm", "deleted_user_msg": deleted}

@api_router.get("/chat/history")
async def get_chat_history_endpoint(limit: int = 50):
    return db_get_chat_history(limit=limit)

# --- 2. TASKS ENDPOINTS ---
@api_router.get("/tasks")
async def get_tasks_endpoint(status: Optional[str] = None, search: Optional[str] = None):
    tasks = db_get_all_tasks(status=status, search=search)
    return {"tasks": tasks, "total": len(tasks)}

@api_router.post("/tasks")
async def create_task_endpoint(task: TaskCreate):
    created = db_create_task(
        title=task.title,
        description=task.description or "",
        status=task.status or "TODO",
        priority=task.priority or "MEDIUM",
        assignee=task.assignee or "Developer",
        deadline=task.deadline or "",
        blocker_reason=task.blocker_reason or "",
        tags=task.tags or ""
    )
    return created

@api_router.put("/tasks/{task_id}")
async def update_task_endpoint(task_id: int, task: TaskUpdate):
    updated = db_update_task(
        task_id=task_id,
        title=task.title,
        description=task.description,
        status=task.status,
        priority=task.priority,
        assignee=task.assignee,
        deadline=task.deadline,
        blocker_reason=task.blocker_reason,
        tags=task.tags
    )
    if not updated:
        raise HTTPException(status_code=404, detail="Không tìm thấy task")
    return updated

@api_router.post("/tasks/status")
async def change_task_status_endpoint(req: TaskStatusChange):
    updated = db_update_task(task_id=req.task_id, status=req.status)
    if not updated:
        raise HTTPException(status_code=404, detail="Không tìm thấy task")
    return updated

@api_router.delete("/tasks/clear-all")
async def clear_all_tasks_endpoint():
    count = db_delete_all_tasks()
    return {"success": True, "deleted_count": count, "message": f"Đã xóa toàn bộ {count} tasks thành công."}

@api_router.delete("/tasks/{task_id}")
async def delete_task_endpoint(task_id: int):
    success = db_delete_task(task_id)
    if not success:
        raise HTTPException(status_code=404, detail="Không tìm thấy task")
    return {"success": True, "message": f"Đã xóa task #{task_id}"}

@api_router.post("/tasks/{task_id}/duplicate")
async def duplicate_task_endpoint(task_id: int):
    duplicated = db_duplicate_task(task_id)
    if not duplicated:
        raise HTTPException(status_code=404, detail="Không tìm thấy task để nhân bản")
    return duplicated

@api_router.get("/tasks/export-monthly-report")
async def export_monthly_report_endpoint(
    author: Optional[str] = "NGUYEN HOANG BAO LONG",
    title: Optional[str] = "Web Developer"
):
    try:
        excel_bytes = generate_monthly_report_excel(author_name=author, author_title=title)
        filename = f"Monthly_Report_{datetime.now().strftime('%m_%Y')}.xlsx"
        return Response(
            content=excel_bytes,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'}
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lỗi khi xuất file báo cáo: {str(e)}")

# --- 3. DAILY NOTES ENDPOINTS ---
@api_router.get("/notes")
async def get_notes_endpoint(limit: int = 30):
    notes = db_get_daily_notes(limit=limit)
    return {"notes": notes}

@api_router.post("/notes")
async def create_note_endpoint(note: DailyNoteCreate):
    created = db_add_daily_note(content=note.content, author=note.author or "Developer")
    return created

# --- 4. RAG & DOCUMENTS ENDPOINTS ---
@api_router.get("/docs")
async def get_docs_endpoint():
    return get_rag_stats()

@api_router.post("/docs/upload")
async def upload_document_endpoint(
    file: UploadFile = File(...),
    scope_type: str = Form("GENERAL"),
    project_name: Optional[str] = Form("")
):
    allowed_exts = {".md", ".txt", ".pdf", ".xlsx", ".xls", ".csv"}
    file_ext = Path(file.filename).suffix.lower()
    if file_ext not in allowed_exts:
        raise HTTPException(status_code=400, detail="Chỉ hỗ trợ file định dạng .md, .txt, .pdf, .xlsx hoặc .csv")

    docs_dir = settings.DATA_DIR / "docs"
    docs_dir.mkdir(parents=True, exist_ok=True)
    destination = docs_dir / file.filename

    with open(destination, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    # Index into ChromaDB with scope and project metadata
    res = add_single_document(
        destination,
        scope_type=scope_type or "GENERAL",
        project_name=project_name or ""
    )

    # If Excel / CSV, automatically parse and import tasks into Kanban
    if file_ext in (".xlsx", ".xls", ".csv"):
        try:
            import json
            from app.tools.excel_tools import tool_import_tasks_from_excel
            excel_res = json.loads(tool_import_tasks_from_excel(str(destination)))
            res["excel_import"] = excel_res
            if excel_res.get("status") == "success":
                count = excel_res.get("total_created_tasks", 0)
                res["message"] = f"Đã index tài liệu và tự động tạo {count} tasks từ file Excel vào Bảng Tasks!"
        except Exception as e:
            res["excel_import_error"] = str(e)

    return res

@api_router.put("/docs/scope")
async def update_doc_scope_endpoint(req: DocumentScopeUpdateRequest):
    res = db_update_document_scope(
        filename=req.filename,
        scope_type=req.scope_type,
        project_name=req.project_name or ""
    )
    if not res:
        raise HTTPException(status_code=404, detail=f"Không tìm thấy tài liệu '{req.filename}' trong hệ thống")
    # Reindex ChromaDB to refresh metadata in vector store
    try:
        index_documents(force_reindex=True)
    except Exception as e:
        print(f"Warning: could not reindex after scope update: {e}")
    return {
        "success": True,
        "message": f"Đã chuyển tài liệu '{req.filename}' sang phạm vi '{res['scope_type']}'" + (f" ({res['project_name']})" if res.get('project_name') else "") + "!",
        "document": res
    }

@api_router.post("/docs/reindex")
async def reindex_docs_endpoint():
    res = index_documents(force_reindex=True)
    return res

@api_router.delete("/docs/{filename:path}")
async def delete_document_endpoint(filename: str):
    success = delete_document_file(filename)
    if not success:
        raise HTTPException(status_code=404, detail=f"Không tìm thấy file tài liệu: {filename}")
    return {"success": True, "message": f"Đã xóa tài liệu '{filename}' và cập nhật chỉ mục RAG thành công!"}

@api_router.post("/docs/query")
async def query_rag_endpoint(req: RAGQueryRequest):
    results = query_rag(req.query, top_k=req.top_k or 4)
    return {"query": req.query, "results": results}

@api_router.get("/sites")
async def get_registered_sites_endpoint():
    sites = db_get_registered_sites()
    return {"sites": sites, "total": len(sites)}


# --- 5. PLANNING & RISKS ENDPOINT ---
@api_router.get("/planning/analyze")
async def analyze_planning_endpoint():
    analysis_json = tool_analyze_project_plan_and_risks()
    import json
    return json.loads(analysis_json)

# --- 6. EMAIL DISPATCHER ENDPOINTS ---
@api_router.get("/emails")
async def get_emails_endpoint(limit: int = 50):
    return {"emails": db_get_email_logs(limit=limit)}

@api_router.post("/emails/send")
async def send_email_endpoint(req: EmailSendRequest):
    res_str = tool_dispatch_email(
        to_email=req.to_email,
        subject=req.subject,
        body=req.body,
        email_type=req.email_type or "manual"
    )
    import json
    return json.loads(res_str)

# --- 7. SCHEDULER ENDPOINTS ---
@api_router.get("/scheduler/status")
async def scheduler_status_endpoint():
    return get_scheduler_status()

@api_router.post("/scheduler/trigger")
async def trigger_scheduler_scan_endpoint():
    result = run_morning_scan(triggered_by="MANUAL")
    return result

# --- 8. SETTINGS ENDPOINTS ---
@api_router.get("/settings")
async def get_settings_endpoint():
    # Return masked secret keys
    api_key_masked = ""
    if settings.GEMINI_API_KEY:
        if len(settings.GEMINI_API_KEY) > 8:
            api_key_masked = settings.GEMINI_API_KEY[:4] + "..." + settings.GEMINI_API_KEY[-4:]
        else:
            api_key_masked = "****"

    smtp_pass_masked = "****" if settings.SMTP_PASSWORD else ""

    return {
        "gemini_api_key_set": bool(settings.GEMINI_API_KEY),
        "gemini_api_key_masked": api_key_masked,
        "gemini_model": settings.GEMINI_MODEL,
        "smtp_host": settings.SMTP_HOST,
        "smtp_port": settings.SMTP_PORT,
        "smtp_user": settings.SMTP_USER,
        "smtp_from": settings.SMTP_FROM,
        "smtp_tls": settings.SMTP_TLS,
        "smtp_password_set": bool(settings.SMTP_PASSWORD),
        "smtp_password_masked": smtp_pass_masked,
        "dev_email": settings.DEV_EMAIL,
        "reminder_hour": settings.REMINDER_HOUR,
        "reminder_minute": settings.REMINDER_MINUTE
    }

@api_router.post("/settings")
async def update_settings_endpoint(req: SettingsUpdateRequest):
    if req.gemini_api_key is not None and req.gemini_api_key != "":
        settings.update_setting("GEMINI_API_KEY", req.gemini_api_key.strip())
    if req.gemini_model:
        settings.update_setting("GEMINI_MODEL", req.gemini_model)
    if req.smtp_host is not None:
        settings.update_setting("SMTP_HOST", req.smtp_host)
    if req.smtp_port is not None:
        settings.update_setting("SMTP_PORT", str(req.smtp_port))
    if req.smtp_user is not None:
        settings.update_setting("SMTP_USER", req.smtp_user)
    if req.smtp_password is not None and req.smtp_password != "":
        settings.update_setting("SMTP_PASSWORD", req.smtp_password)
    if req.smtp_from is not None:
        settings.update_setting("SMTP_FROM", req.smtp_from)
    if req.smtp_tls is not None:
        settings.update_setting("SMTP_TLS", "true" if req.smtp_tls else "false")
    if req.dev_email is not None:
        settings.update_setting("DEV_EMAIL", req.dev_email)

    return {"success": True, "message": "Đã lưu cài đặt thành công!"}

# --- 9. QUICK INGEST (TEAMS & EMAIL) ENDPOINTS ---
@api_router.post("/ingest/teams-email")
async def ingest_teams_email_endpoint(req: QuickIngestRequest):
    result = parse_teams_or_email_message(
        raw_text=req.raw_text,
        source=req.source or "TEAMS",
        author=req.author or "Developer"
    )
    return result

# --- 11. PROJECTS & SCOPE CHANGE NOTES ENDPOINTS ---
@api_router.get("/projects")
async def get_projects_endpoint(tier: Optional[str] = None):
    projects = db_get_all_projects(storage_tier=tier)
    hot_count = sum(1 for p in projects if (p.get("storage_tier") or "HOT").upper() == "HOT")
    cold_count = sum(1 for p in projects if (p.get("storage_tier") or "HOT").upper() == "COLD")
    return {
        "projects": projects,
        "total": len(projects),
        "hot_count": hot_count,
        "cold_count": cold_count
    }

@api_router.put("/projects/{project_id}/storage-tier")
async def update_project_storage_tier_endpoint(project_id: int, req: ProjectStorageTierUpdateRequest):
    tier = req.storage_tier.strip().upper()
    if tier not in ("HOT", "COLD"):
        raise HTTPException(status_code=400, detail="Vùng lưu trữ không hợp lệ. Phải là 'HOT' hoặc 'COLD'.")
    try:
        updated = db_update_project_storage_tier(project_id, tier)
        if not updated:
            raise HTTPException(status_code=404, detail=f"Không tìm thấy dự án #{project_id}")
        tier_label = "🔥 Hot Storage" if tier == "HOT" else "❄️ Cold Storage"
        return {
            "success": True,
            "message": f"Đã chuyển dự án '{updated['name']}' sang phân vùng {tier_label}!",
            "project": updated
        }
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))

@api_router.get("/projects/tier-analysis")
async def get_projects_tier_analysis_endpoint():
    """AI Storage Advisor phân tích các dự án và đề xuất chuyển vùng Hot/Cold."""
    return evaluate_project_storage_tiers()

@api_router.post("/projects/new-plan")
async def create_new_project_plan_endpoint(req: NewProjectPlanRequest):
    result = generate_new_project_plan_and_timeline(
        project_name=req.project_name,
        requirements=req.requirements,
        target_deadline=req.target_deadline or "",
        storage_tier=req.storage_tier or "HOT"
    )
    return result

@api_router.get("/projects/change-notes")
async def get_change_notes_endpoint(project_id: Optional[int] = None):
    notes = db_get_change_notes(project_id=project_id)
    return {"change_notes": notes, "total": len(notes)}

@api_router.post("/projects/change-notes")
async def add_change_note_endpoint(req: ChangeNoteCreateRequest):
    result = record_project_change_request(
        project_name=req.project_name,
        title=req.title,
        content=req.content,
        author=req.author or "Developer"
    )
    return result

@api_router.delete("/projects/{project_id}")
async def delete_project_endpoint(project_id: int, delete_tasks: bool = False):
    success = db_delete_project(project_id, delete_tasks=delete_tasks)
    if not success:
        raise HTTPException(status_code=404, detail="Không tìm thấy dự án")
    return {"success": True, "message": f"Đã xóa dự án #{project_id} thành công!"}


