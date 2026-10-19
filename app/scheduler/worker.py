import json
from datetime import datetime, date
from typing import Dict, Any, Optional
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from app.config import settings
from app.database import (
    db_get_all_tasks,
    db_log_scheduler,
    db_get_scheduler_logs
)
from app.tools.email_tools import tool_dispatch_email

_scheduler: Optional[BackgroundScheduler] = None

def run_morning_scan(triggered_by: str = "MANUAL") -> Dict[str, Any]:
    """Quét các task tồn đọng, quá hạn hoặc đang bị BLOCKED.
    Chủ động tạo thông báo và có thể gửi email nhắc nhở cho dev.
    """
    all_tasks = db_get_all_tasks()
    today = date.today()

    overdue_tasks = []
    due_today_tasks = []
    blocked_tasks = []

    for t in all_tasks:
        status = t["status"]
        deadline_str = t.get("deadline", "")
        
        if status != "DONE" and deadline_str:
            try:
                d_date = datetime.strptime(deadline_str[:10], "%Y-%m-%d").date()
                diff = (d_date - today).days
                if diff < 0:
                    overdue_tasks.append({
                        "id": t["id"],
                        "title": t["title"],
                        "deadline": deadline_str,
                        "days_overdue": abs(diff),
                        "priority": t["priority"]
                    })
                elif diff == 0:
                    due_today_tasks.append({
                        "id": t["id"],
                        "title": t["title"],
                        "deadline": deadline_str,
                        "priority": t["priority"]
                    })
            except Exception:
                pass

        if status == "BLOCKED":
            blocked_tasks.append({
                "id": t["id"],
                "title": t["title"],
                "blocker_reason": t.get("blocker_reason") or "Chưa rõ lý do",
                "priority": t["priority"]
            })

    # Summary text
    summary = (
        f"Quét hoàn tất: {len(overdue_tasks)} task quá hạn, "
        f"{len(due_today_tasks)} task đến hạn hôm nay, "
        f"{len(blocked_tasks)} task đang bị nghẽn (BLOCKED)."
    )

    findings = {
        "overdue_count": len(overdue_tasks),
        "due_today_count": len(due_today_tasks),
        "blocked_count": len(blocked_tasks),
        "overdue_tasks": overdue_tasks,
        "due_today_tasks": due_today_tasks,
        "blocked_tasks": blocked_tasks
    }

    # If there are urgent blockers or overdue tasks, generate a proactive reminder email
    if overdue_tasks or blocked_tasks:
        email_body_lines = [
            f"Chào buổi sáng Developer Team,",
            f"\nBáo cáo nhắc việc sáng từ Task Assistant ({datetime.now().strftime('%d/%m/%Y %H:%M')}):",
            f"\n1. Các task quá hạn ({len(overdue_tasks)}):"
        ]
        for ot in overdue_tasks:
            email_body_lines.append(f" - [ID #{ot['id']}] {ot['title']} (Quá hạn {ot['days_overdue']} ngày - Priority: {ot['priority']})")

        email_body_lines.append(f"\n2. Các task đang bị nghẽn (BLOCKED) ({len(blocked_tasks)}):")
        for bt in blocked_tasks:
            email_body_lines.append(f" - [ID #{bt['id']}] {bt['title']}: {bt['blocker_reason']}")

        email_body_lines.append("\nVui lòng cập nhật trạng thái hoặc liên hệ Tech Lead để tháo gỡ blocker sớm nhất!")
        
        tool_dispatch_email(
            to_email=settings.DEV_EMAIL,
            subject=f"[Nhắc việc sáng] Cảnh báo {len(overdue_tasks)} task quá hạn & {len(blocked_tasks)} task nghẽn",
            body="\n".join(email_body_lines),
            email_type="reminder"
        )

    # Save to scheduler_logs
    log_id = db_log_scheduler(
        job_name="morning_proactive_reminder",
        triggered_by=triggered_by,
        summary=summary,
        findings=json.dumps(findings, ensure_ascii=False)
    )

    return {
        "log_id": log_id,
        "summary": summary,
        "findings": findings,
        "run_at": datetime.now().isoformat(),
        "triggered_by": triggered_by
    }

def start_scheduler():
    """Start APScheduler background scheduler."""
    global _scheduler
    if _scheduler is not None and _scheduler.running:
        return _scheduler

    _scheduler = BackgroundScheduler()

    # Schedule morning scan at configured hour:minute (default 9:00 AM)
    trigger = CronTrigger(hour=settings.REMINDER_HOUR, minute=settings.REMINDER_MINUTE)
    _scheduler.add_job(
        func=lambda: run_morning_scan(triggered_by="CRON"),
        trigger=trigger,
        id="morning_scan_job",
        name="Quét task định kỳ 9:00 AM",
        replace_existing=True
    )

    _scheduler.start()
    return _scheduler

def get_scheduler_status() -> Dict[str, Any]:
    """Get status of scheduler and next run time."""
    global _scheduler
    is_running = _scheduler is not None and _scheduler.running
    next_run = None

    if is_running:
        job = _scheduler.get_job("morning_scan_job")
        if job and job.next_run_time:
            next_run = job.next_run_time.isoformat()

    recent_logs = db_get_scheduler_logs(limit=10)
    return {
        "is_running": is_running,
        "cron_hour": settings.REMINDER_HOUR,
        "cron_minute": settings.REMINDER_MINUTE,
        "next_run_time": next_run,
        "recent_logs": recent_logs
    }
