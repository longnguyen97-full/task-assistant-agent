import os
from pathlib import Path
from typing import List, Dict, Any
from pypdf import PdfReader
from app.config import settings

def chunk_text(text: str, chunk_size: int = 800, chunk_overlap: int = 150) -> List[str]:
    """Split text into overlapping chunks cleanly around paragraph or line boundaries."""
    if not text:
        return []
    
    # Simple, robust sliding window
    paragraphs = text.split("\n\n")
    chunks = []
    current_chunk = ""

    for para in paragraphs:
        para = para.strip()
        if not para:
            continue
        
        if len(current_chunk) + len(para) + 2 <= chunk_size:
            current_chunk = f"{current_chunk}\n\n{para}".strip()
        else:
            if current_chunk:
                chunks.append(current_chunk)
            # If paragraph itself is longer than chunk_size, split by sentences or lines
            if len(para) > chunk_size:
                lines = para.split("\n")
                sub_chunk = ""
                for line in lines:
                    if len(sub_chunk) + len(line) + 1 <= chunk_size:
                        sub_chunk = f"{sub_chunk}\n{line}".strip()
                    else:
                        if sub_chunk:
                            chunks.append(sub_chunk)
                        sub_chunk = line
                if sub_chunk:
                    current_chunk = sub_chunk
                else:
                    current_chunk = ""
            else:
                current_chunk = para

    if current_chunk:
        chunks.append(current_chunk)

    return chunks

def load_document(file_path: Path) -> List[Dict[str, Any]]:
    """Load and chunk a single file (.md, .txt, .pdf)."""
    if not file_path.exists():
        return []

    ext = file_path.suffix.lower()
    full_text = ""

    try:
        if ext in (".md", ".txt", ".markdown"):
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                full_text = f.read()
        elif ext == ".pdf":
            reader = PdfReader(str(file_path))
            pages_text = []
            for i, page in enumerate(reader.pages):
                text = page.extract_text() or ""
                pages_text.append(f"[Trang {i+1}]\n{text}")
            full_text = "\n\n".join(pages_text)
        elif ext in (".xlsx", ".xls"):
            import openpyxl
            wb = openpyxl.load_workbook(str(file_path), data_only=True)
            sheet_texts = []
            for sheetname in wb.sheetnames:
                sheet = wb[sheetname]
                rows = list(sheet.iter_rows(values_only=True))
                if not rows:
                    continue
                sheet_lines = [f"### Sheet: {sheetname}"]
                headers = [str(c or "").strip() for c in rows[0]]
                sheet_lines.append(" | ".join(headers))
                sheet_lines.append(" | ".join(["---"] * len(headers)))
                for row in rows[1:]:
                    if any(row):
                        vals = [str(c if c is not None else "").strip() for c in row]
                        sheet_lines.append(" | ".join(vals))
                sheet_texts.append("\n".join(sheet_lines))
            full_text = "\n\n".join(sheet_texts)
        elif ext == ".csv":
            import csv
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                reader = csv.reader(f)
                rows = list(reader)
                if rows:
                    csv_lines = [f"### File CSV: {file_path.name}"]
                    csv_lines.append(" | ".join(rows[0]))
                    csv_lines.append(" | ".join(["---"] * len(rows[0])))
                    for row in rows[1:]:
                        if any(row):
                            csv_lines.append(" | ".join(row))
                    full_text = "\n".join(csv_lines)
        else:
            # Fallback text read
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                full_text = f.read()
    except Exception as e:
        print(f"Error loading document {file_path}: {e}")
        return []

    chunks = chunk_text(full_text)
    doc_chunks = []
    for idx, chunk in enumerate(chunks):
        doc_chunks.append({
            "content": chunk,
            "metadata": {
                "source": str(file_path.name),
                "full_path": str(file_path),
                "chunk_index": idx,
                "total_chunks": len(chunks),
                "extension": ext
            }
        })
    return doc_chunks

def load_all_documents() -> List[Dict[str, Any]]:
    """Scan data directory and subdirectories for documents (.md, .txt, .pdf)."""
    docs_to_index = []
    supported_exts = {".md", ".txt", ".pdf", ".xlsx", ".xls", ".csv"}

    search_dirs = [settings.DATA_DIR]
    docs_sub = settings.DATA_DIR / "docs"
    if docs_sub.exists():
        search_dirs.append(docs_sub)

    seen_files = set()
    for directory in search_dirs:
        if not directory.exists():
            continue
        for item in directory.glob("*"):
            if item.is_file() and item.suffix.lower() in supported_exts:
                if item.name not in seen_files:
                    seen_files.add(item.name)
                    doc_chunks = load_document(item)
                    docs_to_index.extend(doc_chunks)

    return docs_to_index
