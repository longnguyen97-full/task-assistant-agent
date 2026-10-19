"""
Storage Tier Evaluation & Recommendation Engine.
Analyzes tasks, priority levels, deadlines, change requests, and chat interactions
to evaluate which projects are more active/prioritized and propose Hot/Cold tier migrations.
CRITICAL PRINCIPLE: Recommends/proposes only, NEVER auto-switches without developer confirmation.
"""
import json
import re
from datetime import datetime, date
from typing import Dict, Any, List, Optional

from app.database import (
    db_get_all_projects,
    db_get_project_by_id,
    db_get_project_by_name,
    db_update_project_storage_tier,
    db_get_all_tasks,
    db_get_chat_history,
    db_get_change_notes
)

def evaluate_project_storage_tiers() -> Dict[str, Any]:
    """Phân tích toàn diện tình hình các dự án qua Task, Deadline, Blocker và Chat history
    để đưa ra đề xuất chuyển vùng Hot/Cold Storage hợp lý (chỉ đề xuất, không tự chuyển)."""
    projects = db_get_all_projects()
    tasks = db_get_all_tasks()
    chat_history = db_get_chat_history(limit=80)
    change_notes = db_get_change_notes(limit=100)

    # Lọc nội dung chat gần đây
    recent_chat_texts = [
        (c.get("content") or "").lower()
        for c in chat_history
        if c.get("role") in ("user", "assistant")
    ]

    proposals: List[Dict[str, Any]] = []
    stable_projects: List[Dict[str, Any]] = []

    today_str = date.today().isoformat()

    for proj in projects:
        p_id = proj["id"]
        p_name = proj["name"]
        p_name_lower = p_name.lower()
        current_tier = (proj.get("storage_tier") or "HOT").strip().upper()
        status = proj.get("status") or "IN_PROGRESS"

        # 1. Tìm các task liên quan đến dự án này
        related_tasks = []
        for t in tasks:
            w_name = (t.get("website_name") or "").strip().lower()
            title = (t.get("title") or "").strip().lower()
            tags = (t.get("tags") or "").strip().lower()

            is_match = False
            if w_name and (w_name == p_name_lower):
                is_match = True
            elif f"[{p_name_lower}]" in title:
                is_match = True
            elif p_name_lower in tags:
                is_match = True
            elif w_name and len(w_name) >= 4 and (w_name in p_name_lower or p_name_lower in w_name):
                is_match = True

            if is_match:
                related_tasks.append(t)

        total_tasks = len(related_tasks)
        active_tasks = [t for t in related_tasks if t.get("status") in ("TODO", "IN_PROGRESS", "BLOCKED")]
        done_tasks = [t for t in related_tasks if t.get("status") == "DONE"]
        urgent_tasks = [t for t in active_tasks if t.get("priority") in ("HIGH", "URGENT")]
        blocked_tasks = [t for t in active_tasks if t.get("status") == "BLOCKED"]
        
        # Overdue tasks
        overdue_tasks = []
        for t in active_tasks:
            dline = t.get("deadline") or ""
            if dline and dline < today_str:
                overdue_tasks.append(t)

        # 2. Đếm số lần dự án được thảo luận trong chat gần đây
        keywords = [k for k in re.split(r"[\s/\-_,]+", p_name_lower) if len(k) >= 3 and k not in ("với", "cho", "của", "các", "web", "hệ", "thống")]
        chat_mention_count = 0
        for text in recent_chat_texts:
            if p_name_lower in text:
                chat_mention_count += 1
            elif keywords and sum(1 for kw in keywords if kw in text) >= max(1, len(keywords) // 2):
                chat_mention_count += 1

        # 3. Đếm change notes gần đây
        proj_notes = [
            n for n in change_notes 
            if n.get("project_id") == p_id or (n.get("project_name") or "").lower() == p_name_lower
        ]

        metrics = {
            "total_tasks": total_tasks,
            "active_tasks_count": len(active_tasks),
            "done_tasks_count": len(done_tasks),
            "urgent_tasks_count": len(urgent_tasks),
            "blocked_tasks_count": len(blocked_tasks),
            "overdue_tasks_count": len(overdue_tasks),
            "chat_mentions": chat_mention_count,
            "change_notes_count": len(proj_notes)
        }

        # 4. Thuật toán đánh giá phân vùng (Proposal Engine)
        suggested_tier = current_tier
        reason = ""
        urgency = "LOW"

        if current_tier == "COLD":
            # Đang ở COLD, kiểm tra xem có nên đẩy lên HOT không
            if len(active_tasks) > 0 or chat_mention_count >= 1 or len(urgent_tasks) > 0 or len(proj_notes) > 0:
                suggested_tier = "HOT"
                urgency = "HIGH" if (len(urgent_tasks) > 0 or len(blocked_tasks) > 0) else "MEDIUM"
                reasons = []
                if len(active_tasks) > 0:
                    reasons.append(f"có {len(active_tasks)} task đang triển khai ({len(urgent_tasks)} task mức High/Urgent)")
                if len(blocked_tasks) > 0:
                    reasons.append(f"{len(blocked_tasks)} task đang bị Blocked cần gỡ vướng")
                if chat_mention_count > 0:
                    reasons.append(f"được thảo luận {chat_mention_count} lần trong chat gần đây")
                if len(proj_notes) > 0:
                    reasons.append(f"có {len(proj_notes)} yêu cầu thay đổi mới ghi nhận")
                
                reason = f"Dự án đang nằm ở COLD Storage nhưng {', '.join(reasons)}. Cần đưa lên Hot Storage để Developer theo dõi và xử lý ưu tiên."

        elif current_tier == "HOT":
            # Đang ở HOT, kiểm tra xem có nên chuyển vào COLD để tinh gọn không
            if total_tasks > 0 and len(active_tasks) == 0:
                suggested_tier = "COLD"
                urgency = "MEDIUM"
                reason = f"Toàn bộ {total_tasks} công việc của dự án đã hoàn tất (100% DONE), không có task nào đang chạy dở. Đề xuất chuyển vào Cold Storage để đóng băng lưu trữ và giải phóng bảng theo dõi chính."
            elif status in ("COMPLETED", "ON_HOLD") and len(active_tasks) == 0:
                suggested_tier = "COLD"
                urgency = "LOW"
                reason = f"Dự án có trạng thái '{status}' và không còn task nào cần thực hiện. Đề xuất chuyển vào Cold Storage để tinh gọn bảng dự án chính."
            elif total_tasks == 0 and chat_mention_count < 3:
                suggested_tier = "COLD"
                urgency = "LOW"
                reason = "Dự án hiện chưa có task hành động nào trên Kanban và ít phát sinh trao đổi trong chat. Đề xuất chuyển vào Cold Storage tạm thời cho đến khi có kế hoạch triển khai cụ thể."

        item = {
            "project_id": p_id,
            "project_name": p_name,
            "current_tier": current_tier,
            "suggested_tier": suggested_tier,
            "status": status,
            "urgency": urgency,
            "reason": reason,
            "metrics": metrics
        }

        if suggested_tier != current_tier:
            proposals.append(item)
        else:
            if current_tier == "HOT":
                item["reason"] = f"Dự án đang chạy tích cực ({len(active_tasks)} task active, {len(urgent_tasks)} task gấp). Duy trì ở Hot Storage."
            else:
                item["reason"] = "Dự án đang lưu trữ ổn định, không có công việc phát sinh mới."
            stable_projects.append(item)

    # Tạo bản báo cáo Markdown thân thiện cho Agent & UI
    markdown_lines = []
    markdown_lines.append("### 🧠 AI Storage Advisor - Đánh Giá & Đề Xuất Phân Vùng Dự Án")
    markdown_lines.append("")
    markdown_lines.append("> ⚠️ **LƯU Ý:** Đây là **đề xuất tư vấn** dựa trên dữ liệu công việc (Tasks) và lịch sử trao đổi (Chat). Hệ thống **tuyệt đối KHÔNG tự ý chuyển vùng** mà để Developer toàn quyền quyết định.")
    markdown_lines.append("")

    if proposals:
        markdown_lines.append(f"#### 🎯 Phát hiện **{len(proposals)}** dự án cần đề xuất chuyển vùng:")
        for p in proposals:
            icon_cur = "🔥 Hot" if p["current_tier"] == "HOT" else "❄️ Cold"
            icon_sug = "🔥 Hot Storage" if p["suggested_tier"] == "HOT" else "❄️ Cold Storage"
            m = p["metrics"]
            markdown_lines.append(f"- **{p['project_name']}** (Hiện tại: `{icon_cur}` ➔ Đề xuất: **`{icon_sug}`** | Mức độ: `{p['urgency']}`)")
            markdown_lines.append(f"  - *Lý do:* {p['reason']}")
            markdown_lines.append(f"  - *Dữ liệu:* {m['active_tasks_count']} active tasks, {m['urgent_tasks_count']} urgent, {m['done_tasks_count']} done, {m['chat_mentions']} chat mentions.")
            markdown_lines.append(f"  - 👉 *Hành động:* Bạn có thể bấm nút chuyển trên tab Quản Lý Dự Án hoặc yêu cầu tôi: `Chuyển dự án {p['project_name']} sang {p['suggested_tier']}`.")
            markdown_lines.append("")
    else:
        markdown_lines.append("✅ **Tất cả các dự án hiện tại đều đang ở đúng phân vùng tối ưu!**")
        markdown_lines.append("Không có dự án nào có dấu hiệu bị bỏ quên ở Cold hoặc gây nhiễu ở Hot.")
        markdown_lines.append("")

    markdown_lines.append("#### 📊 Trạng thái phân vùng hiện tại:")
    hot_cnt = sum(1 for p in projects if (p.get("storage_tier") or "HOT").upper() == "HOT")
    cold_cnt = sum(1 for p in projects if (p.get("storage_tier") or "HOT").upper() == "COLD")
    markdown_lines.append(f"- **🔥 Hot Storage:** {hot_cnt} dự án")
    markdown_lines.append(f"- **❄️ Cold Storage:** {cold_cnt} dự án")

    return {
        "status": "success",
        "total_projects": len(projects),
        "hot_count": hot_cnt,
        "cold_count": cold_cnt,
        "proposals_count": len(proposals),
        "proposals": proposals,
        "stable_projects": stable_projects,
        "summary_markdown": "\n".join(markdown_lines)
    }

def tool_set_project_storage_tier(project_name_or_id: str, storage_tier: str) -> Dict[str, Any]:
    """Chuyển đổi phân vùng lưu trữ cho dự án khi Developer có yêu cầu hoặc xác nhận cụ thể."""
    tier = (storage_tier or "").strip().upper()
    if tier not in ("HOT", "COLD"):
        return {
            "status": "error",
            "message": f"Phân vùng '{storage_tier}' không hợp lệ. Chỉ chấp nhận 'HOT' hoặc 'COLD'."
        }

    proj = None
    if str(project_name_or_id).isdigit():
        proj = db_get_project_by_id(int(project_name_or_id))
    if not proj:
        proj = db_get_project_by_name(str(project_name_or_id))

    if not proj:
        return {
            "status": "error",
            "message": f"Không tìm thấy dự án nào tương ứng với '{project_name_or_id}'."
        }

    updated = db_update_project_storage_tier(proj["id"], tier)
    if not updated:
        return {
            "status": "error",
            "message": f"Không thể cập nhật phân vùng cho dự án #{proj['id']}."
        }

    tier_label = "🔥 Hot Storage (Đang triển khai / Nóng)" if tier == "HOT" else "❄️ Cold Storage (Lưu trữ đóng băng / Lạnh)"
    return {
        "status": "success",
        "message": f"Đã chuyển dự án '{updated['name']}' sang phân vùng **{tier_label}** thành công theo yêu cầu của bạn!",
        "project": updated
    }
