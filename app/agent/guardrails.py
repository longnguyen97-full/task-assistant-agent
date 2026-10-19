"""
Site Scope Guardrail Engine.
Ensures that the Agent only processes requests, notes, and tasks that are associated with
or directly derived from registered sites/projects in the system.
"""
import re
from typing import Dict, Any, List, Optional, Tuple
from app.database import db_get_registered_sites

EXEMPT_PATTERNS = [
    r"xuất\s+báo\s+cáo",
    r"export\s+.*report",
    r"báo\s+cáo\s+tháng",
    r"báo\s+cáo\s+hàng\s+tháng",
    r"danh\s+sách\s+(?:site|dự\s+án|website)",
    r"các\s+site\s+hiện\s+có",
    r"hệ\s+thống\s+có\s+(?:những\s+)?site\s+nào",
    r"phạm\s+vi\s+site",
    r"hướng\s+dẫn",
    r"trợ\s+giúp",
    r"bạn\s+làm\s+được\s+gì",
    r"cài\s+đặt",
    r"cấu\s+hình",
    r"settings",
    r"api\s+key"
]

def _normalize_text(text: str) -> str:
    """Normalize vietnamese text for resilient matching."""
    t = text.lower().strip()
    # Replace common diacritics for fallback comparison
    replacements = (
        ("á|à|ả|ã|ạ|ă|ắ|ằ|ẳ|ẵ|ặ|â|ấ|ầ|ẩ|ẫ|ậ", "a"),
        ("é|è|ẻ|ẽ|ẹ|ê|ế|ề|ể|ễ|ệ", "e"),
        ("í|ì|ỉ|ĩ|ị", "i"),
        ("ó|ò|ỏ|õ|ọ|ô|ố|ồ|ổ|ỗ|ộ|ơ|ớ|ờ|ở|ỡ|ợ", "o"),
        ("ú|ù|ủ|ũ|ụ|ư|ứ|ừ|ử|ữ|ự", "u"),
        ("ý|ỳ|ỷ|ỹ|ỵ", "y"),
        ("đ", "d"),
    )
    import re
    for pat, rep in replacements:
        t = re.sub(pat, rep, t)
    return t

def check_site_scope(user_message: str) -> Dict[str, Any]:
    """Kiểm tra tin nhắn người dùng có thuộc phạm vi các site/dự án đang quản lý hay không.
    
    Quy tắc:
    1. Các câu lệnh hệ thống (xuất báo cáo, danh sách site, hướng dẫn) -> Cho phép (EXEMPT).
    2. Nếu tin nhắn có nhắc đến một site đã đăng ký (hoặc từ khóa chính của site) -> Cho phép (MATCHED).
    3. Nếu tin nhắn có đề cập đến mối liên hệ gần như 'clone từ [site]', 'dựa trên [site]' -> Cho phép (RELATED).
    4. Ngược lại (không kèm tên site hoặc không liên quan gì đến site hiện có) -> Chặn (OUT_OF_SCOPE).
    """
    msg_clean = user_message.strip()
    msg_lower = msg_clean.lower()
    msg_norm = _normalize_text(msg_clean)

    registered_sites = db_get_registered_sites()

    # Fallback default sites if DB has no sites yet
    if not registered_sites:
        registered_sites = [
            "SIS Vạn Phúc",
            "SVIS Vạn Phúc",
            "SIS / SVIS - Convert Elementor to Hand-Code",
            "Hệ Thống Agentic AI Giám Sát Website"
        ]

    # 1. Check Exempt System Actions
    for pat in EXEMPT_PATTERNS:
        if re.search(pat, msg_lower):
            return {
                "allowed": True,
                "is_exempt": True,
                "matched_site": None,
                "registered_sites": registered_sites,
                "reason": "Exempt system command"
            }

    # 2. Check direct site mentions or relationships
    matched_site = None
    matched_reason = ""

    # Known key site abbreviations & alias mapping
    site_aliases = {
        "sis vạn phúc": "SIS Vạn Phúc",
        "sis van phuc": "SIS Vạn Phúc",
        "svis vạn phúc": "SVIS Vạn Phúc",
        "svis van phuc": "SVIS Vạn Phúc",
        "vạn phúc": "SIS / SVIS Vạn Phúc",
        "van phuc": "SIS / SVIS Vạn Phúc",
        "sis": "SIS Vạn Phúc",
        "svis": "SVIS Vạn Phúc",
        "kig": "KIG Website",
        "kik": "KIK Website",
        "pegasus": "Pegasus Website",
        "obv": "OBV Website",
        "elementor": "SIS / SVIS - Convert Elementor to Hand-Code",
        "hand-code": "SIS / SVIS - Convert Elementor to Hand-Code",
        "hand code": "SIS / SVIS - Convert Elementor to Hand-Code",
        "agentic ai": "Hệ Thống Agentic AI Giám Sát Website",
        "giám sát website": "Hệ Thống Agentic AI Giám Sát Website",
        "giam sat website": "Hệ Thống Agentic AI Giám Sát Website"
    }

    # Check registered sites from DB
    for site in registered_sites:
        s_lower = site.lower()
        s_norm = _normalize_text(site)

        # Direct exact or substring match
        if s_lower in msg_lower or s_norm in msg_norm:
            matched_site = site
            matched_reason = f"Trực tiếp nhắc đến site '{site}'"
            break

        # Check sub-words of registered sites if length >= 3
        parts = [p.strip() for p in re.split(r"[/–\-\(\)]", site) if len(p.strip()) >= 3]
        for p in parts:
            p_low = p.lower()
            if p_low in msg_lower and len(p_low) > 3:
                matched_site = site
                matched_reason = f"Khớp từ khóa '{p}' của site '{site}'"
                break
        if matched_site:
            break

    # Check aliases if not matched yet
    if not matched_site:
        for alias, mapped_site in site_aliases.items():
            # Check standalone word or phrase
            pattern = rf"\b{re.escape(alias)}\b"
            if re.search(pattern, msg_lower) or re.search(pattern, msg_norm):
                matched_site = mapped_site
                matched_reason = f"Khớp alias '{alias}'"
                break

    # Check clone / derivation patterns (e.g. "clone từ SIS Vạn Phúc", "svis clone từ sis")
    if not matched_site:
        clone_match = re.search(r"clone\s+(?:từ|sang|cho)?\s*([a-zA-Z0-9\s\u00C0-\u1EF9]+)", msg_lower)
        if clone_match:
            cand = clone_match.group(1).strip()
            for alias, mapped_site in site_aliases.items():
                if alias in cand:
                    matched_site = f"{cand.title()} (clone từ {mapped_site})"
                    matched_reason = f"Phát hiện luồng clone liên quan tới {mapped_site}"
                    break

    if matched_site:
        return {
            "allowed": True,
            "is_exempt": False,
            "matched_site": matched_site,
            "registered_sites": registered_sites,
            "reason": matched_reason
        }

    # 3. Blocked: Out of Scope
    bullet_list = "\n".join([f"- 🌐 **{s}**" for s in registered_sites])
    refusal_message = (
        "🛡️ **YÊU CẦU NẰM NGOÀI PHẠM VI SITE ĐANG QUẢN LÝ**\n\n"
        "Hệ thống đang kích hoạt cơ chế **Giới Hạn Phạm Vi Site (Site-Scoped Guardrail)**.\n"
        "Agent chỉ xử lý các công việc/ghi chú khi xác định rõ thuộc site/dự án cụ thể hoặc có liên quan trực tiếp đến các site hiện có trong hệ thống.\n\n"
        f"📋 **Danh sách các Site / Dự án hiện có:**\n{bullet_list}\n\n"
        "💡 **Cách khắc phục để Agent hỗ trợ bạn ngay:**\n"
        "1. Kèm theo **tên site** trong tin nhắn (Ví dụ: `[SIS Vạn Phúc] Sửa lỗi header...` hoặc `project SVIS Vạn Phúc: clone từ SIS Vạn Phúc...`).\n"
        "2. Nếu là site phát sinh (như clone/kế thừa), vui lòng ghi rõ mối liên hệ (Ví dụ: `clone từ SIS Vạn Phúc...`).\n"
        "3. Nếu là dự án mới hoàn toàn, bạn hãy thêm vào hệ thống trước tại tab **Dự Án & Timeline**!"
    )

    return {
        "allowed": False,
        "is_exempt": False,
        "matched_site": None,
        "registered_sites": registered_sites,
        "refusal_message": refusal_message,
        "reason": "Tin nhắn không chứa tên site hoặc không liên quan đến site đang quản lý"
    }
