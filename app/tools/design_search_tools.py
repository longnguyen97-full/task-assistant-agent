import os
import re
import json
import base64
import zipfile
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
import requests

from app.config import settings
from app.database import db_is_path_allowed

# -------------------------------------------------------------
# 1. BLACKLIST & PATH VALIDATION SAFEGUARDS
# -------------------------------------------------------------

# Các thư mục hệ thống cấm quét vì lý do an toàn và bảo mật
WINDOWS_SYSTEM_BLACKLIST = [
    r"^[a-zA-Z]:\\?$",                          # Cả ổ đĩa gốc như C:\, D:\ (quá rộng và chứa file hệ điều hành)
    r"^[a-zA-Z]:\\windows",                     # Thư mục hệ điều hành Windows
    r"^[a-zA-Z]:\\program files",               # Thư mục cài đặt phần mềm
    r"^[a-zA-Z]:\\program files \(x86\)",
    r"^[a-zA-Z]:\\programdata",
    r"^[a-zA-Z]:\\system volume information",   # Thư mục phục hồi hệ thống
    r"^[a-zA-Z]:\\\$recycle\.bin",              # Thùng rác
    r"^[a-zA-Z]:\\recovery",
    r"^[a-zA-Z]:\\boot",
    r"^[a-zA-Z]:\\users\\default",
    r"^\\\\\w+[^\\]*\\(?:admin|c|ipc)\$",       # Administrative hidden shares (ADMIN$, C$, IPC$)
]

def validate_search_path(folder_path: str) -> Tuple[bool, str, Optional[str]]:
    """Kiểm tra tính an toàn (Blacklist) và khả năng truy cập của đường dẫn thư mục.
    
    Returns:
        (is_valid, status_code, message)
        status_code: 'OK' | 'BLACKLISTED' | 'NOT_FOUND' | 'NOT_A_DIRECTORY' | 'PERMISSION_DENIED' | 'NETWORK_ERROR'
    """
    if not folder_path or not folder_path.strip():
        return False, "INVALID_PATH", "Đường dẫn thư mục không được để trống."

    clean_path = folder_path.strip().strip('"').strip("'")

    # Kiểm tra nếu đường dẫn mạng bị thiếu dấu gạch chéo: Báo lỗi cú pháp, KHÔNG tự ý add dấu gạch
    if clean_path.startswith("\\") and not clean_path.startswith("\\\\"):
        return (
            False,
            "INVALID_SYNTAX",
            f"⚠️ **ĐƯỜNG DẪN SAI ĐỊNH DẠNG:** Đường dẫn `{clean_path}` bị sai cú pháp. Đường dẫn chia sẻ mạng Windows UNC cần bắt đầu bằng **2 dấu gạch chéo** (Ví dụ chuẩn: `\\{clean_path}`)."
        )

    norm_path = os.path.normpath(clean_path).lower()

    # 1. Kiểm tra Blacklist
    for pattern in WINDOWS_SYSTEM_BLACKLIST:
        if re.search(pattern, norm_path, re.IGNORECASE):
            return (
                False,
                "BLACKLISTED",
                f"🛡️ **CẢNH BÁO BẢO MẬT:** Đường dẫn `{clean_path}` nằm trong danh sách cấm (Blacklist) của hệ thống vì chứa tệp tin hệ điều hành/hệ thống nhạy cảm. Vui lòng chỉ định một thư mục tài liệu hoặc thiết kế hợp lệ (ví dụ: `\\\\172.16.44.103\\design$`, thư mục dự án riêng, hoặc thư mục con)."
            )

    # 2. Kiểm tra danh sách Allowed Resources được phép truy cập
    is_allowed, matched_res = db_is_path_allowed(clean_path)
    if not is_allowed:
        return (
            False,
            "NOT_IN_ALLOWED_RESOURCES",
            f"🛡️ **ĐƯỜNG DẪN NGOÀI DANH SÁCH CHO PHÉP (ALLOWED RESOURCES):** Đường dẫn `{clean_path}` không nằm trong danh sách Allowed Resources được cấp phép. Agent chỉ được phép quét các thư mục đã được phê duyệt."
        )

    # 2. Kiểm tra nhanh kết nối nếu là đường dẫn mạng UNC (\\\\host\\share)
    if clean_path.startswith(("\\\\", "//")):
        parts = clean_path.lstrip("\\/").split("\\")
        if not parts or not parts[0]:
            parts = clean_path.lstrip("\\/").split("/")
        if parts and parts[0]:
            host = parts[0]
            import socket
            host_alive = False
            for port in (445, 139):
                try:
                    with socket.create_connection((host, port), timeout=2.0):
                        host_alive = True
                        break
                except Exception:
                    pass
            if not host_alive:
                return (
                    False,
                    "NETWORK_ERROR",
                    f"🔌 **LỖI TRUY CẬP Ổ MẠNG:** Không thể kết nối tới máy chủ `{host}` qua cổng chia sẻ file SMB/LAN (Timeout sau 2s). Vui lòng kiểm tra lại địa chỉ IP, mạng nội bộ hoặc VPN công ty."
                )

    # 3. Kiểm tra tồn tại
    if not os.path.exists(clean_path):
        return (
            False,
            "NOT_FOUND",
            f"⚠️ **KHÔNG TÌM THẤY:** Đường dẫn `{clean_path}` không tồn tại. Vui lòng kiểm tra lại chính tả hoặc kết nối mạng/ổ đĩa mạng LAN."
        )

    # 3. Kiểm tra có phải thư mục
    if not os.path.isdir(clean_path):
        return (
            False,
            "NOT_A_DIRECTORY",
            f"⚠️ **LỖI ĐƯỜNG DẪN:** `{clean_path}` là một tệp tin chứ không phải thư mục."
        )

    # 4. Kiểm tra quyền truy cập (Permission / Network Connectivity)
    try:
        with os.scandir(clean_path) as it:
            next(it, None)
    except PermissionError:
        return (
            False,
            "PERMISSION_DENIED",
            f"🚫 **TRUY CẬP BỊ TỪ CHỐI:** Không có quyền đọc nội dung thư mục `{clean_path}` (Permission Denied). Vui lòng kiểm tra phân quyền tài khoản hoặc cấu hình quyền truy cập thư mục chia sẻ."
        )
    except OSError as e:
        return (
            False,
            "NETWORK_ERROR",
            f"🔌 **LỖI TRUY CẬP Ổ MẠNG:** Không thể kết nối hoặc đọc thư mục `{clean_path}`. Chi tiết: {str(e)}"
        )
    except Exception as e:
        return (
            False,
            "ACCESS_ERROR",
            f"⚠️ **LỖI TRUY CẬP:** Không thể mở thư mục `{clean_path}`: {str(e)}"
        )

    return True, "OK", None


# -------------------------------------------------------------
# 2. FEATURE EXTRACTION FROM IMAGE (GEMINI VISION / OCR)
# -------------------------------------------------------------

def extract_features_from_image(image_path: str) -> Dict[str, Any]:
    """Bóc tách đặc trưng văn bản, bảng biểu, mốc thời gian và từ khóa từ hình ảnh thiết kế."""
    p = Path(image_path)
    if not p.exists():
        # Thử tìm trong data/uploads hoặc data/docs
        cand1 = settings.DATA_DIR / "uploads" / p.name
        cand2 = settings.DATA_DIR / "docs" / p.name
        if cand1.exists():
            p = cand1
        elif cand2.exists():
            p = cand2
        else:
            return {
                "success": False,
                "keywords": [],
                "description": f"Không tìm thấy file ảnh tại: {image_path}"
            }

    # Đọc ảnh sang base64
    try:
        with open(p, "rb") as f:
            image_bytes = f.read()
            image_b64 = base64.b64encode(image_bytes).decode("utf-8")
    except Exception as e:
        return {"success": False, "keywords": [], "description": f"Lỗi đọc ảnh: {str(e)}"}

    mime_type = "image/png"
    if p.suffix.lower() in [".jpg", ".jpeg"]:
        mime_type = "image/jpeg"
    elif p.suffix.lower() == ".webp":
        mime_type = "image/webp"

    # Gọi Google Gemini Vision nếu có API Key
    if settings.GEMINI_API_KEY:
        try:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={settings.GEMINI_API_KEY}"
            prompt = (
                "Bạn là chuyên gia phân tích UI/UX và trích xuất dữ liệu thiết kế từ ảnh chụp màn hình.\n"
                "Hãy quan sát kỹ hình ảnh được cung cấp (chứa bảng biểu, thời gian, môn học, nhãn, tiêu đề, văn bản giao diện).\n"
                "Trích xuất tất cả các từ khóa và cụm từ đặc trưng nhất (unique keywords, headings, labels, timestamps, table cells) xuất hiện trong ảnh để dùng làm từ khóa tìm kiếm chính xác file thiết kế (.xd, figma, sketch).\n"
                "BẮT BUỘC trả về đúng định dạng JSON chuẩn (không kèm codeblock markdown) với cấu trúc sau:\n"
                "{\n"
                '  "keywords": ["từ khóa 1", "từ khóa 2", "Break/Snack", "Form Class", "Assembly", "Lunch"],\n'
                '  "unique_phrases": ["cụm từ độc nhất"],\n'
                '  "summary": "Mô tả ngắn gọn nội dung bảng/giao diện trong ảnh (ví dụ: Bảng thời khóa biểu trường học)"\n'
                "}"
            )

            payload = {
                "contents": [
                    {
                        "parts": [
                            {"text": prompt},
                            {
                                "inline_data": {
                                    "mime_type": mime_type,
                                    "data": image_b64
                                }
                            }
                        ]
                    }
                ],
                "generationConfig": {
                    "temperature": 0.1,
                    "response_mime_type": "application/json"
                }
            }

            resp = requests.post(url, json=payload, timeout=35)
            if resp.status_code == 200:
                data = resp.json()
                text_out = data["candidates"][0]["content"]["parts"][0]["text"].strip()
                # Parse JSON
                clean_json = text_out.replace("```json", "").replace("```", "").strip()
                extracted = json.loads(clean_json)
                extracted["success"] = True
                return extracted
            else:
                print(f"[WARN] Gemini Vision API error {resp.status_code}: {resp.text[:200]}")
        except Exception as e:
            print(f"[WARN] Exception during Gemini Vision feature extraction: {e}")

    # Fallback trích xuất tên file nếu không gọi được Gemini
    base_name = p.stem.replace("_", " ").replace("-", " ")
    return {
        "success": True,
        "keywords": [w for w in base_name.split() if len(w) > 2],
        "unique_phrases": [base_name],
        "summary": f"Hình ảnh đính kèm: {p.name}"
    }


# -------------------------------------------------------------
# 3. XD DESIGN FILE SCANNER & KEYWORD MATCHER
# -------------------------------------------------------------

def scan_xd_files_for_keywords(
    folder_path: str,
    keywords: List[str],
    max_depth: int = 4,
    max_files: int = 250
) -> Dict[str, Any]:
    """Quét các file Adobe XD (.xd) trong thư mục để tìm nội dung khớp từ khóa."""
    clean_kws = [k.strip().lower() for k in keywords if k and len(k.strip()) >= 2]
    if not clean_kws:
        return {"status": "error", "message": "Không có từ khóa hợp lệ để tìm kiếm.", "matches": []}

    matches = []
    scanned_count = 0
    clean_folder = os.path.normpath(folder_path.strip().strip('"').strip("'"))
    base_depth = clean_folder.count(os.sep)

    # Thư mục bỏ qua để tăng tốc độ quét trên ổ mạng
    IGNORE_DIRS = {
        ".git", "node_modules", ".cache", "tmp", "temp", "photos", "photo",
        "hinh", "video", "videos", "animation", "audio", ".svn", "$recycle.bin"
    }

    try:
        for root, dirs, files in os.walk(clean_folder):
            # Giới hạn độ sâu
            cur_depth = root.count(os.sep) - base_depth
            if cur_depth >= max_depth:
                dirs[:] = []
                continue

            # Lọc bỏ thư mục ảnh/video nặng không chứa thiết kế
            dirs[:] = [d for d in dirs if d.lower() not in IGNORE_DIRS and not d.startswith(".")]

            for f in files:
                if not f.lower().endswith(".xd"):
                    continue

                scanned_count += 1
                if scanned_count > max_files:
                    break

                file_path = os.path.join(root, f)
                try:
                    with zipfile.ZipFile(file_path, "r") as z:
                        namelist = z.namelist()
                        
                        # Đọc danh sách Artboards nếu có trong resources/graphics/graphicContent.agc
                        artboards_map = {}
                        if "resources/graphics/graphicContent.agc" in namelist:
                            try:
                                res_json = json.loads(z.read("resources/graphics/graphicContent.agc").decode("utf-8", errors="ignore"))
                                for ab_id, ab_info in res_json.get("artboards", {}).items():
                                    artboards_map[ab_id] = ab_info.get("name", ab_id)
                            except Exception:
                                pass

                        matched_kws = set()
                        matched_artboards = set()
                        matched_snippets = []

                        # Duyệt qua các file agc đồ họa và manifest
                        for name in namelist:
                            if name.endswith(".agc") or name.endswith(".json") or name == "manifest":
                                try:
                                    raw_text = z.read(name).decode("utf-8", errors="ignore")
                                    raw_lower = raw_text.lower()
                                except Exception:
                                    continue

                                for kw in clean_kws:
                                    if kw in raw_lower:
                                        matched_kws.add(kw)
                                        # Xác định artboard nếu file nằm trong artwork/artboard-{id}/
                                        if "artboard-" in name:
                                            try:
                                                ab_id = name.split("artboard-")[1].split("/")[0]
                                                ab_name = artboards_map.get(ab_id, ab_id)
                                                matched_artboards.add(ab_name)
                                            except Exception:
                                                pass

                        if matched_kws:
                            # Lấy thông tin kích thước và ngày sửa đổi
                            stat = os.stat(file_path)
                            size_mb = round(stat.st_size / (1024 * 1024), 2)
                            from datetime import datetime
                            mtime_str = datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M")

                            matches.append({
                                "file_name": f,
                                "full_path": file_path,
                                "file_size_mb": size_mb,
                                "last_modified": mtime_str,
                                "matched_keywords_count": len(matched_kws),
                                "matched_keywords": list(matched_kws),
                                "matched_artboards": list(matched_artboards)
                            })
                except Exception:
                    continue

            if scanned_count > max_files:
                break

    except Exception as e:
        return {
            "status": "error",
            "message": f"Lỗi trong quá trình quét file: {str(e)}",
            "matches": matches,
            "scanned_count": scanned_count
        }

    # Sắp xếp kết quả theo số lượng từ khóa khớp nhiều nhất
    matches.sort(key=lambda x: x["matched_keywords_count"], reverse=True)

    return {
        "status": "success",
        "scanned_count": scanned_count,
        "total_matches": len(matches),
        "matches": matches
    }


# -------------------------------------------------------------
# 4. MAIN AGENT TOOL: search_design_files
# -------------------------------------------------------------

def tool_search_design_files_by_image_or_text(
    folder_path: str,
    image_path: Optional[str] = None,
    keywords: Optional[str] = None,
    max_results: int = 10
) -> str:
    """Quét tìm file thiết kế Adobe XD (.xd) trong một thư mục (cục bộ hoặc mạng LAN UNC như \\\\172.16.44.103\\design$)
    dựa trên hình ảnh chụp màn hình (tự động bóc tách từ khóa bằng AI Vision) hoặc danh sách từ khóa chỉ định.
    
    Quy tắc an toàn:
    - Tự động kiểm tra Blacklist (chặn các thư mục hệ thống như C:\\Windows, C:\\Program Files...).
    - Kiểm tra tính truy cập (báo lỗi rõ ràng nếu không truy cập được hoặc ổ mạng mất kết nối).
    
    Args:
        folder_path: Đường dẫn thư mục cần quét (ví dụ: '\\\\172.16.44.103\\design$' hoặc 'D:\\Projects\\Design').
        image_path: Đường dẫn file ảnh chụp màn hình thiết kế cần tìm (nếu có).
        keywords: Chuỗi từ khóa ngăn cách bằng dấu phẩy nếu người dùng nhập trực tiếp (ví dụ: 'Break/Snack, Form Class, Assembly').
        max_results: Số lượng kết quả file khớp nhất cần trả về (mặc định 10).
    """
    # Giữ nguyên đường dẫn người dùng nhập
    norm_folder = folder_path.strip().strip('"').strip("'")

    # 1. Kiểm tra Blacklist & Khả năng truy cập của thư mục
    is_valid, status_code, err_msg = validate_search_path(norm_folder)
    if not is_valid:
        return json.dumps({
            "status": "blocked" if status_code == "BLACKLISTED" else "inaccessible",
            "code": status_code,
            "message": err_msg,
            "folder_path": norm_folder
        }, ensure_ascii=False)

    # 2. Bóc tách đặc trưng nếu có ảnh
    search_kws = []
    image_summary = ""
    if image_path and image_path.strip():
        img_features = extract_features_from_image(image_path)
        if img_features.get("success"):
            search_kws.extend(img_features.get("keywords", []))
            search_kws.extend(img_features.get("unique_phrases", []))
            image_summary = img_features.get("summary", "")

    # Bổ sung từ khóa từ tham số keywords nếu có
    if keywords:
        for k in keywords.split(","):
            k_clean = k.strip()
            if k_clean and k_clean not in search_kws:
                search_kws.append(k_clean)

    if not search_kws:
        return json.dumps({
            "status": "error",
            "message": "Không thể bóc tách từ khóa nào từ hình ảnh hoặc không có từ khóa tìm kiếm được cung cấp.",
            "folder_path": norm_folder
        }, ensure_ascii=False)

    # 3. Quét tệp tin Adobe XD
    scan_res = scan_xd_files_for_keywords(
        folder_path=norm_folder,
        keywords=search_kws,
        max_depth=4,
        max_files=300
    )

    if scan_res.get("status") == "error":
        return json.dumps({
            "status": "error",
            "message": scan_res.get("message"),
            "folder_path": norm_folder
        }, ensure_ascii=False)

    matches = scan_res.get("matches", [])[:max_results]

    return json.dumps({
        "status": "success",
        "folder_path": norm_folder,
        "scanned_files_count": scan_res.get("scanned_count", 0),
        "total_matched_files": len(matches),
        "extracted_keywords": search_kws[:12],
        "image_summary": image_summary,
        "matched_files": matches
    }, ensure_ascii=False)
