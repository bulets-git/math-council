# KẾ HOẠCH THỰC THI CHO AI AGENT (MATH COUNCIL - BƯỚC 2)

## 1. Nguyên tắc bất di bất dịch (Strict Guardrails)
1. **Phạm vi Bước 2:** Chỉ dựng bộ khung (Walking Skeleton) gồm Next.js + FastAPI + PostgreSQL + Alembic + Docker Compose.
2. **TUYỆT ĐỐI KHÔNG** cài đặt hoặc thêm Redis, Celery/RQ, SSE, hay gọi LLM thực tế ở Bước 2.
3. **Không sửa đổi** cấu trúc bảng trong `app/models/problem.py` và `app/models/run.py` đã khóa.
4. **Quy tắc HTTP Status & Lỗi:**
   - `GET /health` -> `200 OK`
   - `POST /api/v1/problems` -> `201 Created` (Trả `422` nếu `statement_original` rỗng hoặc toàn khoảng trắng).
   - `GET /api/v1/problems` -> `200 OK` (Danh sách bài toán sắp xếp mới nhất trước, kèm `latest_run_status`).
   - `GET /api/v1/problems/{id}` -> `200 OK` (Trả `404` nếu UUID không tồn tại).
   - `POST /api/v1/problems/{id}/runs` -> `202 Accepted` (Chỉ tạo bản ghi Run với `status = "queued"`, không gọi AI; trả `404` nếu `problem_id` không tồn tại).
   - `GET /api/v1/runs/{id}` -> `200 OK` (Trả `404` nếu UUID không tồn tại).
   - Không bao giờ để lộ `DATABASE_URL` hoặc stack trace ra JSON lỗi trả về cho client.
5. **Quy tắc Frontend:**
   - Dùng Next.js App Router (TypeScript + TailwindCSS).
   - Cấu hình `next.config.mjs` sử dụng `rewrites` để proxy `/api/v1/:path*` và `/health` sang `${process.env.INTERNAL_API_URL || 'http://api:8000'}/...`.
   - Dùng `react-markdown`, `remark-math`, `rehype-katex` và `katex` để hiển thị công thức toán học.
