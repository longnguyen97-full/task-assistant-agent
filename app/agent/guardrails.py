"""
Site Scope & Allowed Resources Guardrail Engine.
Ensures that the Agent strictly processes requests ONLY when they belong to:
1. Registered projects in the system (db_get_registered_sites).
2. Approved paths in the Allowed Resources whitelist (db_is_path_allowed).
3. Core system commands (export report, settings, help).
"""
import re
import os
from typing import Dict, Any, List, Optional, Tuple
from app.database import (
    db_get_registered_sites,
    db_get_all_allowed_resources,
    db_is_path_allowed
)

EXEMPT_PATTERNS = [
    r"xuất\s+báo\s+cáo",
    r"export\s+.*report",
    r"báo\s+cáo\s+tháng",
    r"báo\s+cáo\s+hàng\s+tháng",
    r"danh\s+sách\s+(?:site|dự\s+án|website|resource|tài\s+nguyên)",
    r"các\s+site\s+hiện\s+có",
    r"hướng\s+dẫn",
    r"trợ\s+giúp",
    r"bạn\s+làm\s+được\s+gì",
    r"cài\s+đặt",
    r"cấu\s+hình",
    r"settings",
    r"api\s+key",
    r"xóa\s+dự\s+án",
    r"xoá\s+dự\s+án",
    r"delete\s+project"
]

def _normalize_text(text: str) -> str:
    """Normalize vietnamese text for resilient matching."""
    t = text.lower().strip()
    replacements = (
        ("á|à|ả|ã|ạ|ă|ắ|ằ|ẳ|ẵ|ặ|â|ấ|ầ|ẩ|ẫ|ậ", "a"),
        ("é|è|ẻ|ẽ|ẹ|ê|ế|ề|ể|ễ|ệ", "e"),
        ("í|ì|ỉ|ĩ|ị", "i"),
        ("ó|ò|ỏ|õ|ọ|ô|ố|ồ|ổ|ỗ|ộ|ơ|ớ|ờ|ở|ỡ|ợ", "o"),
        ("ú|ù|ủ|ũ|ụ|ư|ứ|ừ|ử|ữ|ự", "u"),
        ("ý|ỳ|ỷ|ỹ|ỵ", "y"),
        ("đ", "d"),
    )
    for pat, rep in replacements:
        t = re.sub(pat, rep, t)
    return t

def check_site_scope(user_message: str) -> Dict[str, Any]:
    """Kiểm tra tin nhắn người dùng có thuộc phạm vi hệ thống cho phép hay không.
    
    Quy tắc chặt chẽ:
    1. Các câu lệnh hệ thống cốt lõi (xuất báo cáo, cài đặt, trợ giúp) -> Cho phép (EXEMPT).
    2. Các câu hỏi/yêu cầu quét đường dẫn -> Chỉ cho phép khi đường dẫn thuộc danh sách Allowed Resources.
       (Nếu đường dẫn sai định dạng như thiếu dấu gạch chéo mạng, báo lỗi sai đường dẫn mà không tự bù).
    3. Các câu hỏi/yêu cầu công việc -> Chỉ cho phép khi thuộc các Dự án trong danh sách dự án đã đăng ký.
    4. Ngược lại -> Chặn và thông báo rõ 2 danh sách hợp lệ để người dùng đối chiếu.
    """
    msg_clean = user_message.strip()
    msg_lower = msg_clean.lower()
    msg_norm = _normalize_text(msg_clean)

    registered_sites = db_get_registered_sites()
    allowed_resources = db_get_all_allowed_resources()

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

    # 2. Check Rule 2: Các đường dẫn trong Allowed Resources
    # Bóc tách đường dẫn xuất hiện trong câu lệnh nếu có (UNC Windows hoặc Drive letter)
    path_match = re.search(r"(\\{1,2}[a-zA-Z0-9_\-\.]+\\[a-zA-Z0-9_\-\$\.\\]*|[a-zA-Z]:\\[a-zA-Z0-9_\-\$\.\\]*)", user_message)
    if path_match:
        extracted_path = path_match.group(1).strip().rstrip(".,;")

        # Nếu người dùng gõ sai định dạng đường dẫn mạng (\host\share thay vì \\host\share)
        # Hệ thống không tự add dấu gạch mà thông báo lỗi sai cú pháp theo đúng chỉ đạo
        if extracted_path.startswith("\\") and not extracted_path.startswith("\\\\"):
            res_bullets = "\n".join([f"- 📂 **{r['name']}:** `{r['path']}`" for r in allowed_resources])
            return {
                "allowed": False,
                "is_exempt": False,
                "matched_site": None,
                "registered_sites": registered_sites,
                "refusal_message": (
                    f"⚠️ **ĐƯỜNG DẪN SAI ĐỊNH DẠNG HOẶC KHÔNG TỒN TẠI**\n\n"
                    f"Đường dẫn bạn cung cấp `{extracted_path}` bị sai cú pháp.\n"
                    f"👉 **Lưu ý:** Đường dẫn chia sẻ mạng Windows UNC cần bắt đầu bằng **2 dấu gạch chéo** `\\\\` (Ví dụ: `\\\\{extracted_path.lstrip(chr(92))}`).\n\n"
                    f"📋 **Danh sách các Allowed Resources hợp lệ trong hệ thống:**\n{res_bullets}"
                ),
                "reason": "Đường dẫn mạng sai định dạng (thiếu dấu gạch chéo \\\\)"
            }

        # Kiểm tra xem đường dẫn có nằm trong danh sách Allowed Resources hay không
        is_allowed, matched_res = db_is_path_allowed(extracted_path)
        if is_allowed and matched_res:
            return {
                "allowed": True,
                "is_exempt": False,
                "matched_site": f"Resource: {matched_res['name']}",
                "matched_resource": matched_res,
                "registered_sites": registered_sites,
                "reason": f"Khớp Allowed Resource '{matched_res['name']}' ({matched_res['path']})"
            }
        else:
            # Đường dẫn không nằm trong Allowed Resources -> Chặn ngay lập tức theo quy định
            res_bullets = "\n".join([f"- 📂 **{r['name']}:** `{r['path']}`" for r in allowed_resources])
            return {
                "allowed": False,
                "is_exempt": False,
                "matched_site": None,
                "registered_sites": registered_sites,
                "refusal_message": (
                    f"🛡️ **ĐƯỜNG DẪN NGOÀI DANH SÁCH CHO PHÉP (ALLOWED RESOURCES)**\n\n"
                    f"Đường dẫn `{extracted_path}` **chưa được khai báo** trong danh sách tài nguyên được phép truy cập (Allowed Resources).\n\n"
                    f"📋 **Danh sách các Allowed Resources đang được cấp quyền:**\n{res_bullets}\n\n"
                    f"💡 **Cách khắc phục:** Vui lòng chỉ định một đường dẫn nằm trong danh sách trên hoặc thêm đường dẫn mới vào hệ thống Allowed Resources."
                ),
                "reason": f"Đường dẫn '{extracted_path}' không thuộc Allowed Resources"
            }

    # 3. Check Rule 1: Các dự án trong danh sách dự án đã đăng ký
    matched_site = None
    matched_reason = ""

    # Known key site abbreviations & alias mapping (liên kết với dự án thực tế)
    site_aliases = {
        "gamuda": "SIS Gamuda Gardens",
        "sis gamuda": "SIS Gamuda Gardens",
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

        if s_lower in msg_lower or s_norm in msg_norm:
            matched_site = site
            matched_reason = f"Trực tiếp nhắc đến site '{site}'"
            break

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
            pattern = rf"\b{re.escape(alias)}\b"
            if re.search(pattern, msg_lower) or re.search(pattern, msg_norm):
                matched_site = mapped_site
                matched_reason = f"Khớp alias '{alias}'"
                break

    # Check clone / derivation patterns
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

    # 4. Out of Scope: Neither registered project nor allowed resource
    proj_bullets = "\n".join([f"- 🌐 **{s}**" for s in registered_sites])
    res_bullets = "\n".join([f"- 📂 **{r['name']}:** `{r['path']}`" for r in allowed_resources])

    refusal_message = (
        "🛡️ **YÊU CẦU NẰM NGOÀI PHẠM VI HỆ THỐNG**\n\n"
        "Agent chỉ tiếp nhận và xử lý khi câu hỏi hoặc tác vụ thuộc một trong hai phạm vi sau:\n\n"
        f"1️⃣ **Các Dự án đã đăng ký trong hệ thống:**\n{proj_bullets}\n\n"
        f"2️⃣ **Các Đường dẫn trong Allowed Resources:**\n{res_bullets}\n\n"
        "💡 **Cách khắc phục để Agent hỗ trợ bạn:**\n"
        "- **Nếu là công việc dự án:** Kèm theo tên dự án hợp lệ trong danh sách trên (hoặc tạo dự án mới tại tab **Dự Án & Timeline**).\n"
        "- **Nếu là quét tìm tệp/tài liệu:** Chỉ định đường dẫn thuộc danh sách Allowed Resources trên và viết đúng chuẩn (Ví dụ: `\\\\172.16.44.103\\design$`)."
    )

    return {
        "allowed": False,
        "is_exempt": False,
        "matched_site": None,
        "registered_sites": registered_sites,
        "refusal_message": refusal_message,
        "reason": "Yêu cầu không thuộc danh sách Dự án và không thuộc Allowed Resources"
    }
