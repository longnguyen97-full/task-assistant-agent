import os
import requests
from typing import List, Dict, Any, Optional
from pathlib import Path
import chromadb
from chromadb.config import Settings as ChromaSettings
from chromadb.api.types import Documents, EmbeddingFunction, Embeddings
from app.config import settings
from app.rag.document_loader import load_all_documents, load_document
from app.database import (
    db_get_all_documents,
    db_get_document_by_filename,
    db_upsert_document,
    db_delete_document,
    db_get_all_projects
)

_client: Optional[chromadb.PersistentClient] = None
_collection = None
COLLECTION_NAME = "task_assistant_rag"

class GeminiEmbeddingFunction(EmbeddingFunction):
    """Google Gemini Multilingual Embedding (3072-dimensional vector).
    Cung cấp khả năng biểu diễn ngữ nghĩa tiếng Việt và đa ngôn ngữ với độ chính xác cao nhất."""
    def __init__(self, api_key: str, model_name: str = "models/gemini-embedding-001"):
        self.api_key = api_key
        self.model_name = model_name

    def __call__(self, input: Documents) -> Embeddings:
        if not input:
            return []
        embeddings = []
        batch_size = 20
        for i in range(0, len(input), batch_size):
            batch = input[i:i + batch_size]
            url = f"https://generativelanguage.googleapis.com/v1beta/{self.model_name}:batchEmbedContents?key={self.api_key}"
            requests_list = [
                {"model": self.model_name, "content": {"parts": [{"text": text}]}}
                for text in batch
            ]
            try:
                r = requests.post(url, json={"requests": requests_list}, timeout=30)
                if r.status_code == 200:
                    data = r.json()
                    for item in data.get("embeddings", []):
                        embeddings.append(item["values"])
                else:
                    raise RuntimeError(f"Google Gemini Embedding API error {r.status_code}: {r.text[:200]}")
            except Exception as e:
                print(f"Error in GeminiEmbeddingFunction batch: {e}")
                raise e
        return embeddings

def get_embedding_function() -> Optional[EmbeddingFunction]:
    """Trả về bộ nhúng tiếng Việt của Google nếu có API Key, ngược lại fallback về default."""
    if settings.GEMINI_API_KEY:
        try:
            return GeminiEmbeddingFunction(api_key=settings.GEMINI_API_KEY)
        except Exception as e:
            print(f"Warning: could not initialize GeminiEmbeddingFunction: {e}")
    return None

def get_chroma_client() -> chromadb.PersistentClient:
    global _client
    if _client is None:
        settings.ensure_directories()
        _client = chromadb.PersistentClient(
            path=str(settings.CHROMA_DIR),
            settings=ChromaSettings(anonymized_telemetry=False)
        )
    return _client

def get_rag_collection():
    global _collection
    client = get_chroma_client()
    ef = get_embedding_function()

    if _collection is not None:
        try:
            _collection.count()
            return _collection
        except Exception:
            _collection = None

    try:
        if ef is not None:
            _collection = client.get_or_create_collection(
                name=COLLECTION_NAME,
                embedding_function=ef,
                metadata={"hnsw:space": "cosine"}
            )
        else:
            _collection = client.get_or_create_collection(
                name=COLLECTION_NAME,
                metadata={"hnsw:space": "cosine"}
            )
    except Exception as e:
        # Nếu xung đột số chiều embedding giữa model cũ (384) và mới (3072), tái tạo collection
        if "dimension" in str(e).lower():
            try:
                client.delete_collection(COLLECTION_NAME)
            except Exception:
                pass
            if ef is not None:
                _collection = client.create_collection(
                    name=COLLECTION_NAME,
                    embedding_function=ef,
                    metadata={"hnsw:space": "cosine"}
                )
            else:
                _collection = client.create_collection(
                    name=COLLECTION_NAME,
                    metadata={"hnsw:space": "cosine"}
                )
        else:
            raise e

    return _collection

def index_documents(force_reindex: bool = False) -> Dict[str, Any]:
    """Lập chỉ mục toàn bộ tài liệu trong thư mục data/ vào ChromaDB với embedding đa ngôn ngữ."""
    global _collection
    client = get_chroma_client()

    if force_reindex:
        try:
            client.delete_collection(COLLECTION_NAME)
        except Exception:
            pass
        _collection = None

    collection = get_rag_collection()

    current_count = collection.count()
    if current_count > 0 and not force_reindex:
        return {
            "status": "already_indexed",
            "total_chunks": current_count,
            "message": f"Chỉ mục hiện có {current_count} chunks vector."
        }

    chunks = load_all_documents()
    if not chunks:
        return {
            "status": "empty",
            "total_chunks": 0,
            "message": "Không tìm thấy tài liệu nào trong thư mục data/."
        }

    ids = []
    documents = []
    metadatas = []

    # Cache doc records from SQLite
    db_docs = {d["filename"]: d for d in db_get_all_documents()}

    for idx, item in enumerate(chunks):
        doc_id = f"chunk_{idx}_{item['metadata']['source']}"
        src_name = item['metadata']['source']
        doc_meta = db_docs.get(src_name, {})
        item['metadata']['scope_type'] = doc_meta.get('scope_type', 'GENERAL')
        item['metadata']['project_name'] = doc_meta.get('project_name', '')
        ids.append(doc_id)
        documents.append(item["content"])
        metadatas.append(item["metadata"])

    # Batch add
    batch_size = 40
    for i in range(0, len(ids), batch_size):
        end = i + batch_size
        collection.add(
            ids=ids[i:end],
            documents=documents[i:end],
            metadatas=metadatas[i:end]
        )

    model_desc = "Google Gemini Multilingual (3072-dim)" if settings.GEMINI_API_KEY else "Chroma Default"
    return {
        "status": "success",
        "total_chunks": collection.count(),
        "indexed_files": list(set(item['metadata']['source'] for item in chunks)),
        "embedding_model": model_desc,
        "message": f"Đã lập chỉ mục thành công {collection.count()} chunks vào ChromaDB bằng {model_desc}."
    }

def add_single_document(file_path: Path, scope_type: str = "GENERAL", project_name: str = "") -> Dict[str, Any]:
    """Thêm tài liệu mới tải lên vào ChromaDB kèm metadata phân loại phạm vi."""
    collection = get_rag_collection()
    chunks = load_document(file_path)
    if not chunks:
        return {"status": "error", "message": "Không thể trích xuất nội dung từ file."}

    size_kb = round(file_path.stat().st_size / 1024, 1) if file_path.exists() else 0.0
    db_upsert_document(
        filename=file_path.name,
        file_path=str(file_path),
        scope_type=scope_type,
        project_name=project_name,
        size_kb=size_kb
    )

    ids = []
    documents = []
    metadatas = []

    base_count = collection.count()
    for idx, item in enumerate(chunks):
        doc_id = f"chunk_{base_count + idx}_{item['metadata']['source']}"
        item['metadata']['scope_type'] = scope_type.upper()
        item['metadata']['project_name'] = project_name
        ids.append(doc_id)
        documents.append(item["content"])
        metadatas.append(item["metadata"])

    collection.add(
        ids=ids,
        documents=documents,
        metadatas=metadatas
    )

    return {
        "status": "success",
        "added_chunks": len(chunks),
        "total_chunks": collection.count(),
        "filename": file_path.name,
        "scope_type": scope_type.upper(),
        "project_name": project_name
    }

def query_rag(query: str, top_k: int = 4) -> List[Dict[str, Any]]:
    """Truy vấn ChromaDB Vector Store kết hợp Hybrid Lexical + Semantic Search."""
    try:
        collection = get_rag_collection()
        if collection.count() == 0:
            index_documents(force_reindex=False)
            collection = get_rag_collection()

        count = collection.count()
        if count == 0:
            return []

        # Lấy pool ứng viên rộng hơn để rerank
        candidate_count = min(max(top_k * 3, 10), count)
        results = collection.query(
            query_texts=[query],
            n_results=candidate_count
        )

        matched_items = []
        if results and "documents" in results and results["documents"]:
            docs = results["documents"][0]
            metas = results["metadatas"][0] if "metadatas" in results else [{}] * len(docs)
            distances = results["distances"][0] if "distances" in results and results["distances"] else [0.0] * len(docs)

            query_clean = query.lower().strip()
            query_words = set(w for w in query_clean.split() if len(w) > 1)

            for doc, meta, dist in zip(docs, metas, distances):
                doc_lower = doc.lower()
                vec_score = max(0.0, 1.0 - (dist if dist is not None else 0.5))

                # Hybrid lexical match check
                exact_match = query_clean in doc_lower
                overlap_count = sum(1 for w in query_words if w in doc_lower)
                overlap_ratio = overlap_count / max(1, len(query_words))

                if exact_match:
                    # Tăng vọt độ khớp nếu trùng khớp chính xác 100% cụm từ
                    final_score = round(min(0.98, 0.50 + vec_score * 0.45), 4)
                else:
                    final_score = round(vec_score * 0.70 + overlap_ratio * 0.30, 4)

                matched_items.append({
                    "content": doc,
                    "source": meta.get("source", "Unknown"),
                    "chunk_index": meta.get("chunk_index", 0),
                    "relevance_score": final_score
                })

            # Sắp xếp giảm dần theo điểm số Hybrid
            matched_items.sort(key=lambda x: x["relevance_score"], reverse=True)

        return matched_items[:top_k]
    except Exception as e:
        print(f"Error querying RAG: {e}")
        return []

def get_rag_stats() -> Dict[str, Any]:
    """Trả về thống kê chỉ mục RAG và danh sách tài liệu kèm phân loại phạm vi (GENERAL / PROJECT)."""
    try:
        collection = get_rag_collection()
        total_chunks = collection.count()
    except Exception:
        total_chunks = 0

    # Retrieve docs from SQLite
    db_docs = {d["filename"]: d for d in db_get_all_documents()}
    files = []
    supported_exts = {".md", ".txt", ".pdf", ".xlsx", ".xls", ".csv"}

    def _process_file(f: Path, prefix: str = ""):
        if f.is_file() and f.suffix.lower() in supported_exts:
            fname = f.name
            d_record = db_docs.get(fname, {})
            scope = d_record.get("scope_type", "GENERAL")
            proj = d_record.get("project_name", "")
            if not d_record:
                size_kb = round(f.stat().st_size / 1024, 1)
                db_upsert_document(fname, str(f), scope, proj, size_kb)
            files.append({
                "name": f"{prefix}{fname}" if prefix else fname,
                "clean_name": fname,
                "size_kb": round(f.stat().st_size / 1024, 1),
                "modified": f.stat().st_mtime,
                "scope_type": scope,
                "project_name": proj
            })

    if settings.DATA_DIR.exists():
        for f in settings.DATA_DIR.glob("*"):
            _process_file(f)

    docs_sub = settings.DATA_DIR / "docs"
    if docs_sub.exists():
        for f in docs_sub.glob("*"):
            if not any(x["clean_name"] == f.name for x in files):
                _process_file(f, prefix="docs/")

    emb_name = "Google Gemini Multilingual (3072-dim)" if settings.GEMINI_API_KEY else "all-MiniLM-L6-v2 (Local)"
    all_projects = [p["name"] for p in db_get_all_projects()]

    return {
        "total_chunks": total_chunks,
        "files_count": len(files),
        "files": files,
        "projects": all_projects,
        "collection_name": COLLECTION_NAME,
        "embedding_model": emb_name
    }

def delete_document_file(filename: str) -> bool:
    """Xóa file tài liệu khỏi thư mục data và cập nhật lại chỉ mục RAG."""
    clean_name = os.path.basename(filename.replace("\\", "/"))
    deleted = False
    for candidate in [settings.DATA_DIR / "docs" / clean_name, settings.DATA_DIR / clean_name]:
        if candidate.exists() and candidate.is_file():
            candidate.unlink()
            deleted = True
    db_delete_document(clean_name)
    if deleted:
        index_documents(force_reindex=True)
    return deleted

