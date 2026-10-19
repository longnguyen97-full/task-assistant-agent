import os
import sqlite3
import json
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional
from app.config import settings

def get_db_connection() -> sqlite3.Connection:
    """Create and return a database connection with row factory enabled."""
    conn = sqlite3.connect(settings.DB_PATH, timeout=30.0, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    # Enable WAL mode and busy timeout for high concurrency
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA busy_timeout = 30000;")
    return conn

def init_db():
    """Initialize database tables and create initial sample data if empty."""
    settings.ensure_directories()
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.executescript("""
    CREATE TABLE IF NOT EXISTS tasks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT NOT NULL,
        description TEXT DEFAULT '',
        status TEXT NOT NULL CHECK(status IN ('TODO', 'IN_PROGRESS', 'BLOCKED', 'DONE')),
        priority TEXT NOT NULL CHECK(priority IN ('LOW', 'MEDIUM', 'HIGH', 'URGENT')),
        assignee TEXT DEFAULT 'Developer',
        deadline TEXT DEFAULT '',
        blocker_reason TEXT DEFAULT '',
        tags TEXT DEFAULT '',
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS daily_notes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        author TEXT DEFAULT 'Developer',
        content TEXT NOT NULL,
        extracted_summary TEXT DEFAULT '',
        created_at TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS email_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        to_email TEXT NOT NULL,
        subject TEXT NOT NULL,
        body TEXT NOT NULL,
        email_type TEXT NOT NULL,
        status TEXT NOT NULL CHECK(status IN ('SENT', 'SIMULATED', 'FAILED')),
        error_message TEXT DEFAULT '',
        sent_at TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS scheduler_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        job_name TEXT NOT NULL,
        triggered_by TEXT NOT NULL,
        summary TEXT NOT NULL,
        findings TEXT DEFAULT '',
        run_at TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS chat_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        role TEXT NOT NULL CHECK(role IN ('user', 'assistant', 'system')),
        content TEXT NOT NULL,
        tool_calls TEXT DEFAULT '',
        created_at TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS projects (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL UNIQUE,
        status TEXT DEFAULT 'IN_PROGRESS' CHECK(status IN ('PLANNING', 'IN_PROGRESS', 'COMPLETED', 'ON_HOLD')),
        timeline_doc TEXT DEFAULT '',
        plan_summary TEXT DEFAULT '',
        storage_tier TEXT DEFAULT 'HOT' CHECK(storage_tier IN ('HOT', 'COLD')),
        created_at TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS change_notes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        project_id INTEGER,
        project_name TEXT NOT NULL,
        title TEXT NOT NULL,
        content TEXT NOT NULL,
        author TEXT DEFAULT 'Developer',
        created_at TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS documents (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        filename TEXT NOT NULL UNIQUE,
        file_path TEXT NOT NULL,
        scope_type TEXT NOT NULL DEFAULT 'GENERAL',
        project_name TEXT DEFAULT '',
        size_kb REAL DEFAULT 0,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS agent_telemetry (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_prompt TEXT NOT NULL,
        model_name TEXT NOT NULL,
        provider TEXT NOT NULL,
        latency_ms REAL NOT NULL,
        llm_latency_ms REAL DEFAULT 0,
        tool_latency_ms REAL DEFAULT 0,
        input_tokens INTEGER DEFAULT 0,
        output_tokens INTEGER DEFAULT 0,
        total_tokens INTEGER DEFAULT 0,
        cost_usd REAL DEFAULT 0.0,
        tool_calls_count INTEGER DEFAULT 0,
        executed_tools TEXT DEFAULT '[]',
        out_of_scope INTEGER DEFAULT 0,
        fallback_triggered INTEGER DEFAULT 0,
        created_at TEXT NOT NULL
    );
    """)

    # Safe migration for tasks table (source_type & website_name)
    for col, dtype in [("source_type", "TEXT DEFAULT 'MANUAL'"), ("website_name", "TEXT DEFAULT ''")]:
        try:
            cursor.execute(f"ALTER TABLE tasks ADD COLUMN {col} {dtype}")
        except Exception:
            pass

    # Safe migration for projects table (start_date, target_deadline, phases_json, storage_tier)
    for col, dtype in [("start_date", "TEXT DEFAULT ''"), ("target_deadline", "TEXT DEFAULT ''"), ("phases_json", "TEXT DEFAULT '[]'"), ("storage_tier", "TEXT DEFAULT 'HOT'")]:
        try:
            cursor.execute(f"ALTER TABLE projects ADD COLUMN {col} {dtype}")
        except Exception:
            pass

    # Seed default projects if empty
    cursor.execute("SELECT COUNT(*) FROM projects")
    if cursor.fetchone()[0] == 0:
        now_iso = datetime.now().isoformat()
        default_projects = [
            ("SIS / SVIS - Convert Elementor to Hand-Code", "IN_PROGRESS", "Timeline: Tháng 10/2026. Bàn giao cuối tháng.", "Triển khai tối ưu hóa tốc độ tải trang bằng cách chuyển đổi template Elementor qua hand code.", now_iso),
            ("Hệ Thống Agentic AI Giám Sát Website", "PLANNING", "Timeline: R&D hoàn tất trong Sprint 2.", "Nghiên cứu thử nghiệm hệ thống Agentic AI theo dõi, giám sát website ở local.", now_iso)
        ]
        cursor.executemany("""
        INSERT INTO projects (name, status, timeline_doc, plan_summary, created_at)
        VALUES (?, ?, ?, ?, ?)
        """, default_projects)

    # Check if tasks table is empty, if so, seed sample tasks
    cursor.execute("SELECT COUNT(*) FROM tasks")
    count = cursor.fetchone()[0]
    if count == 0:
        now_str = datetime.now().isoformat()
        sample_tasks = [
            (
                "Khởi tạo dự án & kiến trúc FastAPI + UV",
                "Thiết lập cấu trúc thư mục, môi trường ảo với UV và cấu hình Pydantic schemas",
                "DONE",
                "HIGH",
                "Dev Lead",
                "2026-10-14",
                "",
                "setup, architecture, uv",
                now_str,
                now_str
            ),
            (
                "Xây dựng Web Chat UI cho Developer",
                "Phát triển giao diện web chat hiện đại tích hợp Agent, Kanban board và RAG inspector",
                "IN_PROGRESS",
                "HIGH",
                "Dev",
                "2026-10-22",
                "",
                "frontend, chat, ui",
                now_str,
                now_str
            ),
            (
                "Tích hợp OAuth2 Google Login",
                "Xây dựng luồng xác thực đăng nhập Google Workspace cho thành viên dự án",
                "BLOCKED",
                "HIGH",
                "Dev",
                "2026-10-20",
                "Đang chờ Tech Lead cấp Google Client ID & Secret credentials từ Google Cloud Console",
                "auth, oauth2, security",
                now_str,
                now_str
            ),
            (
                "RAG tra cứu Timeline & Specs với ChromaDB",
                "Index các tài liệu markdown và pdf vào vector store để Agent tra cứu tiến độ",
                "IN_PROGRESS",
                "HIGH",
                "Dev",
                "2026-10-24",
                "",
                "rag, chromadb, embeddings",
                now_str,
                now_str
            ),
            (
                "APScheduler Worker nhắc việc 9h sáng",
                "Thiết lập background cronjob quét task quá hạn hoặc bị blocked mỗi sáng",
                "TODO",
                "MEDIUM",
                "Dev",
                "2026-10-28",
                "",
                "cron, scheduler, notification",
                now_str,
                now_str
            ),
            (
                "Tự động gửi Email báo cáo (Email Dispatcher)",
                "Kết nối SMTP server gửi email tổng hợp tiến độ hàng ngày và cảnh báo blocker",
                "TODO",
                "MEDIUM",
                "Dev",
                "2026-10-28",
                "",
                "email, smtp, dispatcher",
                now_str,
                now_str
            )
        ]
        cursor.executemany("""
        INSERT INTO tasks (title, description, status, priority, assignee, deadline, blocker_reason, tags, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, sample_tasks)

    conn.commit()
    conn.close()

    # Sync documents from disk into documents table
    try:
        db_sync_documents_from_disk()
    except Exception as e:
        print(f"Warning: could not sync documents from disk: {e}")

# Database Helper Functions
def db_get_all_tasks(status: Optional[str] = None, search: Optional[str] = None) -> List[Dict[str, Any]]:
    conn = get_db_connection()
    cursor = conn.cursor()
    query = "SELECT * FROM tasks WHERE 1=1"
    params = []
    if status and status.upper() != "ALL":
        query += " AND status = ?"
        params.append(status.upper())
    if search:
        query += " AND (title LIKE ? OR description LIKE ? OR tags LIKE ?)"
        wildcard = f"%{search}%"
        params.extend([wildcard, wildcard, wildcard])
    query += " ORDER BY CASE priority WHEN 'URGENT' THEN 1 WHEN 'HIGH' THEN 2 WHEN 'MEDIUM' THEN 3 ELSE 4 END, id DESC"
    cursor.execute(query, params)
    rows = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return rows

def db_get_task_by_id(task_id: int) -> Optional[Dict[str, Any]]:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM tasks WHERE id = ?", (task_id,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None

def db_create_task(
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
) -> Dict[str, Any]:
    conn = get_db_connection()
    cursor = conn.cursor()
    now_str = datetime.now().isoformat()
    cursor.execute("""
    INSERT INTO tasks (title, description, status, priority, assignee, deadline, blocker_reason, tags, source_type, website_name, created_at, updated_at)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (title, description, status.upper(), priority.upper(), assignee, deadline, blocker_reason, tags, source_type, website_name, now_str, now_str))
    task_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return db_get_task_by_id(task_id)

def db_update_task(task_id: int, **kwargs) -> Optional[Dict[str, Any]]:
    conn = get_db_connection()
    cursor = conn.cursor()
    existing = db_get_task_by_id(task_id)
    if not existing:
        conn.close()
        return None

    fields = []
    values = []
    for k, v in kwargs.items():
        if v is not None and k in ("title", "description", "status", "priority", "assignee", "deadline", "blocker_reason", "tags", "source_type", "website_name"):
            fields.append(f"{k} = ?")
            values.append(v.upper() if k in ("status", "priority") else v)
    
    if fields:
        fields.append("updated_at = ?")
        values.append(datetime.now().isoformat())
        values.append(task_id)
        cursor.execute(f"UPDATE tasks SET {', '.join(fields)} WHERE id = ?", values)
        conn.commit()
    conn.close()
    return db_get_task_by_id(task_id)

def db_delete_task(task_id: int) -> bool:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
    affected = cursor.rowcount
    conn.commit()
    conn.close()
    return affected > 0

def db_delete_all_tasks() -> int:
    """Xóa toàn bộ tasks trong cơ sở dữ liệu và reset auto-increment."""
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM tasks")
        row = cursor.fetchone()
        count = row[0] if row else 0
        cursor.execute("DELETE FROM tasks")
        try:
            cursor.execute("DELETE FROM sqlite_sequence WHERE name = 'tasks'")
        except Exception:
            pass
        conn.commit()
        return count
    finally:
        conn.close()

def db_duplicate_task(task_id: int) -> Optional[Dict[str, Any]]:
    """Nhân bản (duplicate) một task có sẵn trong cơ sở dữ liệu."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM tasks WHERE id = ?", (task_id,))
    row = cursor.fetchone()
    if not row:
        conn.close()
        return None
    original = dict(row)
    now_str = datetime.now().isoformat()
    new_title = f"{original['title']} (Bản sao)"
    cursor.execute("""
    INSERT INTO tasks (title, description, status, priority, assignee, deadline, blocker_reason, tags, source_type, website_name, created_at, updated_at)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        new_title,
        original.get("description", ""),
        original.get("status", "TODO"),
        original.get("priority", "MEDIUM"),
        original.get("assignee", "Developer"),
        original.get("deadline", ""),
        original.get("blocker_reason", ""),
        original.get("tags", ""),
        original.get("source_type", "MANUAL"),
        original.get("website_name", ""),
        now_str,
        now_str
    ))
    new_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return db_get_task_by_id(new_id)



def db_add_daily_note(content: str, author: str = "Developer", summary: str = "") -> Dict[str, Any]:
    conn = get_db_connection()
    cursor = conn.cursor()
    now_str = datetime.now().isoformat()
    cursor.execute("""
    INSERT INTO daily_notes (author, content, extracted_summary, created_at)
    VALUES (?, ?, ?, ?)
    """, (author, content, summary, now_str))
    note_id = cursor.lastrowid
    conn.commit()
    cursor.execute("SELECT * FROM daily_notes WHERE id = ?", (note_id,))
    row = dict(cursor.fetchone())
    conn.close()
    return row

def db_get_daily_notes(limit: int = 30) -> List[Dict[str, Any]]:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM daily_notes ORDER BY id DESC LIMIT ?", (limit,))
    rows = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return rows

def db_log_email(to_email: str, subject: str, body: str, email_type: str, status: str, error_message: str = "") -> int:
    conn = get_db_connection()
    cursor = conn.cursor()
    now_str = datetime.now().isoformat()
    cursor.execute("""
    INSERT INTO email_logs (to_email, subject, body, email_type, status, error_message, sent_at)
    VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (to_email, subject, body, email_type, status, error_message, now_str))
    email_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return email_id

def db_get_email_logs(limit: int = 50) -> List[Dict[str, Any]]:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM email_logs ORDER BY id DESC LIMIT ?", (limit,))
    rows = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return rows

def db_log_scheduler(job_name: str, triggered_by: str, summary: str, findings: str = "") -> int:
    conn = get_db_connection()
    cursor = conn.cursor()
    now_str = datetime.now().isoformat()
    cursor.execute("""
    INSERT INTO scheduler_logs (job_name, triggered_by, summary, findings, run_at)
    VALUES (?, ?, ?, ?, ?)
    """, (job_name, triggered_by, summary, findings, now_str))
    log_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return log_id

def db_get_scheduler_logs(limit: int = 30) -> List[Dict[str, Any]]:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM scheduler_logs ORDER BY id DESC LIMIT ?", (limit,))
    rows = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return rows

def db_add_chat_message(role: str, content: str, tool_calls: str = "") -> int:
    conn = get_db_connection()
    cursor = conn.cursor()
    now_str = datetime.now().isoformat()
    cursor.execute("""
    INSERT INTO chat_history (role, content, tool_calls, created_at)
    VALUES (?, ?, ?, ?)
    """, (role, content, tool_calls, now_str))
    msg_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return msg_id

def db_get_chat_history(limit: int = 40) -> List[Dict[str, Any]]:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM chat_history ORDER BY id ASC LIMIT ?", (limit,))
    rows = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return rows

def db_delete_last_chat_message(role: Optional[str] = None) -> bool:
    """Xóa tin nhắn gần nhất trong chat_history (hỗ trợ hủy bỏ khi dev submit nhầm)."""
    conn = get_db_connection()
    cursor = conn.cursor()
    if role:
        cursor.execute("SELECT id FROM chat_history WHERE role = ? ORDER BY id DESC LIMIT 1", (role,))
    else:
        cursor.execute("SELECT id FROM chat_history ORDER BY id DESC LIMIT 1")
    row = cursor.fetchone()
    if not row:
        conn.close()
        return False
    msg_id = row["id"] if isinstance(row, sqlite3.Row) else row[0]
    cursor.execute("DELETE FROM chat_history WHERE id = ?", (msg_id,))
    conn.commit()
    conn.close()
    return True

# ==========================================
# PROJECTS & SCOPE CHANGE NOTES (PRESERVE ORIGINAL TIMELINE)
# ==========================================
def db_get_all_projects(storage_tier: Optional[str] = None) -> List[Dict[str, Any]]:
    conn = get_db_connection()
    cursor = conn.cursor()
    if storage_tier:
        cursor.execute("SELECT * FROM projects WHERE UPPER(storage_tier) = ? ORDER BY id DESC", (storage_tier.strip().upper(),))
    else:
        cursor.execute("SELECT * FROM projects ORDER BY id DESC")
    rows = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return rows

def db_get_project_by_id(project_id: int) -> Optional[Dict[str, Any]]:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM projects WHERE id = ?", (project_id,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None

def db_get_project_by_name(project_name: str) -> Optional[Dict[str, Any]]:
    clean = project_name.strip()
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM projects WHERE name = ? COLLATE NOCASE", (clean,))
    row = cursor.fetchone()
    if not row:
        cursor.execute("SELECT * FROM projects WHERE name LIKE ? ORDER BY length(name) ASC LIMIT 1", (f"%{clean}%",))
        row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None

def db_create_project(
    name: str,
    timeline_doc: str,
    plan_summary: str = "",
    status: str = "IN_PROGRESS",
    start_date: str = "",
    target_deadline: str = "",
    phases_json: str = "[]",
    storage_tier: str = "HOT"
) -> Dict[str, Any]:
    """Tạo hoặc cập nhật dự án với WBS các giai đoạn, hạn chót và phân vùng lưu trữ."""
    conn = get_db_connection()
    cursor = conn.cursor()
    now_str = datetime.now().isoformat()
    clean_tier = (storage_tier or "HOT").strip().upper()
    if clean_tier not in ("HOT", "COLD"):
        clean_tier = "HOT"

    cursor.execute("SELECT id, storage_tier FROM projects WHERE name = ?", (name,))
    existing = cursor.fetchone()
    if existing:
        p_id = existing["id"] if isinstance(existing, sqlite3.Row) else existing[0]
        # Giữ nguyên storage_tier hiện tại nếu không chỉ định rõ thay đổi
        current_tier = (existing["storage_tier"] if isinstance(existing, sqlite3.Row) else existing[1]) or clean_tier
        target_tier = clean_tier if storage_tier != "HOT" else current_tier
        cursor.execute("""
        UPDATE projects
        SET status = ?, timeline_doc = ?, plan_summary = ?, start_date = ?, target_deadline = ?, phases_json = ?, storage_tier = ?
        WHERE id = ?
        """, (status, timeline_doc, plan_summary, start_date, target_deadline, phases_json, target_tier, p_id))
    else:
        cursor.execute("""
        INSERT INTO projects (name, status, timeline_doc, plan_summary, start_date, target_deadline, phases_json, storage_tier, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (name, status, timeline_doc, plan_summary, start_date, target_deadline, phases_json, clean_tier, now_str))
        p_id = cursor.lastrowid

    conn.commit()
    cursor.execute("SELECT * FROM projects WHERE id = ?", (p_id,))
    row = dict(cursor.fetchone())
    conn.close()
    return row

def db_update_project_storage_tier(project_id: int, storage_tier: str) -> Optional[Dict[str, Any]]:
    """Cập nhật phân vùng lưu trữ cho dự án (HOT hoặc COLD). Dev có thể chuyển tùy ý."""
    tier = (storage_tier or "").strip().upper()
    if tier not in ("HOT", "COLD"):
        raise ValueError(f"Phân vùng không hợp lệ: '{storage_tier}'. Vui lòng chọn 'HOT' hoặc 'COLD'.")
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM projects WHERE id = ?", (project_id,))
    if not cursor.fetchone():
        conn.close()
        return None
    cursor.execute("UPDATE projects SET storage_tier = ? WHERE id = ?", (tier, project_id))
    conn.commit()
    cursor.execute("SELECT * FROM projects WHERE id = ?", (project_id,))
    row = dict(cursor.fetchone())
    conn.close()
    return row

def db_update_project_storage_tier_by_name(project_name: str, storage_tier: str) -> Optional[Dict[str, Any]]:
    """Cập nhật phân vùng lưu trữ theo tên dự án."""
    proj = db_get_project_by_name(project_name)
    if not proj:
        return None
    return db_update_project_storage_tier(proj["id"], storage_tier)

def db_add_change_note(
    project_id: Optional[int],
    project_name: str,
    title: str,
    content: str,
    author: str = "Developer"
) -> Dict[str, Any]:
    """Ghi nhận ý thay đổi trong cuộc họp mà TUYỆT ĐỐI KHÔNG CHỈNH SỬA TIMELINE GỐC."""
    conn = get_db_connection()
    cursor = conn.cursor()
    now_str = datetime.now().isoformat()
    cursor.execute("""
    INSERT INTO change_notes (project_id, project_name, title, content, author, created_at)
    VALUES (?, ?, ?, ?, ?, ?)
    """, (project_id, project_name, title, content, author, now_str))
    note_id = cursor.lastrowid
    conn.commit()
    cursor.execute("SELECT * FROM change_notes WHERE id = ?", (note_id,))
    row = dict(cursor.fetchone())
    conn.close()

    # Tự động tạo task gắn nhãn CHANGE_REQUEST vào Kanban để dev theo dõi
    db_create_task(
        title=f"[Change Request] {project_name}: {title}",
        description=f"Thay đổi phát sinh từ cuộc họp:\n{content}\n(Lưu ý: Giữ nguyên timeline gốc dự án).",
        status="TODO",
        priority="HIGH",
        assignee=author,
        tags=f"change-request, {project_name.lower()}",
        source_type="CHANGE_REQUEST",
        website_name=project_name
    )

    return row

def db_get_change_notes(project_id: Optional[int] = None, limit: int = 50) -> List[Dict[str, Any]]:
    conn = get_db_connection()
    cursor = conn.cursor()
    if project_id:
        cursor.execute("SELECT * FROM change_notes WHERE project_id = ? ORDER BY id DESC LIMIT ?", (project_id, limit))
    else:
        cursor.execute("SELECT * FROM change_notes ORDER BY id DESC LIMIT ?", (limit,))
    rows = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return rows

def db_delete_project(project_id: int, delete_tasks: bool = False) -> bool:
    """Xóa dự án khỏi cơ sở dữ liệu SQLite kèm theo change notes liên quan."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM projects WHERE id = ?", (project_id,))
    row = cursor.fetchone()
    if not row:
        conn.close()
        return False
    p_name = row["name"]
    cursor.execute("DELETE FROM projects WHERE id = ?", (project_id,))
    cursor.execute("DELETE FROM change_notes WHERE project_id = ? OR project_name = ?", (project_id, p_name))
    # Update document references
    cursor.execute("UPDATE documents SET scope_type = 'GENERAL', project_name = '' WHERE project_name = ?", (p_name,))
    if delete_tasks:
        cursor.execute("DELETE FROM tasks WHERE website_name = ? OR (source_type = 'PROJECT_NEW' AND title LIKE ?)", (p_name, f"[{p_name}]%"))
    conn.commit()
    conn.close()
    return True

def db_delete_project_by_name(project_name: str, delete_tasks: bool = False) -> bool:
    """Xóa dự án theo tên."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM projects WHERE name = ? OR name LIKE ?", (project_name, f"%{project_name}%"))
    row = cursor.fetchone()
    if not row:
        conn.close()
        return False
    p_id = row["id"] if isinstance(row, sqlite3.Row) else row[0]
    conn.close()
    return db_delete_project(p_id, delete_tasks=delete_tasks)

# ==========================================
# REGISTERED SITES & SCOPE DISCOVERY
# ==========================================
def db_get_registered_sites() -> List[str]:
    """Lấy danh sách tên tất cả các site / dự án đang được quản lý trong hệ thống."""
    conn = get_db_connection()
    cursor = conn.cursor()
    sites = set()
    try:
        cursor.execute("SELECT name FROM projects")
        for r in cursor.fetchall():
            n = (r["name"] if isinstance(r, sqlite3.Row) else r[0]) or ""
            if n.strip():
                sites.add(n.strip())
        cursor.execute("SELECT DISTINCT website_name FROM tasks WHERE website_name != '' AND website_name IS NOT NULL")
        for r in cursor.fetchall():
            w = (r["website_name"] if isinstance(r, sqlite3.Row) else r[0]) or ""
            if w.strip():
                sites.add(w.strip())
    finally:
        conn.close()
    return sorted(list(sites))

# ==========================================
# DOCUMENT KNOWLEDGE BASE & SCOPE MANAGEMENT (GENERAL vs PROJECT)
# ==========================================
def db_get_all_documents() -> List[Dict[str, Any]]:
    """Lấy danh sách tất cả tài liệu trong cơ sở dữ liệu."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM documents ORDER BY id DESC")
    rows = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return rows

def db_get_document_by_filename(filename: str) -> Optional[Dict[str, Any]]:
    clean_name = os.path.basename(filename.replace("\\", "/"))
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM documents WHERE filename = ? OR filename = ? OR filename LIKE ?", (filename, clean_name, f"%{clean_name}%"))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None

def db_upsert_document(
    filename: str,
    file_path: str,
    scope_type: str = "GENERAL",
    project_name: str = "",
    size_kb: float = 0.0
) -> Dict[str, Any]:
    """Tạo hoặc cập nhật phân loại tài liệu (Kỹ thuật chung hoặc Dự án riêng)."""
    clean_name = os.path.basename(filename.replace("\\", "/"))
    conn = get_db_connection()
    cursor = conn.cursor()
    now_str = datetime.now().isoformat()
    cursor.execute("SELECT id FROM documents WHERE filename = ? OR filename = ?", (filename, clean_name))
    row = cursor.fetchone()
    if row:
        doc_id = row["id"] if isinstance(row, sqlite3.Row) else row[0]
        cursor.execute("""
        UPDATE documents
        SET file_path = ?, scope_type = ?, project_name = ?, size_kb = ?, updated_at = ?
        WHERE id = ?
        """, (file_path, scope_type.upper(), project_name, size_kb, now_str, doc_id))
    else:
        cursor.execute("""
        INSERT INTO documents (filename, file_path, scope_type, project_name, size_kb, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (clean_name, file_path, scope_type.upper(), project_name, size_kb, now_str, now_str))
        doc_id = cursor.lastrowid
    conn.commit()
    cursor.execute("SELECT * FROM documents WHERE id = ?", (doc_id,))
    res = dict(cursor.fetchone())
    conn.close()
    return res

def db_update_document_scope(filename: str, scope_type: str, project_name: str = "") -> Optional[Dict[str, Any]]:
    """Chuyển đổi phạm vi tài liệu: GENERAL (Dự án chung) hoặc PROJECT (Dự án riêng)."""
    clean_name = os.path.basename(filename.replace("\\", "/"))
    conn = get_db_connection()
    cursor = conn.cursor()
    now_str = datetime.now().isoformat()
    cursor.execute("SELECT id FROM documents WHERE filename = ? OR filename = ?", (filename, clean_name))
    row = cursor.fetchone()
    if not row:
        conn.close()
        return None
    doc_id = row["id"] if isinstance(row, sqlite3.Row) else row[0]
    final_scope = scope_type.upper()
    final_project = project_name.strip() if final_scope == "PROJECT" else ""
    cursor.execute("""
    UPDATE documents
    SET scope_type = ?, project_name = ?, updated_at = ?
    WHERE id = ?
    """, (final_scope, final_project, now_str, doc_id))
    conn.commit()
    cursor.execute("SELECT * FROM documents WHERE id = ?", (doc_id,))
    res = dict(cursor.fetchone())
    conn.close()
    return res

def db_delete_document(filename: str) -> bool:
    clean_name = os.path.basename(filename.replace("\\", "/"))
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM documents WHERE filename = ? OR filename = ?", (filename, clean_name))
    affected = cursor.rowcount
    conn.commit()
    conn.close()
    return affected > 0

def db_sync_documents_from_disk():
    """Tự động đồng bộ các file tài liệu trong thư mục data/ vào SQLite documents table."""
    supported_exts = {".md", ".txt", ".pdf", ".xlsx", ".xls", ".csv"}
    search_dirs = [settings.DATA_DIR]
    docs_sub = settings.DATA_DIR / "docs"
    if docs_sub.exists():
        search_dirs.append(docs_sub)

    seen = set()
    for directory in search_dirs:
        if not directory.exists():
            continue
        for item in directory.glob("*"):
            if item.is_file() and item.suffix.lower() in supported_exts:
                if item.name not in seen:
                    seen.add(item.name)
                    existing = db_get_document_by_filename(item.name)
                    if not existing:
                        size_kb = round(item.stat().st_size / 1024, 1)
                        name_lower = item.name.lower()
                        if any(kw in name_lower for kw in ["report", "excel", "template", "kig", "sis", "svis"]):
                            scope = "PROJECT"
                            proj = "SIS / SVIS - Convert Elementor to Hand-Code" if ("sis" in name_lower or "svis" in name_lower) else ""
                        else:
                            scope = "GENERAL"
                            proj = ""
                        db_upsert_document(
                            filename=item.name,
                            file_path=str(item),
                            scope_type=scope,
                            project_name=proj,
                            size_kb=size_kb
                        )

# ==========================================
# AGENT TELEMETRY & OBSERVABILITY TRACES
# ==========================================

def db_log_telemetry(
    user_prompt: str,
    model_name: str,
    provider: str,
    latency_ms: float,
    llm_latency_ms: float = 0.0,
    tool_latency_ms: float = 0.0,
    input_tokens: int = 0,
    output_tokens: int = 0,
    total_tokens: int = 0,
    cost_usd: float = 0.0,
    tool_calls_count: int = 0,
    executed_tools: str = "[]",
    out_of_scope: bool = False,
    fallback_triggered: bool = False
) -> int:
    """Ghi nhận log thực thi một turn của Agent vào SQLite."""
    conn = get_db_connection()
    cursor = conn.cursor()
    now_str = datetime.now().isoformat()
    cursor.execute("""
    INSERT INTO agent_telemetry (
        user_prompt, model_name, provider, latency_ms, llm_latency_ms, tool_latency_ms,
        input_tokens, output_tokens, total_tokens, cost_usd, tool_calls_count,
        executed_tools, out_of_scope, fallback_triggered, created_at
    )
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        user_prompt, model_name, provider, latency_ms, llm_latency_ms, tool_latency_ms,
        input_tokens, output_tokens, total_tokens, cost_usd, tool_calls_count,
        executed_tools, 1 if out_of_scope else 0, 1 if fallback_triggered else 0, now_str
    ))
    row_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return row_id

def db_get_telemetry_stats() -> Dict[str, Any]:
    """Tổng hợp số liệu thống kê Telemetry (KPIs) cho trang Monitoring."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
    SELECT 
        COUNT(*) as total_requests,
        COALESCE(SUM(total_tokens), 0) as total_tokens,
        COALESCE(SUM(input_tokens), 0) as total_input_tokens,
        COALESCE(SUM(output_tokens), 0) as total_output_tokens,
        COALESCE(SUM(cost_usd), 0.0) as total_cost_usd,
        COALESCE(AVG(latency_ms), 0.0) as avg_latency_ms,
        COALESCE(AVG(llm_latency_ms), 0.0) as avg_llm_latency_ms,
        COALESCE(AVG(tool_latency_ms), 0.0) as avg_tool_latency_ms,
        COALESCE(SUM(out_of_scope), 0) as out_of_scope_count,
        COALESCE(SUM(fallback_triggered), 0) as fallback_count
    FROM agent_telemetry
    """)
    stats_row = cursor.fetchone()
    
    # Task stats
    cursor.execute("SELECT status, COUNT(*) as cnt FROM tasks GROUP BY status")
    task_counts = {row["status"]: row["cnt"] for row in cursor.fetchall()}
    
    # Project stats
    cursor.execute("SELECT storage_tier, COUNT(*) as cnt FROM projects GROUP BY storage_tier")
    tier_counts = {row["storage_tier"]: row["cnt"] for row in cursor.fetchall()}

    conn.close()

    total_req = stats_row["total_requests"] or 0
    out_of_scope_cnt = stats_row["out_of_scope_count"] or 0
    guardrail_pass_rate = round(((total_req - out_of_scope_cnt) / total_req * 100), 1) if total_req > 0 else 100.0

    return {
        "total_requests": total_req,
        "total_tokens": stats_row["total_tokens"] or 0,
        "total_input_tokens": stats_row["total_input_tokens"] or 0,
        "total_output_tokens": stats_row["total_output_tokens"] or 0,
        "total_cost_usd": round(stats_row["total_cost_usd"] or 0.0, 6),
        "avg_latency_ms": round(stats_row["avg_latency_ms"] or 0.0, 1),
        "avg_llm_latency_ms": round(stats_row["avg_llm_latency_ms"] or 0.0, 1),
        "avg_tool_latency_ms": round(stats_row["avg_tool_latency_ms"] or 0.0, 1),
        "out_of_scope_count": out_of_scope_cnt,
        "fallback_count": stats_row["fallback_count"] or 0,
        "guardrail_pass_rate": guardrail_pass_rate,
        "tasks_by_status": task_counts,
        "projects_by_tier": tier_counts
    }

def db_get_recent_traces(limit: int = 30) -> List[Dict[str, Any]]:
    """Lấy danh sách các lượt thực thi gần nhất của Agent cho Waterfall Traces."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM agent_telemetry ORDER BY id DESC LIMIT ?", (limit,))
    rows = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return rows



