import smtplib
import json
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Dict, Any, Optional
from app.config import settings
from app.database import db_log_email

def tool_dispatch_email(
    to_email: str,
    subject: str,
    body: str,
    email_type: str = "daily_report"
) -> str:
    """Tự động gửi email thông báo, báo cáo tiến độ hàng ngày, hoặc email xin hỗ trợ blocker qua SMTP.
    
    Args:
        to_email: Địa chỉ email người nhận (ví dụ: lead@company.com, pm@company.com)
        subject: Tiêu đề email
        body: Nội dung email (có thể định dạng markdown hoặc text rõ ràng)
        email_type: Loại email ('daily_report', 'blocker_escalation', 'sprint_summary', 'manual')
    """
    if not to_email:
        to_email = settings.DEV_EMAIL

    # Check if SMTP is configured
    is_smtp_configured = bool(settings.SMTP_HOST and settings.SMTP_USER and settings.SMTP_PASSWORD)

    if not is_smtp_configured:
        # Mock / Simulation mode
        email_id = db_log_email(
            to_email=to_email,
            subject=subject,
            body=body,
            email_type=email_type,
            status="SIMULATED",
            error_message="Chưa cấu hình SMTP thực; lưu ở chế độ mô phỏng thành công."
        )
        return json.dumps({
            "status": "SIMULATED",
            "message": f"Email #{email_id} đã được chuẩn bị và lưu vào Email Dispatcher Outbox (Chế độ mô phỏng). Bạn có thể xem chi tiết trong tab 'Email Dispatcher'.",
            "to": to_email,
            "subject": subject,
            "email_id": email_id
        }, ensure_ascii=False)

    try:
        msg = MIMEMultipart()
        msg["From"] = settings.SMTP_FROM or settings.SMTP_USER
        msg["To"] = to_email
        msg["Subject"] = subject

        # Attach body
        msg.attach(MIMEText(body, "plain", "utf-8"))

        # Connect to SMTP server
        if settings.SMTP_PORT == 465:
            server = smtplib.SMTP_SSL(settings.SMTP_HOST, settings.SMTP_PORT, timeout=10)
        else:
            server = smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=10)
            if settings.SMTP_TLS:
                server.starttls()

        server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
        server.send_message(msg)
        server.quit()

        email_id = db_log_email(
            to_email=to_email,
            subject=subject,
            body=body,
            email_type=email_type,
            status="SENT"
        )
        return json.dumps({
            "status": "SENT",
            "message": f"Đã gửi email thực tế thành công tới {to_email} qua SMTP!",
            "email_id": email_id,
            "subject": subject
        }, ensure_ascii=False)

    except Exception as e:
        err_msg = str(e)
        email_id = db_log_email(
            to_email=to_email,
            subject=subject,
            body=body,
            email_type=email_type,
            status="FAILED",
            error_message=err_msg
        )
        return json.dumps({
            "status": "FAILED",
            "error": f"Lỗi khi gửi SMTP: {err_msg}. Email đã được lưu lại với trạng thái FAILED.",
            "email_id": email_id
        }, ensure_ascii=False)
