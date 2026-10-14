# KẾ HOẠCH THỰC THI CHO AI AGENT (MATH COUNCIL - BƯỚC 3: MULTI-AGENT & ORCHESTRATOR)

## 1. Kiến trúc & Nguyên tắc bất di bất dịch (Strict Guardrails)
1. **Kiến trúc Modular Monolith + Async Worker:**
   - Bổ sung `redis` (Redis 7 Alpine) và `worker` (chạy cùng codebase với `api` nhưng entrypoint là worker process) vào `docker-compose.yml`.
   - Các Agent TUYỆT ĐỐI không gọi trực tiếp lẫn nhau; mọi luồng dữ liệu phải đi qua `orchestrator/` và lưu trạng thái vào PostgreSQL.
2. **Danh sách 9 Bảng Mới (Tổng cộng 11 bảng trong DB):**
   - Giữ nguyên `problems` và `runs` từ Bước 2.
   - Thêm 9 bảng: `run_agents`, `messages`, `solutions`, `claims`, `claim_dependencies`, `challenges`, `challenge_events`, `model_calls`, `final_reports`.
3. **Danh sách 9 Endpoints Mới cần bổ sung vào `/api/v1`:**
   - `GET /api/v1/models`: Trả về danh sách các LLM models được cấu hình.
   - `POST /api/v1/runs/{id}/cancel`: Hủy phiên đang chạy (`status -> cancelled`).
   - `POST /api/v1/runs/{id}/resume`: Tiếp tục phiên đang ở trạng thái `needs_review` hoặc bị gián đoạn hợp lệ.
   - `GET /api/v1/runs/{id}/events`: Stream SSE (Server-Sent Events) qua Redis Pub/Sub.
   - `GET /api/v1/runs/{id}/messages`: Lịch sử các lượt trao đổi/prompt.
   - `GET /api/v1/runs/{id}/solutions`: Danh sách các phiên bản lời giải (kèm claims).
   - `GET /api/v1/runs/{id}/challenges`: Danh sách các phản biện và lịch sử `challenge_events`.
   - `GET /api/v1/runs/{id}/report`: Báo cáo tổng hợp cuối cùng của Judge.
   - `GET /api/v1/runs/{id}/usage`: Thống kê chi tiết token, độ trễ và chi phí từ `model_calls`.

## 2. Quy tắc Nghiệp vụ & State Machine
1. **Chuỗi trạng thái (`runs.status`):**
   - Luồng chính: `queued -> normalizing -> solving -> critiquing -> revising -> adjudicating -> completed`
   - Trạng thái rẽ nhánh/kết thúc: `needs_review`, `failed`, `cancelled`, `budget_exhausted`.
2. **Bước `normalizing` (Chuẩn hóa đề):**
   - Nếu phát hiện đề toán có dấu hiệu chép sai công thức hoặc thiếu dữ kiện nghiêm trọng, KHÔNG tự ý sửa đề mà lưu cảnh báo và chuyển `run.status = "needs_review"`, dừng đợi người dùng xác nhận qua `/resume`.
3. **Quản lý Mệnh đề (`claims/`) & Đồ thị phụ thuộc:**
   - ID mệnh đề (`C1`, `C2`,...) do backend chuẩn hóa và quản lý.
   - Bắt buộc kiểm tra chu trình (DAG Cycle Detection) trên `claim_dependencies`. Nếu phát hiện phụ thuộc vòng tròn, đánh dấu lỗi lập luận ngay lập tức.
   - Không cấp trạng thái `verified` chỉ vì LLM khẳng định đúng; chỉ dùng `unverified`, `supported`, `disputed`, `rejected`.
4. **Quy tắc Phản biện (`challenges`) & Sửa chữa (`revising`):**
   - Phân loại lỗi bắt buộc (`error_type`): `valid`, `invalid_inference`, `missing_case`, `unsupported_claim`, `incorrect_calculation`, `ambiguous_statement`, `needs_more_evidence`.
   - Trạng thái phản biện (`status`): `open`, `accepted`, `rejected`, `unresolved`.
   - **Quy tắc sắt:** Solver KHÔNG được tự đóng (`accepted`/`rejected`) phản biện nhắm vào mình. Solver chỉ tạo phiên bản `solution` mới (`version + 1`, không ghi đè bản cũ). Bước thẩm định sẽ cập nhật trạng thái challenge và ghi vào `challenge_events`.
5. **Kiểm soát Ngân sách (`budget/`):**
   - Trước mỗi lần gọi LLM (đặc biệt khi Solver A và B chạy song song), phải kiểm tra: `actual_cost_usd + reserved_cost_usd + estimated_call_cost <= budget_usd`.
   - Nếu không đủ ngân sách, hủy lệnh gọi và chuyển Run sang `budget_exhausted`.
6. **Quản lý Prompt (`prompts/`):**
   - Mỗi prompt phải có `prompt_version` bất biến được lưu lại trong `messages`/`model_calls`. Nội dung đề toán phải đặt trong thẻ phân tách dữ liệu để chống Prompt Injection.