import io
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any, Optional
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from app.config import settings
from app.database import db_get_all_tasks, db_get_change_notes

def generate_monthly_report_excel(
    author_name: str = "NGUYEN HOANG BAO LONG",
    author_title: str = "Web Developer",
    month: Optional[int] = None,
    year: Optional[int] = None
) -> bytes:
    """Tạo hoặc cập nhật file Excel Monthly Report theo đúng format biểu mẫu doanh nghiệp.
    
    Tự động đồng bộ toàn bộ tasks từ SQLite Database, đánh dấu X vào các cột
    'NOT STARTED', 'ON GOING', 'DONE', phân nhóm theo các Website / Dự án và
    bổ sung nhật ký Change Requests.
    
    Returns:
        bytes: Nội dung file Excel nhị phân để tải xuống.
    """
    now = datetime.now()
    cur_month = month or now.month
    cur_year = year or now.year

    template_paths = [
        settings.DATA_DIR / "docs" / "Monthly Report_Template - October - 2026.xlsx",
        settings.DATA_DIR / "Monthly Report_Template - October - 2026.xlsx",
        settings.DATA_DIR / "docs" / "monthly_report_sample.xlsx",
        settings.DATA_DIR / "monthly_report_sample.xlsx",
    ]
    template_path = None
    for tp in template_paths:
        if tp.exists():
            template_path = tp
            break

    tasks = db_get_all_tasks()
    change_notes = db_get_change_notes(limit=30)

    if template_path:
        wb = openpyxl.load_workbook(str(template_path))
        sheet = wb.active
        
        # Update Month header and author if found
        for r in range(1, 4):
            for c in range(1, 8):
                val = str(sheet.cell(row=r, column=c).value or "")
                if "MONTHLY REPORT" in val:
                    sheet.cell(row=r, column=c).value = f"MONTHLY REPORT\nTháng {cur_month:02d} / {cur_year}"
                if "Name:" in val:
                    sheet.cell(row=r, column=c).value = f"Name:    {author_name}"

        col_spec = 3
        col_not_started = 4
        col_on_going = 5
        col_done = 7

        matched_task_ids = set()

        for row_idx in range(4, sheet.max_row + 1):
            spec_val = str(sheet.cell(row=row_idx, column=col_spec).value or "").strip().lower()
            item_val = str(sheet.cell(row=row_idx, column=2).value or "").strip().lower()
            
            if not spec_val and not item_val:
                continue

            for task in tasks:
                t_title = task["title"].lower().strip()
                t_desc = (task.get("description") or "").lower().strip()

                if (t_title and (t_title in spec_val or spec_val in t_title)) or \
                   (t_desc and (t_desc in spec_val or spec_val in t_desc)):
                    matched_task_ids.add(task["id"])
                    
                    sheet.cell(row=row_idx, column=col_not_started).value = None
                    sheet.cell(row=row_idx, column=col_on_going).value = None
                    sheet.cell(row=row_idx, column=col_done).value = None
                    
                    st = task["status"]
                    if st == "DONE":
                        sheet.cell(row=row_idx, column=col_done).value = "X"
                    elif st in ["IN_PROGRESS", "BLOCKED"]:
                        sheet.cell(row=row_idx, column=col_on_going).value = "X"
                    else:
                        sheet.cell(row=row_idx, column=col_not_started).value = "X"
                    break

        unmatched_tasks = [t for t in tasks if t["id"] not in matched_task_ids]
        if unmatched_tasks:
            start_r = sheet.max_row + 2
            sheet.cell(row=start_r, column=1).value = "Các công việc phát sinh & Dự án AI Agent"
            sheet.cell(row=start_r, column=1).font = Font(name="Arial", size=10, bold=True, color="FFFFFF")
            sheet.cell(row=start_r, column=1).fill = PatternFill(start_color="1F497D", end_color="1F497D", fill_type="solid")
            for c in range(2, 8):
                sheet.cell(row=start_r, column=c).fill = PatternFill(start_color="1F497D", end_color="1F497D", fill_type="solid")

            for idx, ut in enumerate(unmatched_tasks, start=1):
                cur_r = start_r + idx
                sheet.cell(row=cur_r, column=1).value = idx
                sheet.cell(row=cur_r, column=1).alignment = Alignment(horizontal="center")
                sheet.cell(row=cur_r, column=2).value = ut.get("tags") or "Development"
                sheet.cell(row=cur_r, column=3).value = ut["title"] + (f" ({ut['description']})" if ut.get("description") else "")
                
                st = ut["status"]
                if st == "DONE":
                    sheet.cell(row=cur_r, column=col_done).value = "X"
                    sheet.cell(row=cur_r, column=col_done).alignment = Alignment(horizontal="center")
                elif st in ["IN_PROGRESS", "BLOCKED"]:
                    sheet.cell(row=cur_r, column=col_on_going).value = "X"
                    sheet.cell(row=cur_r, column=col_on_going).alignment = Alignment(horizontal="center")
                else:
                    sheet.cell(row=cur_r, column=col_not_started).value = "X"
                    sheet.cell(row=cur_r, column=col_not_started).alignment = Alignment(horizontal="center")

        out = io.BytesIO()
        wb.save(out)
        return out.getvalue()

    else:
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = f"Report-{cur_month:02d}-{cur_year}"

        title_font = Font(name="Calibri", size=14, bold=True, color="1F4E79")
        subtitle_font = Font(name="Calibri", size=10, bold=True)
        header_font = Font(name="Calibri", size=10, bold=True, color="FFFFFF")
        header_fill = PatternFill(start_color="2F5597", end_color="2F5597", fill_type="solid")
        section_fill = PatternFill(start_color="D9E1F2", end_color="D9E1F2", fill_type="solid")
        center_align = Alignment(horizontal="center", vertical="center")
        border_thin = Border(
            left=Side(style='thin', color='BFBFBF'),
            right=Side(style='thin', color='BFBFBF'),
            top=Side(style='thin', color='BFBFBF'),
            bottom=Side(style='thin', color='BFBFBF')
        )

        ws.merge_cells("A1:G1")
        ws["A1"] = f"MONTHLY REPORT - THÁNG {cur_month:02d}/{cur_year}"
        ws["A1"].font = title_font
        ws["A1"].alignment = center_align

        ws["B2"] = f"Name: {author_name}"
        ws["B2"].font = subtitle_font
        ws["D2"] = f"Title: {author_title}"
        ws["D2"].font = subtitle_font

        headers = ["No.", "ITEM", "SPECIFICATIONS", "NOT STARTED", "ON GOING", "SEEKING APPROVAL", "DONE"]
        for col_idx, h in enumerate(headers, start=1):
            cell = ws.cell(row=3, column=col_idx, value=h)
            cell.font = header_font
            cell.fill = header_fill
            cell.alignment = center_align

        row_idx = 4
        sections: Dict[str, List[Dict[str, Any]]] = {}
        for t in tasks:
            tags = (t.get("tags") or "").lower()
            site = (t.get("website_name") or "").strip()
            if site:
                sec = site
            elif "kig" in tags:
                sec = "KIG Website"
            elif "sis" in tags or "svis" in tags:
                sec = "SIS / SVIS Website"
            elif "kik" in tags:
                sec = "KIK Website"
            elif "pegasus" in tags:
                sec = "Pegasus Website"
            elif "obv" in tags:
                sec = "OBV Website"
            else:
                sec = "Tasks & Development Projects"
            sections.setdefault(sec, []).append(t)

        for sec_name, sec_tasks in sections.items():
            ws.cell(row=row_idx, column=1, value=sec_name)
            ws.cell(row=row_idx, column=1).font = Font(name="Calibri", size=10, bold=True)
            for c in range(1, 8):
                ws.cell(row=row_idx, column=c).fill = section_fill
            row_idx += 1

            for no, t in enumerate(sec_tasks, start=1):
                ws.cell(row=row_idx, column=1, value=no).alignment = center_align
                ws.cell(row=row_idx, column=2, value="Development" if not t.get("tags") else t["tags"])
                ws.cell(row=row_idx, column=3, value=t["title"])

                st = t["status"]
                if st == "DONE":
                    ws.cell(row=row_idx, column=7, value="X").alignment = center_align
                elif st in ["IN_PROGRESS", "BLOCKED"]:
                    ws.cell(row=row_idx, column=5, value="X").alignment = center_align
                else:
                    ws.cell(row=row_idx, column=4, value="X").alignment = center_align

                for c in range(1, 8):
                    ws.cell(row=row_idx, column=c).border = border_thin
                row_idx += 1

        # Append Change Requests section if any exist
        if change_notes:
            row_idx += 1
            ws.cell(row=row_idx, column=1, value="Scope Change Requests (Preserved Timelines)")
            ws.cell(row=row_idx, column=1).font = Font(name="Calibri", size=10, bold=True, color="C00000")
            for c in range(1, 8):
                ws.cell(row=row_idx, column=c).fill = PatternFill(start_color="FCE4D6", end_color="FCE4D6", fill_type="solid")
            row_idx += 1

            for c_idx, cn in enumerate(change_notes, start=1):
                ws.cell(row=row_idx, column=1, value=f"CR-{c_idx}").alignment = center_align
                ws.cell(row=row_idx, column=2, value=cn.get("project_name", "Dự án"))
                ws.cell(row=row_idx, column=3, value=f"{cn.get('title')}: {cn.get('content')}")
                ws.cell(row=row_idx, column=5, value="X").alignment = center_align
                for c in range(1, 8):
                    ws.cell(row=row_idx, column=c).border = border_thin
                row_idx += 1

        ws.column_dimensions["A"].width = 8
        ws.column_dimensions["B"].width = 18
        ws.column_dimensions["C"].width = 45
        ws.column_dimensions["D"].width = 14
        ws.column_dimensions["E"].width = 12
        ws.column_dimensions["F"].width = 18
        ws.column_dimensions["G"].width = 10

        out = io.BytesIO()
        wb.save(out)
        return out.getvalue()
