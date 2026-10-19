import json
from app.rag.vector_store import query_rag

def tool_query_project_docs(query: str, top_k: int = 4) -> str:
    """Tra cứu tài liệu dự án, tiến độ (timeline.md), đặc tả kỹ thuật (specs.md), và các quy định qua Vector Database (RAG).
    
    Args:
        query: Câu hỏi hoặc từ khóa cần tra cứu trong tài liệu
        top_k: Số lượng đoạn trích phù hợp nhất cần lấy (mặc định 4)
    """
    results = query_rag(query, top_k=top_k)
    if not results:
        return json.dumps({
            "message": "Không tìm thấy nội dung phù hợp trong tài liệu dự án.",
            "results": []
        }, ensure_ascii=False)

    formatted = []
    for r in results:
        formatted.append({
            "source": r["source"],
            "relevance": r["relevance_score"],
            "content": r["content"]
        })

    return json.dumps({
        "query": query,
        "matches_count": len(formatted),
        "results": formatted
    }, ensure_ascii=False)
