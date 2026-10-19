# 🤖 Task Assistant Agent - Production-Ready Single-Agent & RAG System

[![Python](https://img.shields.io/badge/Python-3.12%2B-3776AB?style=flat&logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115%2B-009688?style=flat&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![LangChain](https://img.shields.io/badge/LangChain%20%2F%20LangGraph-Agentic%20Core-1C3C3C?style=flat&logo=langchain&logoColor=white)](https://python.langchain.com/)
[![ChromaDB](https://img.shields.io/badge/ChromaDB-Vector%20Store-FF6F00?style=flat)](https://www.trychroma.com/)
[![SQLite WAL](https://img.shields.io/badge/SQLite-WAL%20Mode-003B57?style=flat&logo=sqlite&logoColor=white)](https://www.sqlite.org/wal.html)
[![Package Manager](https://img.shields.io/badge/uv-Astral-DE5FE9?style=flat)](https://github.com/astral-sh/uv)
[![Code Standard](https://img.shields.io/badge/Code%20Standard-%3C%20500%20Lines%2FFile-brightgreen?style=flat)]()

Hệ thống **AI Agent (Single-Agent Architecture)** thông minh được thiết kế và triển khai nhằm giải quyết trọn vẹn luồng công việc hằng ngày của Developer & Quản lý dự án: tự động hóa tiếp nhận chỉ đạo công việc đa thức (Text, Email/Teams, Ảnh chụp màn hình lỗi, Specs), bóc tách dữ liệu có cấu trúc (Structured Extraction), quản lý tiến độ Kanban (State Management), lập kế hoạch WBS 4 giai đoạn chuẩn mực, bảo toàn mốc thời gian gốc (Timeline Preservation), tra cứu kho tri thức kỹ thuật nội bộ (RAG Retrieval) và xuất báo cáo công việc tháng định kỳ (.xlsx) chỉ với 1 click.

Dự án được xây dựng bám sát tiêu chuẩn phần mềm production: phân tầng rõ ràng giữa **Agentic Workflow**, **Backend Service (FastAPI)**, **Vector Database (ChromaDB)** và **Relational Database (SQLite WAL mode)**, tuân thủ nguyên tắc thiết kế **100% file mã nguồn < 500 dòng code**.

---

## 🎯 Bối Cảnh Nghiệp Vụ & Bài Toán Giải Quyết

Trong thực tế vận hành công việc kỹ thuật hằng ngày, kỹ sư phần mềm thường đối mặt với các vấn đề:
1. **Quá tải thông tin từ nhiều kênh:** Nhận task phân mảnh qua Teams, Email, hình ảnh chụp nhanh giao diện hoặc yêu cầu trao đổi miệng.
2. **Mất thời gian lập kế hoạch dự án:** Khi nhận dự án mới, cần ngay bản phân rã công việc (WBS) gồm 4 giai đoạn với mốc thời gian, nhân sự, mục tiêu và deliverables rõ ràng.
3. **Thay đổi phạm vi làm vỡ timeline (Scope Creep):** Khi dự án đang chạy có yêu cầu thay đổi (Change Request), kỹ sư cần ghi nhận chính xác nội dung thay đổi mà **không được tùy tiện xê dịch timeline gốc** đã cam kết với ban quản lý.
4. **Phân tán tài liệu kỹ thuật:** Specs dự án, tài liệu kiến trúc dùng chung nằm rải rác, gây khó khăn cho việc tra cứu nhanh khi đang code.
5. **Áp lực báo cáo cuối tháng:** Cuối mỗi tháng phải ngồi lục lại lịch sử chat, email, commit để viết báo cáo KPI và tiến độ nộp cấp quản lý.

👉 **Task Assistant Agent** đóng vai trò là một trợ lý thông minh thường trực, tự động xử lý toàn bộ các khâu trên thông qua hội thoại tự nhiên và giao diện điều khiển tập trung.

---

## 🧠 Kiến Trúc Hệ Thống (Single-Agent ReAct Architecture)

Agent hoạt động theo mô hình **ReAct (Reasoning + Acting)** lặp tuần tự, sử dụng LLM làm bộ điều khiển trung tâm để phân tích ngữ cảnh, lựa chọn công cụ thực thi (Tool Calling) và duy trì ngữ cảnh trạng thái:

```text
                                [ MULTI-MODAL INPUT ]
               Chat tự nhiên | Email/Teams | Ảnh chụp lỗi | Specs PDF/MD
                                          │
                                          ▼
                ┌──────────────────────────────────────────────────┐
                │        AGENTIC CORE CONTROLLER (FastAPI)         │
                │  - Google Gemini Engine (Flash / Pro)            │
                │  - Context Engineering & Dynamic Few-shot Prompt │
                │  - ReAct Reasoning Loop:                         │
                │    [Thought] ➔ [Action (Tool)] ➔ [Observation]   │
                └─────────────────────────┬────────────────────────┘
                                          │ Tool Calling
         ┌──────────────────┬─────────────┴───────┬──────────────────┐
         ▼                  ▼                     ▼                  ▼
┌─────────────────┐ ┌───────────────┐ ┌─────────────────┐ ┌──────────────────┐
│  Task Extractor │ │  WBS Planner  │ │  Change Logger  │ │   RAG Retriever  │
│  (Pydantic Zero-│ │  (4-Phase WBS │ │  (Scope Change, │ │   (Dense Vector  │
│   Click Parse)  │ │   Generator)  │ │  Preserve Time) │ │    ChromaDB)     │
└────────┬────────┘ └───────┬───────┘ └────────┬────────┘ └────────┬─────────┘
         │                  │                  │                   │
         ▼                  ▼                  ▼                   │
 ┌────────────────────────────────────────────────────────┐        │
 │              RELATIONAL DATABASE (SQLite)              │        │
 │  - Journal Mode: WAL (Write-Ahead Logging)             │        │
 │  - Busy Timeout: 30s (Concurrency Safe)                │        │
 │  - Tables: tasks, projects, project_phases, notes      │        │
 └──────────────────────────┬─────────────────────────────┘        │
                            │                                      ▼
                            ▼                     ┌──────────────────────────┐
                 ┌────────────────────┐           │ VECTOR STORE (ChromaDB)  │
                 │   Report Engine    │           │ - Recursive Text Splitter│
                 │ (OpenPyXL Export)  │           │ - Multilingual Embeddings│
                 │  .xlsx Doanh Nghiệp│           │ - Metadata Filtering     │
                 └────────────────────┘           └──────────────────────────┘
```

---

## 🚀 Điểm Nhấn Kỹ Thuật (Key Technical Highlights)

### 1. Agentic Workflow & ReAct Pattern
* **Single-Agent Decision Maker:** Sử dụng vòng lặp **ReAct** (Thought – Action – Observation) để giải quyết các yêu cầu phức tạp từ người dùng mà không cần can thiệp thủ công.
* **Tool Calling & Function Calling:** Đóng gói nghiệp vụ thành các công cụ chuẩn (`create_task`, `plan_wbs`, `query_docs`, `log_change_request`, `export_monthly_report`), cho phép Agent chủ động kích hoạt dựa trên intent của câu lệnh.
* **Structured Output:** Ép kiểu phản hồi của mô hình thành dữ liệu có cấu trúc (Pydantic / JSON Schema) với các trường định danh rõ ràng: mức độ ưu tiên (`LOW`, `MEDIUM`, `HIGH`, `URGENT`), deadline, tags phân loại, danh sách deliverables.
* **Human-in-the-Loop & Validation:** Cung cấp cơ chế xác nhận an toàn trước các hành động nhạy cảm (như xóa task hàng loạt hoặc cập nhật trạng thái quan trọng).

### 2. Retrieval-Augmented Generation (RAG) & Semantic Search
* **Vector Store Integration:** Tích hợp **ChromaDB** phục vụ lưu trữ embeddings và vector indexing cho tài liệu dự án (`.pdf`, `.md`, `.txt`).
* **Multilingual Semantic Retrieval:** Hỗ trợ nhúng ngữ nghĩa chuyên sâu tiếng Việt và thuật ngữ kỹ thuật, tối ưu hóa quá trình tìm kiếm đoạn văn bản liên quan.
* **Context Construction:** Tự động chunking văn bản, lọc nhiễu và bơm thông tin ngữ cảnh chính xác vào system prompt, giảm thiểu tối đa hiện tượng ảo giác (Hallucination) khi trả lời specs kỹ thuật.

### 3. State Management & Data Persistence
* **Hybrid Storage Architecture:**
  * **Relational State (SQLite WAL Mode):** Quản lý trạng thái tasks, projects, phases, change requests với chế độ `journal_mode=WAL` và `busy_timeout=30s` chống lock khi đọc/ghi đồng thời.
  * **Vector State (ChromaDB):** Quản lý tri thức ngữ nghĩa không cấu trúc.
* **Timeline Preservation Logic:** Cơ chế nghiệp vụ ghi nhận **Change Request** vào nhật ký riêng biệt để làm căn cứ đánh giá năng suất, **bảo toàn 100% mốc timeline gốc** đã cam kết ban đầu.

### 4. Production Engineering & Software Design
* **Clean & Modular Architecture:** Mã nguồn được tách lớp rõ ràng (Agent Core, REST API Routes, RAG Layer, Background Schedulers) với quy tắc nghiêm ngặt: **100% file mã nguồn < 500 dòng code**.
* **Background Worker:** Sử dụng **APScheduler** chạy nền ngầm định kỳ quét task quá hạn (Overdue) và cảnh báo nút thắt cổ chai (Blockers).
* **Modern Tooling:** Quản lý môi trường và gói dependencies bằng **`uv`** theo chuẩn **PEP 621**, tối ưu hóa tốc độ build và khả năng tái lập môi trường.

---

## ✨ Các Phân Hệ Chức Năng Chính

| Phân hệ | Chức năng chính | Giá trị mang lại |
|---|---|---|
| **💬 Chat Tiếp Nhận & Zero-Click Task Extraction** | Tiếp nhận input tự nhiên qua text, email, ảnh chụp; tự động nhận diện intent, trích xuất thực thể và tạo task Kanban tự động. | Tiết kiệm 90% thời gian nhập liệu thủ công của developer. |
| **📋 Kanban Board State Management** | Bảng công việc 4 cột (`TODO` ➔ `IN PROGRESS` ➔ `BLOCKED` ➔ `DONE`) với bộ lọc nguồn việc, dự án, cảnh báo deadline trực quan và nút xóa task an toàn. | Trực quan hóa tiến độ công việc, dễ dàng kéo thả và theo dõi blocker. |
| **🚀 WBS 4-Phase Planner & Change Tracker** | Tự động lập kế hoạch 4 giai đoạn chuẩn (Specs ➔ Backend ➔ Frontend ➔ UAT) và ghi nhật ký yêu cầu thay đổi (Change Notes) mà không sửa timeline gốc. | Chuẩn hóa quy trình giao nộp kế hoạch dự án cho cấp trên. |
| **📚 Kho Tri Thức RAG** | Quản lý tập trung tài liệu dự án và tài liệu dùng chung; tải lên, xóa và tra cứu ngữ nghĩa tức thì qua vector search. | Agent nắm rõ specs chi tiết, trả lời câu hỏi nghiệp vụ chuẩn xác. |
| **📊 Business Report Engine** | Xuất báo cáo tổng kết tháng tự động ra định dạng Excel (`.xlsx`) chuẩn hóa KPI, danh mục công việc hoàn thành và Change Requests chỉ với 1 click. | Đến kỳ báo cáo chỉ cần bấm 1 nút là có file nộp sếp. |

---

## 🏗️ Ngăn Xếp Công Nghệ (Tech Stack)

| Thành phần | Công nghệ / Thư viện | Vai trò kỹ thuật |
| --- | --- | --- |
| **Agent Framework** | LangChain / LangGraph | Điều phối ReAct Loop, Tool Binding và State Context |
| **LLM Core** | Google Gemini (Flash / Pro) | Inference, Multimodal Vision, Function Calling & Structured Extraction |
| **Backend API** | FastAPI (Python 3.12+) | High-performance Asynchronous RESTful API Server |
| **Vector Database** | ChromaDB | Lưu trữ Vector Embeddings, Semantic Search RAG |
| **Relational Database** | SQLite (WAL Mode) | Quản lý bảng dữ liệu tasks, timeline, change logs |
| **Package Manager** | `uv` (Astral) | Quản lý virtualenv và dependencies chuẩn PEP 621 |
| **Task Scheduler** | APScheduler | Background cron worker quét task quá hạn và blocker |
| **Report Generation** | OpenPyXL | Tự động hóa kết xuất báo cáo Excel (.xlsx) chuẩn doanh nghiệp |
| **Frontend UI** | HTML5 / CSS / Vanilla JS | Giao diện Dark Glassmorphism, thiết kế module độc lập |

---

## 📁 Cấu Trúc Thư Mục Dự Án

```text
task-assistant-agent/
├── main.py                         # FastAPI App Entrypoint, Middlewares & Lifespan
├── pyproject.toml                  # Khai báo cấu hình Dependencies (UV / PEP 621)
├── .env.example                    # Template biến môi trường
├── README.md                       # Tài liệu kiến trúc toàn diện của hệ thống
├── app/
│   ├── config.py                   # Cấu hình biến môi trường, đường dẫn và system settings
│   ├── database.py                 # SQLite engine (WAL Mode), Schema definition & CRUD ops
│   ├── db_ops.py                   # Backward-compatibility alias layer
│   ├── models.py                   # Pydantic schemas cho API & Agent Structured Outputs
│   ├── agent/
│   │   ├── graph.py                # ReAct Agent Core Runner & Workflow Controller
│   │   ├── tools.py                # Tool Calling definitions (Task, RAG, Plan, Report)
│   │   ├── prompts.py              # Context Engineering, Few-shot & System Prompts
│   │   └── assistant.py            # Backward-compatibility alias layer
│   ├── api/
│   │   └── routes.py               # REST API Endpoints (CRUD Tasks, Projects, RAG, Export)
│   ├── rag/
│   │   ├── vector_store.py         # Text chunking, Embedding pipeline & ChromaDB indexing
│   │   └── document_loader.py      # Bộ trích xuất nội dung từ PDF, MD, TXT
│   ├── reports/
│   │   └── monthly_report.py       # Engine xử lý tạo báo cáo tháng (.xlsx)
│   ├── scheduler/
│   │   └── worker.py               # Background worker định kỳ quét blocker & overdue tasks
│   ├── tools/                      # Tool wrappers & helper modules
│   └── web/
│       ├── templates/              # Giao diện Jinja2 UI (modular tabs & dialogs)
│       └── static/                 # Stylesheets & Modular JS components (< 500 lines/file)
└── data/
    ├── task_assistant.db           # SQLite database file
    ├── chroma_db/                  # ChromaDB vector persistent directory
    └── docs/                       # Thư mục lưu trữ tài liệu kỹ thuật dự án
```

> [!NOTE]
> Tất cả các file mã nguồn trong dự án đều tuân thủ nghiêm ngặt quy tắc **không vượt quá 500 dòng code**, đảm bảo tính dễ đọc, dễ kiểm thử và bảo trì lâu dài.

---

## ⚙️ Cài Đặt & Khởi Chạy Nhanh

### 1. Yêu cầu hệ thống
* **Python 3.12+**
* Trình quản lý gói **`uv`** (khuyên dùng để đạt hiệu năng tối đa):

```powershell
# Cài đặt uv trên Windows (PowerShell)
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

```bash
# Cài đặt uv trên Linux / macOS
curl -LsSf https://astral.sh/uv/install.sh | sh
```

### 2. Cài đặt dependencies

```bash
uv sync
```

### 3. Thiết lập biến môi trường

Sao chép file mẫu:

```bash
cp .env.example .env
```

Điền API Key của bạn vào `.env`:

```env
GEMINI_API_KEY=your_gemini_api_key_here
GEMINI_MODEL=gemini-flash-latest
```

*(Lưu ý: Bạn cũng có thể mở trực tiếp bảng **Cài đặt** trên Web UI để nhập API Key bất cứ lúc nào).*

### 4. Khởi chạy ứng dụng

```bash
uv run python main.py
```

* Ứng dụng Web: **[http://127.0.0.1:8000](http://127.0.0.1:8000)**
* API Documentation (Swagger UI): **[http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)**

---

## 📡 Danh Mục API RESTful Chính

| Method | Endpoint | Mô tả chức năng |
|---|---|---|
| `POST` | `/api/chat` | Gửi prompt hội thoại, tài liệu hoặc ảnh chụp cho ReAct Agent xử lý |
| `GET` | `/api/tasks` | Lấy danh sách toàn bộ tasks kèm trạng thái và metadata |
| `POST` | `/api/tasks` | Tạo task mới thủ công |
| `PUT` | `/api/tasks/{id}` | Cập nhật thông tin / trạng thái task (`TODO`, `IN_PROGRESS`, `DONE`, `BLOCKED`) |
| `DELETE` | `/api/tasks/{id}` | Xóa một task cụ thể |
| `DELETE` | `/api/tasks/clear-all` | Xóa sạch toàn bộ task (yêu cầu xác nhận an toàn) |
| `GET` | `/api/projects` | Lấy danh sách dự án kèm 4 giai đoạn và chi tiết timeline |
| `POST` | `/api/projects` | Tạo dự án mới kèm phân bổ 4 giai đoạn WBS |
| `GET` | `/api/projects/change-notes` | Lấy danh sách nhật ký thay đổi phạm vi (Change Requests) |
| `POST` | `/api/projects/change-notes` | Ghi nhận yêu cầu thay đổi mới mà không can thiệp timeline gốc |
| `GET` | `/api/docs` | Lấy danh mục tài liệu đã được index vào ChromaDB |
| `POST` | `/api/docs/upload` | Tải lên tài liệu kỹ thuật mới (.pdf, .md, .txt) và tự động index |
| `DELETE` | `/api/docs/{id}` | Xóa tài liệu khỏi kho tri thức và vector database |
| `GET` | `/api/reports/monthly-excel` | Tải về file Excel (.xlsx) báo cáo KPI và công việc tháng tự động |
| `GET` | `/api/settings` | Lấy cấu hình runtime hiện tại của hệ thống |
| `POST` | `/api/settings` | Lưu cập nhật cấu hình API key, model và SMTP |

---

## 🧪 Kiểm Tra & Đảm Bảo Chất Lượng Code (Quality Assurance)

Dự án cung cấp kịch bản kiểm tra tự động tích hợp:

```powershell
# 1. Kiểm tra giới hạn số dòng code (< 500 lines/file)
uv run python -c "
import os
violations = []
for root, dirs, files in os.walk('.'):
    if any(p in root for p in ['.venv', '.git', '__pycache__']): continue
    for f in files:
        if f.endswith(('.py', '.js', '.css', '.html')):
            path = os.path.join(root, f)
            with open(path, 'r', encoding='utf-8', errors='ignore') as fp:
                c = len(fp.readlines())
                if c >= 500: violations.append((path, c))
if violations:
    print('Violations found:', violations)
else:
    print('✅ Tất cả file mã nguồn đều tuân thủ chuẩn < 500 dòng code!')
"

# 2. Kiểm tra tính toàn vẹn của các Python modules
uv run python -c "
import main, app.database, app.config, app.agent.graph, app.api.routes, app.reports.monthly_report
print('✅ Tất cả modules import thành công và sẵn sàng phục vụ!')
"
```

---

## 📈 Định Hướng Nâng Cấp (Future Roadmap)

* [ ] **Multi-Agent Collaboration:** Nâng cấp từ Single-Agent sang mạng lưới Multi-Agent (Supervisor, Planning Agent, Coding Agent, Reviewer Agent) bằng LangGraph.
* [ ] **Model Context Protocol (MCP):** Chuẩn hóa việc tích hợp công cụ thông qua giao thức MCP để kết nối an toàn với các hệ thống Git, Jira, Notion của doanh nghiệp.
* [ ] **LLM Observability & Evaluation:** Tích hợp Langfuse / OpenTelemetry để theo dõi độ trễ (latency), chi phí token (cost) và đánh giá độ chuẩn xác của Tool Calling (LLM-as-a-Judge).
* [ ] **Enterprise Vector & Data Store:** Hỗ trợ kết nối Qdrant / pgvector và PostgreSQL cho các môi trường triển khai quy mô lớn phân tán.

---

## 📄 Bản Quyền & Giấy Phép

Phát triển bởi đội ngũ kỹ sư và phục vụ cho mục đích tối ưu hóa năng suất làm việc của lập trình viên và nhà quản lý dự án. Phát hành dưới giấy phép mã nguồn mở MIT.# task-assistant-agent
