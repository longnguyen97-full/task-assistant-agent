import sqlite3
import json
from datetime import datetime
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
    """)

    # Safe migration for tasks table (source_type & website_name)
    for col, dtype in [("source_type", "TEXT DEFAULT 'MANUAL'"), ("website_name", "TEXT DEFAULT ''")]:
        try:
            cursor.execute(f"ALTER TABLE tasks ADD COLUMN {col} {dtype}")
        except Exception:
            pass

    # Safe migration for projects table (start_date, target_deadline, phases_json)
    for col, dtype in [("start_date", "TEXT DEFAULT ''"), ("target_deadline", "TEXT DEFAULT ''"), ("phases_json", "TEXT DEFAULT '[]'")]:
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

# ==========================================
# PROJECTS & SCOPE CHANGE NOTES (PRESERVE ORIGINAL TIMELINE)
# ==========================================
def db_get_all_projects() -> List[Dict[str, Any]]:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM projects ORDER BY id DESC")
    rows = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return rows

def db_create_project(
    name: str,
    timeline_doc: str,
    plan_summary: str = "",
    status: str = "IN_PROGRESS",
    start_date: str = "",
    target_deadline: str = "",
    phases_json: str = "[]"
) -> Dict[str, Any]:
    """Tạo hoặc cập nhật dự án với WBS các giai đoạn và hạn chót."""
    conn = get_db_connection()
    cursor = conn.cursor()
    now_str = datetime.now().isoformat()

    cursor.execute("SELECT id FROM projects WHERE name = ?", (name,))
    existing = cursor.fetchone()
    if existing:
        p_id = existing["id"] if isinstance(existing, sqlite3.Row) else existing[0]
        cursor.execute("""
        UPDATE projects
        SET status = ?, timeline_doc = ?, plan_summary = ?, start_date = ?, target_deadline = ?, phases_json = ?
        WHERE id = ?
        """, (status, timeline_doc, plan_summary, start_date, target_deadline, phases_json, p_id))
    else:
        cursor.execute("""
        INSERT INTO projects (name, status, timeline_doc, plan_summary, start_date, target_deadline, phases_json, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (name, status, timeline_doc, plan_summary, start_date, target_deadline, phases_json, now_str))
        p_id = cursor.lastrowid

    conn.commit()
    cursor.execute("SELECT * FROM projects WHERE id = ?", (p_id,))
    row = dict(cursor.fetchone())
    conn.close()
    return row

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

