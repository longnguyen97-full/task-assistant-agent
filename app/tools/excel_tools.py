import os
import re
import json
from pathlib import Path
from datetime import datetime, date
from typing import Dict, Any, List, Optional
import openpyxl
from app.config import settings
from app.database import db_create_task

def tool_import_tasks_from_excel(file_name_or_path: str) -> str:
    """Đọc file Excel báo cáo tiến độ/kế hoạch tháng (.xlsx, .xls) hoặc CSV.
    Tự động nhận diện cấu trúc (cả dạng bảng thông thường lẫn bảng mẫu Monthly Report có checklist/status),
    bóc tách tên task, hạn chót (deadline), người phụ trách (assignee), trạng thái (status), blocker
    và import hàng loạt vào cơ sở dữ liệu SQLite để hiển thị trên Bảng Tasks (Kanban) và kích hoạt lịch nhắc việc.
    
    Args:
        file_name_or_path: Tên file (ví dụ: 'report_thang10.xlsx') hoặc đường dẫn file Excel.
    """
    # Find file path
    target_path = Path(file_name_or_path)
    if not target_path.exists():
        cand1 = settings.DATA_DIR / "docs" / file_name_or_path
        cand2 = settings.DATA_DIR / file_name_or_path
        if cand1.exists():
            target_path = cand1
        elif cand2.exists():
            target_path = cand2
        else:
            # Also try stripped filename
            clean_name = Path(file_name_or_path).name
            cand3 = settings.DATA_DIR / "docs" / clean_name
            cand4 = settings.DATA_DIR / clean_name
            if cand3.exists():
                target_path = cand3
            elif cand4.exists():
                target_path = cand4
            else:
                return json.dumps({
                    "status": "error",
                    "message": f"Không tìm thấy file '{file_name_or_path}' trong thư mục data/ hoặc data/docs/."
                }, ensure_ascii=False)

    try:
        wb = openpyxl.load_workbook(str(target_path), data_only=True)
    except Exception as e:
        return json.dumps({
            "status": "error",
            "message": f"Lỗi khi mở file Excel: {str(e)}"
        }, ensure_ascii=False)

    created_tasks = []
    skipped_rows = 0

    for sheetname in wb.sheetnames:
        sheet = wb[sheetname]
        rows = list(sheet.iter_rows(values_only=True))
        if not rows or len(rows) < 2:
            continue

        # Check if this sheet is a Monthly Report Template with status columns (SPECIFICATIONS, ON GOING, DONE...)
        is_matrix_template = False
        header_row_idx = -1
        author_from_file = "Developer"

        for r_idx, r in enumerate(rows[:5]):
            line_str = " ".join([str(c or "").strip() for c in r if c])
            if "name:" in line_str.lower():
                m = re.search(r"name:\s*([^|,\n]+?)(?:title:|$)", line_str, re.IGNORECASE)
                if m:
                    author_from_file = m.group(1).strip()

            headers_lower = [str(c or "").lower().strip() for c in r if c]
            if any("specifications" in h or "specification" in h for h in headers_lower):
                is_matrix_template = True
                header_row_idx = r_idx
                break

        if is_matrix_template and header_row_idx != -1:
            # 1. Parse Status Matrix Template (e.g. Monthly Report Template)
            current_section = ""
            raw_matrix_items = []

            for r in rows[header_row_idx + 1:]:
                vals = [c for c in r if c is not None and str(c).strip()]
                if not vals:
                    continue

                col0 = str(r[0] or "").strip() if len(r) > 0 else ""
                col1 = str(r[1] or "").strip() if len(r) > 1 else ""
                col2 = str(r[2] or "").strip() if len(r) > 2 else ""

                # Check if this is a section header (like 'KIG Website', 'SIS / SVIS Website', 'Plan')
                if (len(vals) == 1 or not col0.isdigit()) and not col1 and not col2:
                    current_section = str(vals[0]).strip()
                    continue

                if col0.isdigit() or col1 or col2:
                    item = col1
                    spec = col2
                    if not item and not spec:
                        skipped_rows += 1
                        continue

                    # Determine status by searching for 'X' in columns
                    status = "TODO"
                    for col_idx in range(3, min(len(r), 8)):
                        val_str = str(r[col_idx] or "").strip().upper()
                        if "X" in val_str or "1" in val_str or "YES" in val_str:
                            if col_idx >= 6:
                                status = "DONE"
                            elif col_idx == 5:
                                status = "IN_PROGRESS"  # Seeking approval
                            elif col_idx == 4:
                                status = "IN_PROGRESS"
                            elif col_idx == 3:
                                status = "TODO"
                            break

                    blocker = "Chờ phê duyệt (Seeking approval)" if (len(r) > 5 and str(r[5] or "").strip().upper() == "X") else ""
                    raw_matrix_items.append({
                        "section": current_section,
                        "item": item,
                        "spec": spec,
                        "status": status,
                        "blocker": blocker
                    })

            # --- PHÂN LOẠI THEO TẦN SUẤT LẶP LẠI (Recurring / Routine Tasks) ---
            # Gom các tác vụ vận hành định kỳ (Hosting, Backup, SSL, Posting) thành các Thẻ Vận Hành Tổng Hợp
            # để không làm rác bảng Kanban với hàng chục thẻ lặp lại cho từng website.
            routine_groups = {
                "daily_hosting": {
                    "title": "[Ops - Hàng Ngày] Giám sát Hosting, Server & Database các Website",
                    "priority": "HIGH",
                    "tags": "ops, recurring, daily, hosting",
                    "items": []
                },
                "weekly_backup": {
                    "title": "[Ops - Hàng Tuần] Bảo trì & Sao lưu (Backup) định kỳ các Website",
                    "priority": "HIGH",
                    "tags": "ops, recurring, weekly, backup",
                    "items": []
                },
                "monthly_ssl": {
                    "title": "[Ops - Hàng Tháng] Kiểm tra & Xác thực chứng chỉ bảo mật SSL",
                    "priority": "HIGH",
                    "tags": "ops, recurring, monthly, ssl",
                    "items": []
                },
                "content_posting": {
                    "title": "[Ops - Định kỳ] Đăng tải Newsletter, Học liệu & Nội dung Website",
                    "priority": "MEDIUM",
                    "tags": "ops, recurring, content",
                    "items": []
                }
            }

            projects_and_initiatives = []

            for entry in raw_matrix_items:
                sec = entry["section"].lower()
                it = entry["item"].lower()
                sp = entry["spec"].lower()
                combined = f"{sec} {it} {sp}"

                # Kiểm tra công việc dự án / phát triển / nghiên cứu thực thụ (không gom)
                is_project = any(k in combined for k in [
                    "development", "phát triển", "nghiên cứu", "học tập", "research",
                    "feature", "tính năng", "support", "hỗ trợ", "plan", "kế hoạch",
                    "fix", "bug", "sửa lỗi", "thiết kế", "design", "triển khai"
                ]) and not any(k in it for k in ["hosting", "maintain", "backup", "ssl", "posting"])

                if is_project:
                    projects_and_initiatives.append(entry)
                elif any(k in combined for k in ["hosting", "server", "máy chủ", "database", "hạ tầng", "infra"]):
                    routine_groups["daily_hosting"]["items"].append(entry)
                elif any(k in combined for k in ["backup", "sao lưu", "maintain", "bảo trì"]):
                    routine_groups["weekly_backup"]["items"].append(entry)
                elif any(k in combined for k in ["ssl", "chứng chỉ", "xác thực ssl", "security"]):
                    routine_groups["monthly_ssl"]["items"].append(entry)
                elif any(k in combined for k in ["posting", "newsletter", "upload", "đăng bài", "bài viết", "học liệu"]):
                    routine_groups["content_posting"]["items"].append(entry)
                else:
                    projects_and_initiatives.append(entry)

            # 1.1 Tạo các Thẻ Vận Hành Định Kỳ đã gom nhóm
            for g_key, g_info in routine_groups.items():
                items = g_info["items"]
                if not items:
                    continue

                if all(x["status"] == "DONE" for x in items):
                    agg_status = "DONE"
                elif any(x["status"] == "IN_PROGRESS" for x in items):
                    agg_status = "IN_PROGRESS"
                else:
                    agg_status = "TODO"

                desc_lines = [
                    f"**Nhóm công việc vận hành lặp lại** được tổng hợp tự động từ file báo cáo.",
                    f"- **Phụ trách chính:** {author_from_file}",
                    f"- **Tần suất thực hiện:** {g_info['title'].split(']')[0].replace('[Ops - ', '')}",
                    f"- **Tổng số hệ thống giám sát:** {len(items)}",
                    "\n**Danh sách kiểm tra (Checklist) chi tiết:**"
                ]
                for x in items:
                    icon = "✅" if x["status"] == "DONE" else ("⏳" if x["status"] == "IN_PROGRESS" else "⬜")
                    desc_lines.append(f"- {icon} **{x['section']}**: {x['item']} - {x['spec']} (`{x['status']}`)")

                created = db_create_task(
                    title=g_info["title"],
                    description="\n".join(desc_lines),
                    status=agg_status,
                    priority=g_info["priority"],
                    assignee=author_from_file,
                    deadline="",
                    blocker_reason="",
                    tags=g_info["tags"]
                )
                created_tasks.append(created)

            # 1.2 Tạo các Thẻ Dự Án / Nghiên Cứu riêng biệt (Không gom nhóm)
            for entry in projects_and_initiatives:
                sec = entry["section"]
                it = entry["item"]
                sp = entry["spec"]
                full_title = f"[{sec}] {it}: {sp}" if sec else f"{it}: {sp}"
                if not sp:
                    full_title = f"[{sec}] {it}" if sec else it

                priority = "HIGH" if "development" in full_title.lower() or "ai" in full_title.lower() else "MEDIUM"
                tag_type = "development" if "development" in full_title.lower() else ("research" if any(k in full_title.lower() for k in ["nghiên cứu", "học tập"]) else "project")

                created = db_create_task(
                    title=full_title[:120],
                    description=f"Công việc dự án từ {target_path.name} (Sheet: {sheetname}).\nPhụ trách: {author_from_file}.\nChi tiết: {sp or it}",
                    status=entry["status"],
                    priority=priority,
                    assignee=author_from_file,
                    deadline="",
                    blocker_reason=entry["blocker"],
                    tags=f"project, {tag_type}, {sec.lower().replace(' ', '-') if sec else 'general'}"
                )
                created_tasks.append(created)

        else:
            # 2. Parse Standard Columnar Excel Table
            headers = [str(c or "").lower().strip() for c in rows[0]]
            idx_title = -1
            idx_assignee = -1
            idx_deadline = -1
            idx_status = -1
            idx_priority = -1
            idx_blocker = -1
            idx_desc = -1

            for i, h in enumerate(headers):
                if any(k in h for k in ["tên task", "tên công việc", "nội dung", "công việc", "task", "title", "action"]):
                    if idx_title == -1: idx_title = i
                elif any(k in h for k in ["người phụ trách", "phụ trách", "assignee", "người làm", "dev"]):
                    idx_assignee = i
                elif any(k in h for k in ["deadline", "hạn chót", "thời hạn", "ngày hoàn thành", "target date", "due date"]):
                    idx_deadline = i
                elif any(k in h for k in ["trạng thái", "status", "tiến độ"]):
                    idx_status = i
                elif any(k in h for k in ["mức độ", "ưu tiên", "priority", "độ ưu tiên"]):
                    idx_priority = i
                elif any(k in h for k in ["blocker", "khó khăn", "vấn đề", "nghẽn", "rủi ro"]):
                    idx_blocker = i
                elif any(k in h for k in ["mô tả", "ghi chú", "note", "description", "chi tiết"]):
                    idx_desc = i

            if idx_title == -1:
                idx_title = 0

            for row in rows[1:]:
                if not any(row):
                    continue
                
                raw_title = row[idx_title] if idx_title < len(row) else None
                if not raw_title or str(raw_title).strip() == "":
                    skipped_rows += 1
                    continue

                title = str(raw_title).strip()
                assignee = str(row[idx_assignee]).strip() if (idx_assignee != -1 and idx_assignee < len(row) and row[idx_assignee]) else "Developer"

                deadline = ""
                if idx_deadline != -1 and idx_deadline < len(row) and row[idx_deadline]:
                    val = row[idx_deadline]
                    if isinstance(val, (datetime, date)):
                        deadline = val.strftime("%Y-%m-%d")
                    else:
                        deadline = str(val).strip()[:10]

                status = "TODO"
                if idx_status != -1 and idx_status < len(row) and row[idx_status]:
                    st_lower = str(row[idx_status]).lower()
                    if any(k in st_lower for k in ["done", "xong", "hoàn thành", "finished"]):
                        status = "DONE"
                    elif any(k in st_lower for k in ["block", "nghẽn", "kẹt", "pending"]):
                        status = "BLOCKED"
                    elif any(k in st_lower for k in ["progress", "đang làm", "doing", "in progress"]):
                        status = "IN_PROGRESS"

                priority = "MEDIUM"
                if idx_priority != -1 and idx_priority < len(row) and row[idx_priority]:
                    pr_lower = str(row[idx_priority]).lower()
                    if any(k in pr_lower for k in ["urgent", "khẩn", "gấp", "cao nhất"]):
                        priority = "URGENT"
                    elif any(k in pr_lower for k in ["high", "cao"]):
                        priority = "HIGH"
                    elif any(k in pr_lower for k in ["low", "thấp"]):
                        priority = "LOW"

                blocker_reason = str(row[idx_blocker]).strip() if (idx_blocker != -1 and idx_blocker < len(row) and row[idx_blocker]) else ""
                if blocker_reason and status != "DONE":
                    status = "BLOCKED"

                description = str(row[idx_desc]).strip() if (idx_desc != -1 and idx_desc < len(row) and row[idx_desc]) else ""

                created = db_create_task(
                    title=title,
                    description=description,
                    status=status,
                    priority=priority,
                    assignee=assignee,
                    deadline=deadline,
                    blocker_reason=blocker_reason,
                    tags=f"excel-import, {sheetname.lower()}"
                )
                created_tasks.append(created)

    return json.dumps({
        "status": "success",
        "file": target_path.name,
        "total_created_tasks": len(created_tasks),
        "skipped_rows": skipped_rows,
        "sample_created_tasks": [
            {
                "id": t["id"],
                "title": t["title"],
                "status": t["status"],
                "deadline": t.get("deadline", ""),
                "priority": t["priority"],
                "assignee": t.get("assignee", "Developer")
            } for t in created_tasks[:10]
        ],
        "message": f"Đã bóc tách thành công {len(created_tasks)} tasks từ file Excel và lưu vào cơ sở dữ liệu. Worker định kỳ sẽ tự động theo dõi hạn chót để nhắc nhở."
    }, ensure_ascii=False)
