"""
Heuristic Fallback Agent & Rule-Based Intent Engine.
Provides graceful zero-downtime fallback when LLM models are offline or encounter errors.
"""
import json
import re
from typing import Dict, Any, List, Optional

from app.database import (
    db_create_task,
    db_add_daily_note,
    db_delete_project,
    db_delete_project_by_name
)
from app.rag.vector_store import query_rag
from app.tools.planning_tools import (
    generate_new_project_plan_and_timeline,
    record_project_change_request
)

def synthesize_tool_summary(tool_calls: List[Dict[str, Any]], user_message: str) -> str:
    """Tạo tổng kết Markdown có cấu trúc từ danh sách tool đã gọi."""
    lines = ["Tôi đã xử lý các yêu cầu của bạn theo quy trình ReAct:"]
    for tc in tool_calls:
        name = tc["name"]
        res_str = tc.get("result", "")
        try:
            res_obj = json.loads(res_str) if isinstance(res_str, str) else res_str
        except Exception:
            res_obj = {}

        if name == "create_task":
            t = res_obj.get("task", {})
            lines.append(f"\n📌 **Đã tạo Task:** `#{t.get('id', '?')} {t.get('title', '')}` (Status: `{t.get('status', 'TODO')}`, Priority: `{t.get('priority', 'MEDIUM')}`).")
        elif name == "ingest_task_from_message":
            m = res_obj.get("summary_markdown", "")
            if m:
                lines.append(f"\n{m}")
            else:
                lines.append("\n✅ **Đã bóc tách tin nhắn thành task chuẩn trên Bảng Kanban.**")
        elif name == "plan_wbs":
            p = res_obj.get("project", {})
            cnt = res_obj.get("total_created_tasks", 0)
            lines.append(f"\n🚀 **Đã lập Kế hoạch WBS 4 Pha cho Dự án:** `{p.get('name', '')}`. Tự động sinh `{cnt}` tasks tương ứng theo từng mốc.")
        elif name == "log_change_request":
            lines.append(f"\n📝 **Đã ghi nhận Change Request:** {res_obj.get('message', 'Đã bảo toàn timeline gốc')}.")
        elif name == "delete_project":
            lines.append(f"\n🗑️ **Đã xóa dự án khỏi hệ thống:** {res_obj.get('message', 'Đã xóa dự án thành công')}.")
        elif name == "query_docs":
            matches = res_obj.get("results", [])
            if matches:
                top = matches[0]
                lines.append(f"\n📖 **Tra cứu tài liệu ({top.get('source')}):**\n{top.get('content')[:350]}...")
        elif name == "export_monthly_report":
            lines.append("\n📥 **Báo cáo tháng đã sẵn sàng:** Bấm vào nút **'Xuất Báo Cáo (.xlsx)'** trên thanh công cụ để tải file.")
        elif name == "record_daily_note":
            lines.append("\n📓 **Đã ghi nhận nhật ký làm việc (Daily Note) vào hệ thống.**")
        elif name == "dispatch_email":
            lines.append("\n✉️ **Đã chuyển email báo cáo vào Dispatcher Outbox.**")
        elif name == "evaluate_project_storage_tiers":
            m = res_obj.get("summary_markdown", "")
            if m:
                lines.append(f"\n{m}")
            else:
                lines.append("\n🧠 **Đã đánh giá các dự án và phân tích đề xuất phân vùng Hot/Cold Storage.**")
        elif name == "set_project_storage_tier":
            msg = res_obj.get("message", "Đã cập nhật phân vùng lưu trữ dự án.")
            lines.append(f"\n🏷️ **{msg}**")
        elif name == "search_design_files":
            status = res_obj.get("status")
            if status in ("blocked", "inaccessible"):
                lines.append(f"\n{res_obj.get('message', 'Không thể truy cập đường dẫn thư mục.')}")
            elif status == "success":
                matches = res_obj.get("matched_files", [])
                cnt = res_obj.get("total_matched_files", 0)
                scanned = res_obj.get("scanned_files_count", 0)
                folder = res_obj.get("folder_path", "")
                kws = ", ".join(res_obj.get("extracted_keywords", [])[:8])
                if matches:
                    lines.append(f"\n🎯 **Đã tìm thấy {cnt} tệp thiết kế phù hợp** (quét trong số {scanned} tệp .xd tại `{folder}`):")
                    if kws:
                        lines.append(f"🔍 *Từ khóa đặc trưng đã trích xuất & đối chiếu:* `{kws}`")
                    for m in matches:
                        ab_str = ", ".join(m.get("matched_artboards", [])) if m.get("matched_artboards") else "Toàn bộ tệp"
                        lines.append(f"\n- 📁 **Tệp tin:** `{m.get('file_name')}` ({m.get('file_size_mb')} MB - Sửa đổi: {m.get('last_modified')})")
                        lines.append(f"  - 📍 **Đường dẫn:** `{m.get('full_path')}`")
                        lines.append(f"  - 🎨 **Artboard chứa nội dung:** `{ab_str}`")
                        lines.append(f"  - 🏷️ **Từ khóa đã khớp ({m.get('matched_keywords_count')}):** `{', '.join(m.get('matched_keywords', []))}`")
                else:
                    lines.append(f"\nℹ️ Đã quét {scanned} tệp .xd trong `{folder}` nhưng không tìm thấy nội dung khớp với hình ảnh/từ khóa.")
            else:
                lines.append(f"\n⚠️ {res_obj.get('message', 'Lỗi khi quét tìm tệp thiết kế.')}")

    return "\n".join(lines)

import time

def heuristic_fallback_agent(user_message: str, author: str = "Developer", start_time: Optional[float] = None) -> Dict[str, Any]:
    """Bộ điều khiển dự phòng (Rule-based Intent Engine) khi chưa cấu hình LLM hoặc gặp sự cố mạng."""
    _t0 = start_time if start_time is not None else time.perf_counter()
    msg_lower = user_message.lower()
    tool_calls: List[Dict[str, Any]] = []
    response_parts: List[str] = []

    # 1. Monthly Report Intent
    if any(w in msg_lower for w in ["xuất báo cáo", "export", "báo cáo hàng tháng", "báo cáo tháng", "tự update file báo cáo", "đem nộp"]):
        response_parts.append(
            "🎯 **Quy trình Báo Cáo Tháng tự động 100%:**\n\n"
            "1. 📝 **Note hằng ngày:** Bất cứ khi nào có task mới, tiến độ hoặc blocker, bạn chỉ cần nhắn với tôi qua khung Chat (hoặc tạo trên Bảng Tasks). Hệ thống tự động ghi nhận vào SQLite.\n"
            "2. 🔄 **Tự động phân nhóm & đồng bộ:** Hệ thống liên tục cập nhật trạng thái các task (`DONE`, `ON GOING`, `NOT STARTED`) theo đúng phân mục Website/Dự án.\n"
            "3. 📥 **Xuất báo cáo 1-click:** Bạn bấm nút **'📥 Xuất Báo Cáo (.xlsx)'** trên Bảng Tasks (hoặc tải tại [đây](/api/tasks/export-monthly-report)) là có ngay file Excel đúng chuẩn mẫu công ty (có sẵn tên Tác giả `NGUYEN HOANG BAO LONG` và dấu tick `X`)!"
        )

    # 2. Teams / Email ingestion & Direct Actionable Task Extraction
    elif (
        ("nội dung:" in msg_lower or "nội dung :" in msg_lower or "clone" in msg_lower)
        and ("deadline" in msg_lower or "hạn chót" in msg_lower or "ngày" in msg_lower or "project" in msg_lower)
        and not any(w in msg_lower for w in ["họp dự án mới", "lập kế hoạch wbs", "kế hoạch 4 pha", "wbs nộp sếp", "timeline tổng thể", "họp thay đổi", "phát sinh", "thêm tính năng", "change request", "sửa specs"])
    ) or (any(kw in msg_lower for kw in ["kig", "sis", "svis", "kik", "pegasus", "obv"]) and any(w in msg_lower for w in ["clone", "giao", "lỗi", "sửa", "task", "yêu cầu", "cắt gọt", "nội dung"]) and not any(w in msg_lower for w in ["họp thay đổi", "phát sinh", "thêm tính năng", "change request"])):
        detected_project = ""
        p_match = re.search(r"(?:project|dự án|hệ thống)\s+([^,\.\n:]+)", user_message, re.IGNORECASE)
        if p_match:
            detected_project = p_match.group(1).strip()
        else:
            for kw, sname in [("svis", "SVIS Vạn Phúc"), ("sis", "SIS Website"), ("kig", "KIG Website"), ("kik", "KIK Website"), ("pegasus", "Pegasus Website"), ("obv", "OBV Website")]:
                if kw in msg_lower:
                    detected_project = sname
                    break
        if not detected_project:
            detected_project = "Website Dự Án"

        deadline_str = ""
        dl_match = re.search(r"(\d{1,2})[/-](\d{1,2})(?:[/-](\d{4}))?", user_message)
        if dl_match:
            try:
                from datetime import datetime
                d = int(dl_match.group(1))
                m = int(dl_match.group(2))
                y = int(dl_match.group(3)) if dl_match.group(3) else datetime.now().year
                deadline_str = f"{y:04d}-{m:02d}-{d:02d}"
            except Exception:
                pass

        content_candidate = ""
        c_match = re.search(r"(?:nội dung|yêu cầu)\s*:\s*([^,\.\n]+.*)", user_message, re.IGNORECASE)
        if c_match:
            content_candidate = c_match.group(1).strip()
        elif "clone" in msg_lower:
            cl_match = re.search(r"(clone\s+[^,\.\n]+(?:và\s+[^,\.\n]+)?)", user_message, re.IGNORECASE)
            content_candidate = cl_match.group(1).strip() if cl_match else "Clone website và cập nhật nội dung"
        else:
            content_candidate = user_message.strip()

        title = f"[{detected_project}] {content_candidate[0].upper() + content_candidate[1:] if content_candidate else 'Công việc mới'}"
        if len(title) > 90:
            title = title[:87] + "..."

        t = db_create_task(
            title=title,
            description=user_message,
            status="TODO",
            priority="HIGH" if ("gấp" in msg_lower or "khẩn" in msg_lower) else "MEDIUM",
            assignee=author,
            deadline=deadline_str,
            tags=f"clone, content, {detected_project.lower().replace(' ', '-')}",
            source_type="MANUAL",
            website_name=detected_project
        )
        db_add_daily_note(content=f"Ghi nhận công việc: {title} (Deadline: {deadline_str or 'Linh hoạt'})", author=author)

        tool_calls.append({
            "name": "create_task",
            "args": {"title": title, "deadline": deadline_str, "website_name": detected_project},
            "result": json.dumps({"status": "success", "task": t}, ensure_ascii=False)
        })

        response_parts.append(
            f"✅ **Đã tiếp nhận và tạo công việc trên Bảng Tasks (Kanban):**\n\n"
            f"- 📌 **Tên Task:** `{title}` (Task #{t['id']})\n"
            f"- 🌐 **Dự án / Website:** `{detected_project}`\n"
            f"- ⏰ **Hạn chót:** {f'`{deadline_str}`' if deadline_str else 'Trong tuần / Linh hoạt'}\n"
            f"- ⚡ **Độ ưu tiên:** `MEDIUM`\n"
            f"- 📋 **Trạng thái:** `TODO`\n\n"
            f"*(Hệ thống đã nhận diện đây là công việc trực tiếp và đưa thẳng lên Kanban để bạn theo dõi, không tạo các pha rườm rà).*"
        )

    # 3. Project Deletion
    elif any(w in msg_lower for w in ["xóa dự án", "xoá dự án", "delete project"]):
        p_match = re.search(r"(?:xóa dự án|xoá dự án|delete project)\s+([^,\.\n]+)", user_message, re.IGNORECASE)
        p_target = p_match.group(1).strip() if p_match else ""
        if p_target.isdigit():
            del_ok = db_delete_project(int(p_target))
        else:
            del_ok = db_delete_project_by_name(p_target)
        status_res = "success" if del_ok else "not_found"
        tool_calls.append({"name": "delete_project", "args": {"project_name_or_id": p_target}, "result": json.dumps({"status": status_res})})
        if del_ok:
            response_parts.append(f"🗑️ **Đã xóa dự án `{p_target}` thành công khỏi hệ thống!** Toàn bộ Change Requests liên quan đã được dọn dẹp.")
        else:
            response_parts.append(f"⚠️ **Không tìm thấy dự án `{p_target}`** trong cơ sở dữ liệu để xóa.")

    # 4. New Project Planning (WBS 4-phase)
    elif any(w in msg_lower for w in ["dự án mới", "kế hoạch dự án", "lập timeline", "wbs", "kế hoạch thực hiện"]):
        match = re.search(r"(?:dự án mới|kế hoạch dự án|dự án)\s+([^,\.\n]+)", user_message, re.IGNORECASE)
        p_name = match.group(1).strip() if match else "Dự Án Mới"
        p_res = generate_new_project_plan_and_timeline(project_name=p_name, requirements=user_message)
        tool_calls.append({"name": "plan_wbs", "args": {"project_name": p_name}, "result": json.dumps(p_res, ensure_ascii=False)})
        response_parts.append(f"🚀 **Đã phân rã Kế hoạch 4 giai đoạn (WBS) cho dự án `{p_name}`!**\nCác task của 4 giai đoạn đã được đưa lên Bảng Tasks.")

    # 5. Scope Change Request (Preserve original timeline)
    elif any(w in msg_lower for w in ["họp thay đổi", "phát sinh", "thêm tính năng", "change request", "sửa specs"]):
        cr_res = record_project_change_request(project_name="Dự Án Đang Chạy", title="Yêu cầu thay đổi từ cuộc họp", content=user_message, author=author)
        tool_calls.append({"name": "log_change_request", "args": {"title": "Thay đổi tính năng"}, "result": json.dumps(cr_res, ensure_ascii=False)})
        response_parts.append("📝 **Đã ghi nhận Change Request vào hệ thống!**\n⚠️ *Lưu ý: Mốc timeline gốc đã được bảo toàn 100% để đối chiếu.*")

    # 6. Search Design Files & Network Folders (.xd / Image / Keywords)
    elif any(w in msg_lower for w in ["tìm file", "kiếm file", "quét folder", "scan file", "file xd", "kiếm cái file", "tìm trong", "quét"]) or ("\\\\" in user_message and any(w in msg_lower for w in ["tìm", "kiếm", "quét", "hình", "ảnh", "xd"])):
        # Extract folder path with support for spaces and quotes
        target_folder = r"\\172.16.44.103\design$"
        q_match = re.search(r"[\"']([\\\/]{1,2}[^\"']+|[a-zA-Z]:\\[^\"']+)[\"']", user_message)
        if q_match:
            target_folder = q_match.group(1).strip()
        else:
            prefix_match = re.search(r"(?:trong|ở|tại|folder|đường dẫn)\s+([\\\/]{1,2}[^\n\r,\;]+|[a-zA-Z]:[\\\/][^\n\r,\;]+)", user_message, re.IGNORECASE)
            if prefix_match:
                cand = prefix_match.group(1).strip().rstrip(".,;")
                cand = re.split(r"\s+(?:có|chứa|để|với|tìm|file|hãy)\b", cand, flags=re.IGNORECASE)[0].strip()
                target_folder = cand
            else:
                m = re.search(r"([\\\/]{1,2}[^\n\r,\;]+|[a-zA-Z]:\\[^\n\r,\;]+)", user_message)
                if m:
                    cand = m.group(1).strip().rstrip(".,;")
                    cand = re.split(r"\s+(?:có|chứa|để|với|tìm|file|hãy)\b", cand, flags=re.IGNORECASE)[0].strip()
                    target_folder = cand
        img_match = re.search(r"\[Đính kèm(?:\s+hình\s+ảnh)?:\s*([^\]]+)\]", user_message)
        img_path = img_match.group(1).strip() if img_match else None

        extracted_kws = None
        if not img_path:
            kw_match = re.search(r"(?:có\s+chữ|từ\s+khóa|nội\s+dung|bảng)\s+([^,\.\n:]+(?:,\s*[^,\.\n:]+)*)", user_message, re.IGNORECASE)
            if kw_match:
                extracted_kws = kw_match.group(1).strip()
            else:
                quotes = re.findall(r"[\"']([^\"']+)[\"']", user_message)
                if quotes:
                    extracted_kws = ", ".join(quotes)
                else:
                    extracted_kws = "Break/Snack, Form Class, Lunch, Assembly"

        from app.tools.design_search_tools import tool_search_design_files_by_image_or_text
        tool_res = tool_search_design_files_by_image_or_text(
            folder_path=target_folder,
            image_path=img_path,
            keywords=extracted_kws
        )
        tool_calls.append({
            "name": "search_design_files",
            "args": {"folder_path": target_folder, "image_path": img_path},
            "result": tool_res
        })
        response_parts.append(synthesize_tool_summary(tool_calls, user_message))

    # 7. Daily Progress / Blocker Logging
    else:
        is_logging = any(w in msg_lower for w in ["hôm nay", "đã làm", "đang làm", "xong", "nghẽn", "blocker", "kẹt", "bị lỗi", "note", "task"])
        has_blocker = any(w in msg_lower for w in ["blocker", "nghẽn", "kẹt", "bị tắc", "chờ", "lỗi", "thiếu"])

        if is_logging or len(user_message) > 20:
            db_add_daily_note(content=user_message, author=author, summary=user_message[:100])
            tool_calls.append({"name": "record_daily_note", "args": {"content": user_message}, "result": json.dumps({"status": "recorded"})})

        if "xong" in msg_lower or "hoàn thành" in msg_lower:
            match = re.search(r"(?:làm xong|hoàn thành|xong)\s+([^,\.\n]+)", user_message, re.IGNORECASE)
            title = match.group(1).strip() if match else user_message[:40]
            t = db_create_task(title=title, description=user_message, status="DONE", priority="MEDIUM", assignee=author)
            tool_calls.append({"name": "create_task", "args": {"title": title, "status": "DONE"}, "result": json.dumps(t, ensure_ascii=False)})
            response_parts.append(f"✅ **Đã ghi nhận task hoàn thành:** `{title}` (Status: DONE)")

        elif has_blocker:
            match = re.search(r"(?:nghẽn|blocker|kẹt|chờ)\s+([^,\.\n]+)", user_message, re.IGNORECASE)
            reason = match.group(0).strip() if match else "Gặp trở ngại kỹ thuật cần giải quyết"
            title = f"Xử lý vấn đề: {reason[:40]}"
            t = db_create_task(title=title, description=user_message, status="BLOCKED", priority="HIGH", blocker_reason=reason, assignee=author)
            tool_calls.append({"name": "create_task", "args": {"title": title, "status": "BLOCKED"}, "result": json.dumps(t, ensure_ascii=False)})
            response_parts.append(f"⚠️ **Đã ghi nhận Blocker:** `{title}` (Status: BLOCKED)\n- **Lý do:** {reason}\n- Đã gắn nhãn ưu tiên HIGH.")

        elif any(w in msg_lower for w in ["nhắc tôi", "nhắc mình", "nhắc", "lên lịch", "cần làm", "tạo task"]):
            clean_title = re.sub(r"^(?:hãy\s+)?(?:nhắc\s+tôi|nhắc\s+mình|nhắc|lên\s+lịch|tạo\s+task|cần\s+làm)\s+", "", user_message, flags=re.IGNORECASE).strip()
            clean_title = clean_title[0].upper() + clean_title[1:] if clean_title else "Công việc mới"
            t = db_create_task(title=clean_title, description=user_message, status="TODO", priority="MEDIUM", assignee=author)
            tool_calls.append({"name": "create_task", "args": {"title": clean_title, "status": "TODO"}, "result": json.dumps(t, ensure_ascii=False)})
            response_parts.append(f"⏰ **Đã thiết lập công việc:** `{clean_title}` (Status: TODO)")

        if any(w in msg_lower for w in ["timeline", "tiến độ", "milestone", "specs", "đặc tả", "hạn chót", "deadline"]):
            rag_res = query_rag(user_message, top_k=2)
            tool_calls.append({"name": "query_docs", "args": {"query": user_message}, "result": json.dumps(rag_res, ensure_ascii=False)})
            if rag_res:
                response_parts.append(f"📖 **Tra cứu tài liệu ({rag_res[0].get('source')}):**\n\n{rag_res[0].get('content')[:450]}...")

    if not response_parts:
        response_parts.append("Tôi đã nhận được thông tin từ bạn và ghi nhận vào hệ thống.")

    tip = "\n\n💡 *Gợi ý: Bạn có thể chọn nhà cung cấp LLM (Ollama Qwen hoặc Google Gemini) trong mục Cài đặt (⚙️).*"
    latency_ms = round((time.perf_counter() - _t0) * 1000, 2)
    return {
        "role": "assistant",
        "content": "\n\n".join(response_parts) + tip,
        "tool_calls": tool_calls,
        "model": "rule-based-fallback",
        "metrics": {
            "latency_ms": latency_ms,
            "llm_latency_ms": 0.0,
            "tool_latency_ms": latency_ms,
            "input_tokens": 0,
            "output_tokens": 0,
            "total_tokens": 0,
            "cost_usd": 0.0,
            "provider": "rule-based",
            "model": "rule-based-fallback"
        }
    }

# Backward compatibility alias
_heuristic_fallback_agent = heuristic_fallback_agent
_synthesize_tool_summary = synthesize_tool_summary
