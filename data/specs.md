# 📋 Tài liệu Đặc tả Kỹ thuật (Technical Specifications)
**Dự án:** Task Assistant AI Agent  
**Phiên bản:** v1.2  
**Đối tượng áp dụng:** Toàn bộ Developer & Tech Lead dự án  

---

## 1. Tiêu chuẩn Mã nguồn & Kiến trúc
- **Ngôn ngữ:** Python 3.12+ (hỗ trợ CPython 3.13)
- **Framework Web & API:** FastAPI (Async endpoints, Pydantic v2 schemas)
- **Trình quản lý gói:** `uv` (nhanh, tương thích chuẩn PEP 621)
- **Cơ sở dữ liệu Quan hệ (Notes & Tasks):** SQLite (file lưu trữ `data/task_assistant.db`), sử dụng connection pooling và WAL mode để tối ưu đọc ghi song song.
- **Cơ sở dữ liệu Vector (RAG):** ChromaDB (lưu trữ vector embeddings, tự động chunk tài liệu với size 800 tokens, overlap 150 tokens).
- **Mô hình ngôn ngữ (LLM):** Google Gemini (`gemini-2.5-flash` cho tác vụ nhanh/chat hằng ngày, `gemini-1.5-pro` cho tác vụ phân tích lập kế hoạch sâu).
- **Hàng đợi & Tác vụ định kỳ (Cron):** APScheduler `BackgroundScheduler` chạy ngầm.

---

## 2. Quy định về Quản lý Task & Trạng thái (Task Status Specs)
Mỗi task trong hệ thống phải tuân theo vòng đời trạng thái:
1. `TODO`: Task mới được tạo hoặc lên kế hoạch, chưa bắt đầu code.
2. `IN_PROGRESS`: Dev đang tích cực phát triển. Một dev không nên có quá 3 tasks ở trạng thái này cùng lúc.
3. `BLOCKED`: Task bị tắc nghẽn do yếu tố khách quan (thiếu API credentials, bên thứ 3 chưa phản hồi, thiếu specs, bug thư viện).
   - **Bắt buộc:** Phải nêu rõ lý do `blocker_reason`.
   - **Cơ chế:** Khi chuyển sang `BLOCKED`, hệ thống tự động gắn cờ cảnh báo rủi ro (risk flag) và đề xuất phương án xử lý hoặc soạn email thông báo PM/Tech Lead.
4. `DONE`: Hoàn thành kiểm thử và code review.

### Mức độ ưu tiên (Priority Levels):
- `LOW`: Các cải tiến nhỏ, refactor mã nguồn.
- `MEDIUM`: Tính năng thông thường theo Sprint.
- `HIGH`: Tính năng cốt lõi hoặc task có phụ thuộc (dependency) ảnh hưởng người khác.
- `URGENT`: Blocker nghiêm trọng hoặc lỗi nóng (hotfix).

---

## 3. Quy chuẩn Email Dispatcher & Mẫu Báo cáo (Email Specs)
Hệ thống hỗ trợ 3 mẫu email chuẩn:
1. **Báo cáo tiến độ hằng ngày (Daily Progress Report):**
   - Danh sách việc đã xong trong ngày.
   - Việc đang làm dở và việc dự kiến làm ngày mai.
   - Các blocker đang gặp phải kèm đề xuất trợ giúp.
2. **Cảnh báo Blocker khẩn cấp (Blocker Escalation Alert):**
   - Tiêu đề: `[URGENT BLOCKER] {Tên task} - Cần hỗ trợ`
   - Nội dung: Tóm tắt sự cố, tác động tới deadline của Milestone, người phụ trách và thông tin liên hệ.
3. **Tổng kết kế hoạch & Phân tích rủi ro (Sprint Risk Summary):**
   - Gửi cho PM vào đầu tuần hoặc khi có task quá hạn.

---

## 4. Quy định Bảo mật & Cấu hình Môi trường
- Toàn bộ secret keys (`GEMINI_API_KEY`, mật khẩu SMTP) lưu trữ trong file `.env`. Tuyệt đối không commit file `.env` lên git.
- Khuyến nghị sử dụng App Password khi kết nối Gmail SMTP (`smtp.gmail.com:587`).
- Hỗ trợ chế độ Mock Dispatcher: Khi chưa cấu hình SMTP thật, hệ thống tự động ghi nhật ký vào bảng `email_logs` mà không làm gián đoạn luồng làm việc.
