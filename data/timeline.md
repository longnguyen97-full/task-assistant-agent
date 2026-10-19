# 📅 Kế hoạch & Tiến độ Dự án (Project Timeline)
**Dự án:** Task Assistant AI & Developer Portal  
**Quản lý dự án:** PM Tech Lead  
**Thời gian thực hiện:** 01/10/2026 - 15/11/2026 (6 Tuần)  
**Chu kỳ Sprint:** 2 tuần / Sprint

---

## 🎯 Tổng quan các Milestone (Cột mốc quan trọng)

| Milestone | Tên giai đoạn | Thời hạn | Mục tiêu chính | Trạng thái |
|---|---|---|---|---|
| **M1** | Foundation & Auth | 14/10/2026 | Hoàn thiện kiến trúc cơ bản, DB schema và Auth API | ✅ Đã hoàn thành |
| **M2** | Core Task & Realtime | 28/10/2026 | Quản lý Task Kanban, Daily Note Logging & SQLite sync | 🟡 Đang thực hiện |
| **M3** | RAG & AI Agent Planning | 08/11/2026 | Tích hợp LangChain, ChromaDB RAG, AI Planning | ⚪ Sắp tới |
| **M4** | Notification & Production | 15/11/2026 | Email Dispatcher, APScheduler Worker, Deploy | ⚪ Sắp tới |

---

## 🚀 Chi tiết các Sprint

### 📌 Sprint 1: Foundation & Authentication (01/10/2026 - 14/10/2026)
- **Mục tiêu:** Thiết lập cấu trúc dự án, cấu hình FastAPI, SQLite database, và hệ thống xác thực.
- **Tasks bàn giao:**
  1. [x] Khởi tạo FastAPI repository, UV package manager và cấu trúc module.
  2. [x] Thiết kế SQLite database schema cho `tasks`, `daily_notes`, `email_logs`.
  3. [x] Xây dựng REST API CRUD cơ bản cho Tasks.
  4. [x] Cấu hình Dockerfile và môi trường local development.
- **Tiêu chuẩn nghiệm thu:** API chạy trơn tru trên local, test coverage > 80%.

---

### 📌 Sprint 2: Core Task & Logging (15/10/2026 - 28/10/2026) *(HIỆN TẠI)*
- **Mục tiêu:** Hoàn thiện bảng Kanban, cơ chế ghi nhận nhật ký hàng ngày (daily notes) và phát hiện blocker.
- **Tasks bàn giao:**
  1. [ ] Tích hợp giao diện Kanban kéo thả 4 trạng thái: TODO, IN_PROGRESS, BLOCKED, DONE.
  2. [ ] Xây dựng cơ chế Chat bóc tách task tự động từ lời thoại tự nhiên của Developer.
  3. [ ] Xử lý phân loại blocker và gán mức độ ưu tiên (LOW, MEDIUM, HIGH, URGENT).
  4. [ ] Viết API đồng bộ trạng thái task và lịch sử ghi chú.
- **Cảnh báo tiến độ:** Hạn chót Sprint 2 là **28/10/2026**. Cần đặc biệt chú ý các task liên quan đến OAuth2 hoặc tích hợp dịch vụ ngoài nếu bị nghẽn (blocker) cần báo cáo ngay.

---

### 📌 Sprint 3: RAG Knowledge Base & AI Agent (29/10/2026 - 08/11/2026)
- **Mục tiêu:** Đọc hiểu tài liệu `timeline.md`, `specs.md`, các file PDF qua ChromaDB và điều phối Agent.
- **Tasks bàn giao:**
  1. [ ] Thiết lập ChromaDB vector store lưu embeddings tài liệu dự án.
  2. [ ] Xây dựng Tool RAG tra cứu specs và timeline cho Agent.
  3. [ ] Xây dựng Tool AI Planning phân tích rủi ro trễ hạn (Deadline Risk Analysis).
  4. [ ] Xây dựng prompt system thông minh bằng tiếng Việt có cấu trúc JSON output.
- **Tiêu chuẩn nghiệm thu:** Agent trả lời chính xác các câu hỏi về milestone, deadline và đưa ra gợi ý giải quyết blocker.

---

### 📌 Sprint 4: Proactive Reminders & Production (09/11/2026 - 15/11/2026)
- **Mục tiêu:** Tự động hóa gửi email báo cáo (Email Dispatcher) và worker nhắc việc định kỳ (APScheduler).
- **Tasks bàn giao:**
  1. [ ] Xây dựng APScheduler worker quét task lúc 9:00 AM mỗi sáng.
  2. [ ] Tích hợp SMTP Tool gửi email tổng hợp tiến độ và cảnh báo blocker khẩn cấp.
  3. [ ] Tối ưu hóa UI Web Dashboard và kiểm thử toàn diện End-to-End.
  4. [ ] Viết tài liệu bàn giao và đóng gói Docker container.
