import sys
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

import uvicorn
from pathlib import Path
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.database import init_db
from app.rag.vector_store import index_documents
from app.scheduler.worker import start_scheduler
from app.api.routes import api_router

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup and shutdown events."""
    print("🚀 [1/3] Khởi tạo SQLite Database...")
    init_db()

    print("📚 [2/3] Kiểm tra & Lập chỉ mục ChromaDB Vector Store...")
    try:
        rag_res = index_documents()
        print(f"   ✓ ChromaDB: {rag_res.get('message', 'Ready')}")
    except Exception as e:
        print(f"   ⚠️ ChromaDB warning: {e}")

    print("⏰ [3/3] Khởi chạy APScheduler Worker (Quét nhắc việc 9h sáng)...")
    try:
        start_scheduler()
        print("   ✓ Worker đang chạy ngầm.")
    except Exception as e:
        print(f"   ⚠️ APScheduler warning: {e}")

    print("\n" + "="*60)
    print("🤖 Task Assistant Agent đã sẵn sàng!")
    print(f"🌐 Truy cập giao diện Web UI tại: http://{settings.HOST}:{settings.PORT}")
    print("="*60 + "\n")
    yield
    print("🛑 Hệ thống đang dừng...")

app = FastAPI(
    title="Task Assistant Agent",
    description="Trợ lý ảo hỗ trợ Developer: Note Logging, RAG tra cứu Timeline & Specs, AI Planning và Email Dispatcher.",
    version="1.0.0",
    lifespan=lifespan
)

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API Router
app.include_router(api_router)

# Mount Static Files
static_dir = settings.BASE_DIR / "app" / "web" / "static"
if static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

# Templates
templates_dir = settings.BASE_DIR / "app" / "web" / "templates"
templates = Jinja2Templates(directory=str(templates_dir))
templates.env.auto_reload = True

# No-Cache Middleware for Static Assets during development
@app.middleware("http")
async def add_no_cache_headers(request: Request, call_next):
    response = await call_next(request)
    if request.url.path.startswith("/static/"):
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
    return response

# Serve Index HTML at Root with Cache Buster
import time

@app.get("/", response_class=HTMLResponse)
async def serve_index(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={"v": int(time.time())}
    )

def main():
    """Run the Task Assistant server."""
    uvicorn.run(
        "main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=False
    )

if __name__ == "__main__":
    main()
