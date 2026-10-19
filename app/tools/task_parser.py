import re
import json
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from app.database import db_create_task

def parse_teams_or_email_message(raw_text: str, source: str = "TEAMS", author: str = "Developer") -> Dict[str, Any]:
    """Phân tích nội dung tin nhắn nhận từ MS Teams hoặc Email để tự động chuyển thành Task chuẩn hóa.
    
    Tự động bóc tách:
    - Thuộc website / dự án nào (KIG, SIS, SVIS, KIK, Pegasus, SISH, OBV...)
    - Tên công việc (Title) & Chi tiết yêu cầu
    - Hạn chót (Deadline)
    - Mức độ ưu tiên (LOW, MEDIUM, HIGH, URGENT)
    - Blocker hoặc ghi chú đặc biệt
    """
    clean_text = raw_text.strip()
    if not clean_text:
        return {"error": "Nội dung tin nhắn trống"}

    text_lower = clean_text.lower()

    # 1. Detect target website / project
    detected_site = ""
    proj_match = re.search(r"(?:project|dự án|hệ thống)\s+([^,\.\n:]+)", clean_text, re.IGNORECASE)
    if proj_match:
        detected_site = proj_match.group(1).strip()
    else:
        site_keywords = {
            "KIG Website": ["kig", "kinderworld international group"],
            "SIS / SVIS Website": ["sis", "svis", "singapore international school", "singapore vietnamese"],
            "KIK Website": ["kik", "kinderworld international kindergarten"],
            "Pegasus Website": ["pegasus", "pic", "pihm"],
            "SISH Website": ["sish", "sish institute"],
            "OBV Website": ["obv", "outward bound", "outwardbound"]
        }
        for site_name, kw_list in site_keywords.items():
            if any(kw in text_lower for kw in kw_list):
                detected_site = site_name
                break
    if not detected_site:
        detected_site = "Chung"

    # 2. Detect Priority
    priority = "MEDIUM"
    if any(w in text_lower for w in ["gấp", "khẩn", "urgent", "asap", "ngay lập tức", "hotfix", "critical"]):
        priority = "URGENT"
    elif any(w in text_lower for w in ["ưu tiên", "quan trọng", "high priority", "sớm nhất có thể"]):
        priority = "HIGH"
    elif any(w in text_lower for w in ["khi nào rảnh", "low priority", "không vội", "tùy ý"]):
        priority = "LOW"

    # 3. Detect Deadline
    deadline_str = ""
    today = datetime.now()
    
    # Try exact date patterns like 25/10, 25-10, 2026-10-25, 23/10/2026
    date_match = re.search(r"(\d{1,2})[/-](\d{1,2})(?:[/-](\d{4}))?", clean_text)
    if date_match:
        try:
            d = int(date_match.group(1))
            m = int(date_match.group(2))
            y = int(date_match.group(3)) if date_match.group(3) else today.year
            deadline_str = f"{y:04d}-{m:02d}-{d:02d}"
        except Exception:
            pass

    if not deadline_str:
        if "hôm nay" in text_lower or "today" in text_lower:
            deadline_str = today.strftime("%Y-%m-%d")
        elif "ngày mai" in text_lower or "tomorrow" in text_lower:
            deadline_str = (today + timedelta(days=1)).strftime("%Y-%m-%d")
        elif "thứ 6" in text_lower or "thứ sáu" in text_lower:
            # next Friday
            days_ahead = (4 - today.weekday()) % 7
            if days_ahead == 0: days_ahead = 7
            deadline_str = (today + timedelta(days=days_ahead)).strftime("%Y-%m-%d")
        elif "cuối tuần" in text_lower:
            days_ahead = (6 - today.weekday()) % 7
            deadline_str = (today + timedelta(days=days_ahead)).strftime("%Y-%m-%d")
        elif "cuối tháng" in text_lower:
            next_month = today.replace(day=28) + timedelta(days=4)
            last_day = next_month - timedelta(days=next_month.day)
            deadline_str = last_day.strftime("%Y-%m-%d")

    # 4. Extract Title & Action items
    content_match = re.search(r"(?:nội dung|yêu cầu)\s*:\s*([^,\.\n]+.*)", clean_text, re.IGNORECASE)
    if content_match:
        title_candidate = content_match.group(1).strip()
    else:
        lines = [l.strip() for l in clean_text.split("\n") if l.strip()]
        first_line = lines[0] if lines else clean_text[:60]
        title_candidate = re.sub(r"^(?:re:|fwd:|fw:|\[teams\]|\[email\]|task:|yêu cầu:)\s*", "", first_line, flags=re.IGNORECASE).strip()

    title_candidate = title_candidate[0].upper() + title_candidate[1:] if title_candidate else f"Xử lý yêu cầu từ {source}"
    if len(title_candidate) > 75:
        title_candidate = title_candidate[:72] + "..."

    formatted_title = f"[{detected_site}] {title_candidate}"

    # 5. Save structured task into SQLite
    created_task = db_create_task(
        title=formatted_title,
        description=f"Nội dung nhận qua {source}:\n\n{clean_text}",
        status="TODO",
        priority=priority,
        assignee="Developer",
        deadline=deadline_str,
        tags=f"{source.lower()}, {detected_site.lower().replace(' website', '')}",
        source_type="TEAMS_EMAIL",
        website_name=detected_site
    )

    return {
        "success": True,
        "task": created_task,
        "parsed_metadata": {
            "source": source,
            "target_website": detected_site,
            "priority": priority,
            "deadline": deadline_str or "Không quy định rõ",
            "title": formatted_title
        },
        "summary_markdown": (
            f"✅ **Đã tiếp nhận & chuyển thành Task từ {source}:**\n"
            f"- **Công việc:** `{formatted_title}` (Task #{created_task['id']})\n"
            f"- **Website / Dự án:** `{detected_site}`\n"
            f"- **Mức độ ưu tiên:** `{priority}`\n"
            f"- **Hạn chót:** {deadline_str if deadline_str else 'Trong tuần / linh hoạt'}\n"
            f"- **Trạng thái:** `TODO` (Đã đưa lên Bảng Tasks / Kanban)"
        )
    }
