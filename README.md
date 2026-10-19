# 🤖 Task Assistant Agent - Production-Ready Single-Agent & RAG System

[![Python](https://img.shields.io/badge/Python-3.12%2B-3776AB?style=flat&logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115%2B-009688?style=flat&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![Ollama](https://img.shields.io/badge/Ollama-Qwen%202.5%20Local-black?style=flat&logo=ollama&logoColor=white)](https://ollama.com/)
[![Google Gemini](https://img.shields.io/badge/Google%20Gemini-Flash%20%2F%20Pro-4285F4?style=flat&logo=google&logoColor=white)](https://aistudio.google.com/)
[![LangChain](https://img.shields.io/badge/LangChain%20%2F%20LangGraph-Agentic%20Core-1C3C3C?style=flat&logo=langchain&logoColor=white)](https://python.langchain.com/)
[![ChromaDB](https://img.shields.io/badge/ChromaDB-Vector%20Store-FF6F00?style=flat)](https://www.trychroma.com/)
[![SQLite WAL](https://img.shields.io/badge/SQLite-WAL%20Mode-003B57?style=flat&logo=sqlite&logoColor=white)](https://www.sqlite.org/wal.html)
[![Package Manager](https://img.shields.io/badge/uv-Astral-DE5FE9?style=flat)](https://github.com/astral-sh/uv)

Hệ thống **AI Agent (Single-Agent Architecture)** thông minh được thiết kế và triển khai nhằm giải quyết trọn vẹn luồng công việc hằng ngày của Developer & Quản lý dự án: tự động hóa tiếp nhận chỉ đạo công việc đa thức (Text, Email/Teams, Ảnh chụp màn hình lỗi, Specs), bóc tách dữ liệu có cấu trúc (Structured Extraction), quản lý tiến độ Kanban (State Management), lập kế hoạch WBS 4 giai đoạn chuẩn mực, bảo toàn mốc thời gian gốc (Timeline Preservation), phân tầng lưu trữ dự án thông minh (**Hot vs Cold Storage**), cơ chế bảo vệ phạm vi tác vụ (**Site-Scoped Guardrail**), tra cứu kho tri thức kỹ thuật nội bộ (RAG Retrieval) và xuất báo cáo công việc tháng định kỳ (.xlsx) chỉ với 1 click.

Hệ thống hỗ trợ kiến trúc mô hình lai linh hoạt (**Hybrid LLM Provider**): chạy cục bộ 100% offline với **Ollama (Qwen 2.5:7b)** đảm bảo bảo mật dữ liệu tuyệt đối hoặc kết nối đám mây với **Google Gemini (Flash/Pro)**.

---

## 🎯 Bối Cảnh Nghiệp Vụ & Bài Toán Giải Quyết

Trong thực tế vận hành công việc kỹ thuật hằng ngày, kỹ sư phần mềm thường đối mặt với các vấn đề:
1. **Quá tải thông tin từ nhiều kênh:** Nhận task phân mảnh qua Teams, Email, hình ảnh chụp nhanh giao diện hoặc yêu cầu trao đổi miệng.
2. **Mất thời gian lập kế hoạch dự án:** Khi nhận dự án mới, cần ngay bản phân rã công việc (WBS) gồm 4 giai đoạn với mốc thời gian, nhân sự, mục tiêu và deliverables rõ ràng.
3. **Thay đổi phạm vi làm vỡ timeline (Scope Creep):** Khi dự án đang chạy có yêu cầu thay đổi (Change Request), kỹ sư cần ghi nhận chính xác nội dung thay đổi mà **không được tùy tiện xê dịch timeline gốc** đã cam kết với ban quản lý.
4. **Phân tán tài liệu kỹ thuật:** Specs dự án, tài liệu kiến trúc dùng chung nằm rải rác, gây khó khăn cho việc tra cứu nhanh khi đang code.
5. **Nhiễu loạn danh sách dự án (Project Bloat):** Quá nhiều dự án cũ lẫn lộn với dự án đang active làm rối tầm nhìn quản lý.
6. **Áp lực báo cáo cuối tháng:** Cuối mỗi tháng phải ngồi lục lại lịch sử chat, email, commit để viết báo cáo KPI và tiến độ nộp cấp quản lý.

👉 **Task Assistant Agent** đóng vai trò là một trợ lý thông minh thường trực, tự động xử lý toàn bộ các khâu trên thông qua hội thoại tự nhiên và giao diện điều khiển tập trung.

---

## 🧠 Kiến Trúc Hệ Thống (Single-Agent ReAct Architecture)

Agent hoạt động theo mô hình **ReAct (Reasoning + Acting)** lặp tuần tự, sử dụng LLM làm bộ điều khiển trung tâm để phân tích ngữ cảnh, kiểm duyệt phạm vi an toàn, lựa chọn công cụ thực thi (Tool Calling) và duy trì ngữ cảnh trạng thái:

```text
                                [ MULTI-MODAL INPUT ]
               Chat tự nhiên | Email/Teams | Ảnh chụp lỗi | Specs PDF/MD
                                          │
                                          ▼
                ┌──────────────────────────────────────────────────┐
                │          GATEWAY & SITE-SCOPED GUARDRAIL         │
                │  - Kiểm tra tính hợp lệ của Site / Project       │
                │  - Từ chối prompt ngoài phạm vi / không rõ site  │
                └─────────────────────────┬────────────────────────┘
                                          │ Hợp lệ
                                          ▼
                ┌──────────────────────────────────────────────────┐
                │        AGENTIC CORE CONTROLLER (FastAPI)         │
                │  - LLM Engine: Ollama (Qwen 2.5) / Google Gemini │
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
 │  - Storage Tiering: 🔥 HOT SPRINT vs ❄️ COLD ARCHIVE   │        │
 └──────────────────────────┬─────────────────────────────┘        │
                            │                                      ▼
                            ▼                     ┌──────────────────────────┐
                 ┌────────────────────┐           │ VECTOR STORE (ChromaDB)  │
                 │   Report Engine    │           │ - Recursive Text Splitter│
                 │ (OpenPyXL Export)  │           │ - Document Scoping       │
                 │  .xlsx Doanh Nghiệp│           │   (GENERAL vs PROJECT)   │
                 └────────────────────┘           └──────────────────────────┘
```

---

## 🚀 Điểm Nhấn Kỹ Thuật (Key Technical Highlights)

### 1. Hybrid LLM Engine (Local On-Premise & Cloud API)
* **Ollama (Qwen 2.5:7b Local):** Chạy trực tiếp trên máy chủ / workstation nội bộ, đảm bảo **zero data leakage**, bảo mật mã nguồn và dữ liệu công việc doanh nghiệp, không phát sinh chi phí API token.
* **Google Gemini (Flash / Pro Cloud):** Khả năng phân tích hình ảnh đa phương thức (Vision) cho ảnh chụp màn hình lỗi, mockup và tốc độ suy luận đám mây vượt trội.
* **Chuyển đổi 1-Click:** Dễ dàng đổi qua lại giữa Ollama và Gemini ngay trên modal Cài đặt của Web UI mà không cần khởi động lại server.

### 2. Site-Scoped Guardrail & Context Safety
* **Bộ lọc phạm vi ngữ cảnh:** Agent tự động rà soát xem yêu cầu có thuộc về các site/dự án trong danh mục hệ thống quản lý hay không.
* **Ngăn chặn tác vụ rác:** Tuyệt đối không tự động tạo task hoặc vẽ kế hoạch cho các câu hỏi vu vơ, việc cá nhân hoặc không rõ tên website/dự án; chủ động phản hồi lịch sự hướng dẫn dev định danh rõ ràng.

### 3. Data Tiering & AI Storage Advisor (Hot vs Cold Storage)
* **Phân tầng lưu trữ dự án:**
  * 🔥 **Hot Storage:** Dành cho các dự án đang triển khai tích cực, có nhiều task `TODO`/`IN_PROGRESS`, task ưu tiên `HIGH`/`URGENT` hoặc đang được trao đổi liên tục trong chat.
  * ❄️ **Cold Storage:** Dành cho các dự án đã hoàn tất (DONE 100%), đang tạm dừng (`ON_HOLD`), hoặc đóng băng lưu trữ.
* **AI Storage Advisor:** Tự động phân tích tình trạng vận hành của các dự án và đưa ra đề xuất chuyển vùng thông minh, **tôn trọng quyền quyết định của con người (Human-in-the-Loop)**: chỉ gợi ý chứ không tự ý can thiệp khi chưa có sự xác nhận của developer.

### 4. Interactive Document Scoping (Phạm Vi Kho Tri Thức RAG)
* **Phân loại tri thức rõ ràng:**
  * `GENERAL`: Tài liệu quy chuẩn kỹ thuật, guideline chung áp dụng cho mọi dự án.
  * `PROJECT`: Đặc tả kỹ thuật (specs), cấu hình riêng gắn chặt với một website/dự án cụ thể.
* **Chuyển đổi phạm vi linh hoạt:** Hỗ trợ cập nhật phạm vi tài liệu và tự động làm mới chỉ mục vector trong ChromaDB.

### 5. Interactive Chat Stream Interruption & Task Duplication
* **Ngắt luồng Agent tức thì:** Nút Cancel cho phép dừng ngay lập tức quá trình suy nghĩ của mô hình khi dev gửi nhầm prompt và tự động dọn dẹp tin nhắn gửi nhầm.
* **Nhân bản công việc 1-click:** Tính năng Duplicate Task giúp nhân bản nhanh các đầu việc định kỳ hoặc lặp lại.

---

## ✨ Các Phân Hệ Chức Năng Chính

| Phân hệ | Chức năng chính | Giá trị mang lại |
|---|---|---|
| **💬 Chat Tiếp Nhận & Zero-Click Task Extraction** | Tiếp nhận input tự nhiên qua text, email, ảnh chụp; tự động nhận diện intent, trích xuất thực thể và tạo task Kanban tự động. Hỗ trợ ngắt luồng chat tức thì. | Tiết kiệm 90% thời gian nhập liệu thủ công của developer. |
| **📋 Kanban Board State Management** | Bảng công việc 4 cột (`TODO` ➔ `IN PROGRESS` ➔ `BLOCKED` ➔ `DONE`) với bộ lọc nguồn việc, dự án, cảnh báo deadline trực quan, nút nhân bản task và xóa task an toàn. | Trực quan hóa tiến độ công việc, dễ dàng kéo thả và theo dõi blocker. |
| **🚀 WBS 4-Phase Planner & Change Tracker** | Tự động lập kế hoạch 4 giai đoạn chuẩn (Specs ➔ Backend ➔ Frontend ➔ UAT) và ghi nhật ký yêu cầu thay đổi (Change Notes) mà không sửa timeline gốc. | Chuẩn hóa quy trình giao nộp kế hoạch dự án cho cấp trên. |
| **🔥/❄️ Quản Lý Phân Vùng Dự Án (Hot & Cold)** | Lọc và quản lý dự án theo vùng hoạt động (Hot) và vùng lưu trữ (Cold); tích hợp AI Storage Advisor phân tích khuyến nghị tối ưu hiển thị. | Giữ giao diện làm việc luôn tinh gọn, tập trung vào các sprint nóng. |
| **📚 Kho Tri Thức RAG Đa Phạm Vi** | Quản lý tập trung tài liệu dự án và tài liệu dùng chung; tải lên, gán phạm vi (General / Project), xóa và tra cứu ngữ nghĩa tức thì qua vector search ChromaDB. | Agent nắm rõ specs chi tiết, trả lời câu hỏi nghiệp vụ chuẩn xác. |
| **📊 Business Report Engine** | Xuất báo cáo tổng kết tháng tự động ra định dạng Excel (`.xlsx`) chuẩn hóa KPI, danh mục công việc hoàn thành và Change Requests chỉ với 1 click. | Đến kỳ báo cáo chỉ cần bấm 1 nút là có file nộp sếp. |

---

## 🏗️ Ngăn Xếp Công Nghệ (Tech Stack)

| Thành phần | Công nghệ / Thư viện | Vai trò kỹ thuật |
| --- | --- | --- |
| **Agent Framework** | LangChain / LangGraph | Điều phối ReAct Loop, Tool Binding và State Context |
| **Local LLM Engine** | Ollama (Qwen 2.5:7b) | Suy luận ngôn ngữ cục bộ on-premise, bảo mật 100%, 0 chi phí token |
| **Cloud LLM Engine** | Google Gemini (Flash / Pro) | Inference đám mây tốc độ cao, phân tích thị giác hình ảnh lỗi (Vision) |
| **Backend API** | FastAPI (Python 3.12+) | High-performance Asynchronous RESTful API Server |
| **Vector Database** | ChromaDB | Lưu trữ Vector Embeddings, Semantic Search RAG |
| **Relational Database** | SQLite (WAL Mode) | Quản lý bảng dữ liệu tasks, timeline, change logs với phân vùng Hot/Cold |
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
│   ├── config.py                   # Cấu hình biến môi trường (Ollama, Gemini, SMTP, SQLite)
│   ├── database.py                 # SQLite engine (WAL Mode), Schema definition & CRUD ops
│   ├── db_ops.py                   # Backward-compatibility alias layer
│   ├── models.py                   # Pydantic schemas cho API & Agent Structured Outputs
│   ├── agent/
│   │   ├── graph.py                # ReAct Agent Core Runner, Ollama / Gemini router & Workflow
│   │   ├── tools.py                # Tool Calling definitions (Task, RAG, Plan, Report, Storage)
│   │   ├── prompts.py              # Context Engineering, Guardrails & System Prompts
│   │   └── assistant.py            # Backward-compatibility alias layer
│   ├── api/
│   │   └── routes.py               # REST API Endpoints (CRUD Tasks, Projects, RAG, Export)
│   ├── rag/
│   │   ├── vector_store.py         # Text chunking, Embedding pipeline & ChromaDB indexing
│   │   └── document_loader.py      # Bộ trích xuất nội dung từ PDF, MD, TXT, Excel
│   ├── reports/
│   │   └── monthly_report.py       # Engine xử lý tạo báo cáo tháng (.xlsx)
│   ├── scheduler/
│   │   └── worker.py               # Background worker định kỳ quét blocker & overdue tasks
│   ├── tools/
│   │   ├── storage_tier_tools.py   # AI Storage Advisor (Phân tích Hot / Cold storage)
│   │   ├── planning_tools.py       # WBS Generator & Change Request Logger
│   │   ├── task_parser.py          # Bộ phân tích tin nhắn Teams / Email
│   │   ├── excel_tools.py          # Nhập liệu tự động từ bảng tính Excel
│   │   └── email_tools.py          # Bộ điều phối gửi email thông báo
│   └── web/
│       ├── templates/              # Giao diện Jinja2 UI (modular tabs & dialogs)
│       └── static/                 # Stylesheets & Modular JS components
└── data/
    ├── task_assistant.db           # SQLite database file (WAL mode)
    ├── chroma_db/                  # ChromaDB vector persistent directory
    └── docs/                       # Thư mục lưu trữ tài liệu kỹ thuật dự án
```

---

## ⚙️ Cài Đặt & Khởi Chạy Nhanh

### 1. Yêu cầu hệ thống
* **Python 3.12+**
* Trình quản lý gói **`uv`**:

```powershell
# Cài đặt uv trên Windows (PowerShell)
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

```bash
# Cài đặt uv trên Linux / macOS
curl -LsSf https://astral.sh/uv/install.sh | sh
```

### 2. Thiết lập Mô hình AI (Chọn 1 trong 2 hoặc dùng cả hai)

#### Lựa chọn A: Dùng Ollama Local (Khuyên dùng - Miễn phí & Riêng tư)
1. Tải và cài đặt [Ollama](https://ollama.com/).
2. Kéo mô hình Qwen 2.5 về máy:
```bash
ollama run qwen2.5:7b
```

#### Lựa chọn B: Dùng Google Gemini Cloud
Lấy API Key miễn phí tại [Google AI Studio](https://aistudio.google.com/).

### 3. Cài đặt dependencies

```bash
uv sync
```

### 4. Thiết lập biến môi trường

Sao chép file mẫu:

```bash
cp .env.example .env
```

Điền cấu hình vào `.env`:

```env
# AI Provider (ollama hoặc gemini)
LLM_PROVIDER=ollama
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=qwen2.5:7b

# Google Gemini (Nếu dùng Gemini)
GEMINI_API_KEY=your_gemini_api_key_here
GEMINI_MODEL=gemini-flash-latest
```

*(Lưu ý: Bạn hoàn toàn có thể cấu hình và đổi qua lại giữa Ollama và Gemini ngay trên bảng **Cài đặt** của Web UI).*

### 5. Khởi chạy ứng dụng

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
| `POST` | `/api/chat/cancel` | Ngắt tức thời luồng suy nghĩ của Agent và dọn tin nhắn gửi nhầm |
| `GET` | `/api/chat/history` | Lấy lịch sử hội thoại gần nhất |
| `GET` | `/api/tasks` | Lấy danh sách toàn bộ tasks kèm trạng thái và metadata |
| `POST` | `/api/tasks` | Tạo task mới thủ công |
| `PUT` | `/api/tasks/{id}` | Cập nhật thông tin / trạng thái task (`TODO`, `IN_PROGRESS`, `DONE`, `BLOCKED`) |
| `DELETE` | `/api/tasks/{id}` | Xóa một task cụ thể |
| `POST` | `/api/tasks/{id}/duplicate` | Nhân bản 1-click công việc cụ thể |
| `DELETE` | `/api/tasks/clear-all` | Xóa sạch toàn bộ task (yêu cầu xác nhận an toàn) |
| `GET` | `/api/projects` | Lấy danh sách dự án (có thể lọc theo phân vùng `HOT` hoặc `COLD`) |
| `POST` | `/api/projects/new-plan` | Tạo dự án mới kèm phân bổ 4 giai đoạn WBS |
| `PUT` | `/api/projects/{id}/storage-tier` | Chuyển phân vùng dự án giữa 🔥 Hot Storage và ❄️ Cold Storage |
| `GET` | `/api/projects/tier-analysis` | Kích hoạt AI Storage Advisor phân tích và đề xuất phân vùng |
| `DELETE` | `/api/projects/{id}` | Xóa một dự án khỏi hệ thống |
| `GET` | `/api/projects/change-notes` | Lấy danh sách nhật ký thay đổi phạm vi (Change Requests) |
| `POST` | `/api/projects/change-notes` | Ghi nhận yêu cầu thay đổi mới mà không can thiệp timeline gốc |
| `GET` | `/api/docs` | Lấy danh mục tài liệu đã được index vào ChromaDB |
| `POST` | `/api/docs/upload` | Tải lên tài liệu kỹ thuật mới kèm phân loại phạm vi (General / Project) |
| `PUT` | `/api/docs/scope` | Cập nhật phạm vi áp dụng của tài liệu kỹ thuật |
| `DELETE` | `/api/docs/{id}` | Xóa tài liệu khỏi kho tri thức và vector database |
| `GET` | `/api/sites` | Lấy danh mục các website/dự án đã đăng ký trong hệ thống |
| `GET` | `/api/tasks/export-monthly-report` | Tải về file Excel (.xlsx) báo cáo KPI và công việc tháng tự động |
| `GET` | `/api/settings` | Lấy cấu hình runtime hiện tại của hệ thống |
| `POST` | `/api/settings` | Lưu cập nhật cấu hình LLM provider, API key, model và SMTP |

---

## 🧪 Kiểm Tra & Đảm Bảo Chất Lượng Code (Quality Assurance)

Dự án cung cấp kịch bản kiểm tra tự động tính toàn vẹn của hệ thống:

```powershell
# Kiểm tra tính toàn vẹn của các Python modules
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

Phát triển bởi đội ngũ kỹ sư và phục vụ cho mục đích tối ưu hóa năng suất làm việc của lập trình viên và nhà quản lý dự án. Phát hành dưới giấy phép mã nguồn mở MIT.
