import json
from datetime import datetime, date
from typing import Dict, Any, List
from app.database import db_get_all_tasks, db_create_task
from app.rag.vector_store import query_rag

def tool_analyze_project_plan_and_risks() -> str:
    """Đối chiếu tiến độ thực tế (các tasks trong SQLite) với kế hoạch & tiến độ (RAG trên Timeline & Specs).
    Tự động phân tích nguy cơ trễ hạn (deadline risk), đánh giá các task bị nghẽn (blocker), và đề xuất kế hoạch phân bổ công việc.
    """
    all_tasks = db_get_all_tasks()
    
    # 1. Fetch relevant timeline information via RAG
    timeline_chunks = query_rag("Milestone Sprint tiến độ kế hoạch deadline thời hạn", top_k=3)
    timeline_context = "\n---\n".join([c["content"] for c in timeline_chunks]) if timeline_chunks else "Không có dữ liệu timeline."

    # 2. Analyze Task distribution
    stats = {
        "total": len(all_tasks),
        "TODO": 0,
        "IN_PROGRESS": 0,
        "BLOCKED": 0,
        "DONE": 0,
        "overdue": [],
        "due_soon": [],
        "blockers": []
    }

    today = date.today()

    for t in all_tasks:
        status = t["status"]
        if status in stats:
            stats[status] += 1

        deadline_str = t.get("deadline", "")
        if deadline_str:
            try:
                # Support YYYY-MM-DD
                d_date = datetime.strptime(deadline_str[:10], "%Y-%m-%d").date()
                days_left = (d_date - today).days
                if status != "DONE":
                    if days_left < 0:
                        stats["overdue"].append({
                            "id": t["id"],
                            "title": t["title"],
                            "deadline": deadline_str,
                            "days_overdue": abs(days_left),
                            "priority": t["priority"]
                        })
                    elif days_left <= 3:
                        stats["due_soon"].append({
                            "id": t["id"],
                            "title": t["title"],
                            "deadline": deadline_str,
                            "days_left": days_left,
                            "priority": t["priority"]
                        })
            except Exception:
                pass

        if status == "BLOCKED":
            stats["blockers"].append({
                "id": t["id"],
                "title": t["title"],
                "blocker_reason": t.get("blocker_reason") or "Chưa rõ nguyên nhân",
                "priority": t["priority"],
                "assignee": t.get("assignee", "Developer")
            })

    # Calculate completion rate
    active_count = stats["TODO"] + stats["IN_PROGRESS"] + stats["BLOCKED"]
    completion_rate = round((stats["DONE"] / stats["total"] * 100) if stats["total"] > 0 else 0, 1)

    # Risk level determination
    risk_level = "LOW"
    risk_reasons = []
    if len(stats["overdue"]) > 0:
        risk_level = "HIGH"
        risk_reasons.append(f"Có {len(stats['overdue'])} task đã quá hạn deadline.")
    if len(stats["blockers"]) > 0:
        if risk_level != "HIGH":
            risk_level = "MEDIUM"
        risk_reasons.append(f"Có {len(stats['blockers'])} task đang bị nghẽn (BLOCKED).")

    return json.dumps({
        "timestamp": datetime.now().isoformat(),
        "completion_rate_percent": completion_rate,
        "summary": {
            "total_tasks": stats["total"],
            "todo": stats["TODO"],
            "in_progress": stats["IN_PROGRESS"],
            "blocked": stats["BLOCKED"],
            "done": stats["DONE"]
        },
        "risk_assessment": {
            "overall_risk": risk_level,
            "reasons": risk_reasons,
            "overdue_tasks": stats["overdue"],
            "due_soon_tasks": stats["due_soon"],
            "blocked_tasks": stats["blockers"]
        },
        "timeline_reference_from_rag": timeline_context
    }, ensure_ascii=False)

def generate_new_project_plan_and_timeline(project_name: str, requirements: str, target_deadline: str = "") -> Dict[str, Any]:
    """Tự động phân rã yêu cầu dự án mới thành Bản Kế Hoạch Thực Hiện + Bảng Timeline (WBS & Milestones) để nộp sếp / khách hàng.
    Chia rõ ràng 4 giai đoạn cụ thể: từ ngày nào tới ngày nào, thành viên thực hiện, nội dung thực hiện, và mục tiêu.
    """
    from datetime import timedelta
    from app.db_ops import db_create_project
    
    today_date = date.today()
    start_str = today_date.strftime("%Y-%m-%d")
    
    # Tính toán target date
    target_date = None
    if target_deadline:
        for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%Y/%m/%d"):
            try:
                target_date = datetime.strptime(target_deadline[:10], fmt).date()
                break
            except Exception:
                pass
                
    if not target_date or target_date <= today_date:
        target_date = today_date + timedelta(days=21)
    
    total_days = max(4, (target_date - today_date).days)
    d1 = max(1, round(total_days * 0.15))
    d2 = max(2, round(total_days * 0.35))
    d3 = max(1, round(total_days * 0.30))
    d4 = max(1, total_days - (d1 + d2 + d3))
    
    p1_start = today_date
    p1_end = p1_start + timedelta(days=max(0, d1 - 1))
    
    p2_start = p1_end + timedelta(days=1)
    p2_end = p2_start + timedelta(days=max(0, d2 - 1))
    
    p3_start = p2_end + timedelta(days=1)
    p3_end = p3_start + timedelta(days=max(0, d3 - 1))
    
    p4_start = p3_end + timedelta(days=1)
    p4_end = target_date

    phases = [
        {
            "phase_num": 1,
            "name": "Giai đoạn 1: Khảo sát, Phân tích Specs & Thiết kế Kiến trúc",
            "start_date": p1_start.strftime("%Y-%m-%d"),
            "end_date": p1_end.strftime("%Y-%m-%d"),
            "duration_days": d1,
            "assignees": "Tech Lead, Solution Architect, Business Analyst",
            "tasks": ["Phân tích specs & yêu cầu hệ thống", "Thiết kế database & mockup giao diện UI/UX"],
            "objective": "Hoàn thiện tài liệu kiến trúc, specs và wireframe UI/UX được phê duyệt"
        },
        {
            "phase_num": 2,
            "name": "Giai đoạn 2: Phát triển Backend & Cơ sở dữ liệu Cốt lõi",
            "start_date": p2_start.strftime("%Y-%m-%d"),
            "end_date": p2_end.strftime("%Y-%m-%d"),
            "duration_days": d2,
            "assignees": "Backend Developer, Database Administrator",
            "tasks": ["Xây dựng API, endpoints & cơ sở dữ liệu", "Tích hợp nghiệp vụ bảo mật & logic cốt lõi"],
            "objective": "Hoàn thiện toàn bộ API endpoints, migration DB và vượt qua Unit Tests"
        },
        {
            "phase_num": 3,
            "name": "Giai đoạn 3: Phát triển Giao diện Frontend & Tích hợp Hệ thống",
            "start_date": p3_start.strftime("%Y-%m-%d"),
            "end_date": p3_end.strftime("%Y-%m-%d"),
            "duration_days": d3,
            "assignees": "Frontend Developer, UI/UX Designer",
            "tasks": ["Xây dựng UI/UX theo thiết kế responsive", "Kết nối frontend với backend API và xử lý dữ liệu"],
            "objective": "Giao diện hoàn chỉnh, tương tác mượt mà, kết nối trơn tru với API trên môi trường staging"
        },
        {
            "phase_num": 4,
            "name": "Giai đoạn 4: Kiểm thử UAT, Tối ưu & Triển khai Production",
            "start_date": p4_start.strftime("%Y-%m-%d"),
            "end_date": p4_end.strftime("%Y-%m-%d"),
            "duration_days": d4,
            "assignees": "QA/Tester, DevOps, Project Manager",
            "tasks": ["Chạy kiểm thử chức năng, UAT người dùng", "Deploy production, cấu hình domain, SSL & bàn giao"],
            "objective": "Nghiệm thu toàn diện, triển khai production an toàn và bàn giao đầy đủ cho khách hàng/sếp"
        }
    ]

    plan_md = f"# 📋 KẾ HOẠCH THỰC HIỆN DỰ ÁN: {project_name.upper()}\n\n"
    plan_md += f"**Thời gian dự kiến:** Từ `{p1_start.strftime('%d/%m/%Y')}` đến `{p4_end.strftime('%d/%m/%Y')}` (Tổng `{total_days}` ngày)\n"
    plan_md += f"**Hạn chót mục tiêu:** `{p4_end.strftime('%d/%m/%Y')}`\n\n"
    plan_md += f"**Mô tả yêu cầu chức năng:**\n{requirements}\n\n"
    plan_md += "## 📅 PHÂN KỲ THỰC HIỆN & TIMELINE (WBS 4 GIAI ĐOẠN):\n\n"
    plan_md += "| Giai đoạn | Khoảng thời gian | Thành viên thực hiện | Mục tiêu trọng tâm |\n"
    plan_md += "| :--- | :--- | :--- | :--- |\n"
    for p in phases:
        plan_md += f"| **{p['name']}** | {p['start_date']} đến {p['end_date']} | {p['assignees']} | {p['objective']} |\n"

    plan_md += "\n### 📌 CHI TIẾT TỪNG GIAI ĐOẠN:\n"
    for p in phases:
        plan_md += f"\n#### {p['name']}\n"
        plan_md += f"- **Thời gian:** Từ ngày `{p['start_date']}` đến ngày `{p['end_date']}` ({p['duration_days']} ngày)\n"
        plan_md += f"- **Thành viên thực hiện:** {p['assignees']}\n"
        plan_md += f"- **Nội dung công việc:** {', '.join(p['tasks'])}\n"
        plan_md += f"- **Mục tiêu đạt được:** {p['objective']}\n"

    # Save to projects table with phases_json
    project_record = db_create_project(
        name=project_name,
        timeline_doc=plan_md,
        plan_summary=f"Kế hoạch 4 giai đoạn ({p1_start.strftime('%d/%m')} - {p4_end.strftime('%d/%m/%Y')})",
        status="PLANNING",
        start_date=start_str,
        target_deadline=p4_end.strftime("%Y-%m-%d"),
        phases_json=json.dumps(phases, ensure_ascii=False)
    )

    # Automatically create initial tasks on Kanban with each phase's deadline
    created_tasks = []
    for p in phases:
        for t_title in p["tasks"]:
            t = db_create_task(
                title=f"[{project_name}] {t_title}",
                description=f"Thuộc {p['name']} của dự án {project_name}.\nThời hạn giai đoạn: Từ {p['start_date']} đến {p['end_date']}.\nPhụ trách: {p['assignees']}.\nMục tiêu: {p['objective']}.\nYêu cầu: {requirements[:200]}",
                status="TODO",
                priority="HIGH" if p["phase_num"] in (1, 4) else "MEDIUM",
                assignee=p["assignees"].split(",")[0].strip(),
                deadline=p["end_date"],
                tags=f"project-new, {project_name.lower().replace(' ', '-')}, giai-doan-{p['phase_num']}",
                source_type="PROJECT_NEW",
                website_name=project_name
            )
            created_tasks.append(t)

    return {
        "success": True,
        "project": project_record,
        "plan_markdown": plan_md,
        "phases": phases,
        "total_created_tasks": len(created_tasks)
    }

def record_project_change_request(project_name: str, title: str, content: str, author: str = "Developer") -> Dict[str, Any]:
    """Ghi nhận ý thay đổi trong cuộc họp dự án mà TUYỆT ĐỐI KHÔNG CHỈNH SỬA TIMELINE GỐC."""
    from app.db_ops import db_add_change_note
    note = db_add_change_note(
        project_id=None,
        project_name=project_name,
        title=title,
        content=content,
        author=author
    )
    return {
        "success": True,
        "change_note": note,
        "message": f"Đã ghi nhận Change Request cho dự án '{project_name}'. Timeline gốc được bảo toàn 100%."
    }
