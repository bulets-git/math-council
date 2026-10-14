# HÀNG ĐỢI THỰC THI TỰ ĐỘNG (AUTONOMOUS EXECUTION QUEUE)

**QUY TẮC BẮT BUỘC CHO AGENT:**
1. Thực hiện tuần tự từng Phase từ trên xuống dưới. **TUYỆT ĐỐI KHÔNG** làm gộp nhiều Phase cùng lúc.
2. Ở cuối mỗi Phase, bắt buộc phải chạy lệnh **Verification Gate** trong terminal.
3. Nếu lệnh Verification Gate báo lỗi (exit code != 0), phải tự đọc log lỗi, sửa code và chạy lại cho đến khi PASS 100%.
4. Ngay khi một Phase PASS, hãy cập nhật file `AUTO_RUNNER_QUEUE.md` này: đổi `[ ]` thành `[x]` ở Phase đó, sau đó **TỰ ĐỘNG chuyển sang thực hiện Phase kế tiếp ngay lập tức** mà không cần dừng lại hỏi người dùng.

---

## PHẦN A: HOÀN THIỆN BƯỚC 2 (WALKING SKELETON)

- [x] **Phase 2.1: Backend Repositories, Routes, Alembic & Main App**
  - Đọc `STEP2_AGENT_PLAN.md` và các file mẫu trong `services/api/app/models/` và `schemas/`[cite: 1].
  - Tạo `repositories/problem_repo.py` và `run_repo.py` (dùng `AsyncSession`)[cite: 1].
  - Tạo `routes/problems.py` và `routes/runs.py` thực thi 5 endpoints (`/api/v1/problems`, `/api/v1/problems/{id}`, `/api/v1/problems/{id}/runs`, `/api/v1/runs/{id}`) đúng mã HTTP `201`, `202`, `404`, `422`[cite: 1].
  - Tạo `app/main.py` có `GET /health`[cite: 1], CORS, Global Exception Handler.
  - Cấu hình `alembic.ini`, `alembic/env.py` (async) và tạo migration `0001_initial_step2_tables.py`[cite: 1].
  - **Verification Gate:** Chạy `docker compose up -d db api` và kiểm tra `curl -f http://localhost:8000/health` trả về 200 OK[cite: 1].

- [x] **Phase 2.2: Automated Pytest cho Bước 2**
  - Tạo `services/api/tests/conftest.py` và `tests/test_api_step2.py`[cite: 1].
  - Test đủ các case: `/health` (200), tạo đề LaTeX (201), đề rỗng/khoảng trắng (422), đọc đề (200), tạo run `queued` (202), đọc run (200), UUID không tồn tại (404)[cite: 1].
  - **Verification Gate:** Chạy `docker compose exec api pytest tests/test_api_step2.py -v` phải PASS 100%[cite: 1].

- [x] **Phase 2.3: Frontend Next.js + KaTeX & Nghiệm thu Bước 2**
  - Tạo `apps/web/` (Next.js App Router, TypeScript, TailwindCSS, `Dockerfile`, `next.config.mjs` rewrites `/api/v1` sang `http://api:8000`)[cite: 1].
  - Tạo `components/MathRenderer.tsx` (`react-markdown` + `remark-math` + `rehype-katex` với `throwOnError: false`)[cite: 1].
  - Tạo các trang `/`, `/problems`, `/problems/new` (Live LaTeX Preview), `/problems/[id]` (kèm nhãn "Chưa chạy AI")[cite: 1].
  - **Verification Gate:** Chạy `docker compose up -d --build web`, kiểm tra `curl -f http://localhost:3000` trả về 200 OK[cite: 1].

---

## PHẦN B: TRIỂN KHAI BƯỚC 3 (MULTI-AGENT & ORCHESTRATOR)

- [x] **Phase 3.1: Mở rộng 9 Bảng Database & Kiểm tra chu trình DAG (`claims/`)**
  - Đọc `STEP3_AGENT_PLAN.md`[cite: 1].
  - Tạo SQLAlchemy models cho 9 bảng: `run_agents`, `messages`, `solutions`, `claims`, `claim_dependencies`, `challenges`, `challenge_events`, `model_calls`, `final_reports`[cite: 1].
  - Tạo Alembic migration `0002_step3_agent_tables.py` và chạy `alembic upgrade head`[cite: 1].
  - Tạo Pydantic schemas cho Agent contracts trong `schemas/agent_contracts.py` và thuật toán kiểm tra chu trình trong `claims/dag_validator.py`[cite: 1].
  - **Verification Gate:** Viết và chạy `docker compose exec api pytest tests/test_dag_validator.py -v` PASS 100%.

- [x] **Phase 3.2: LLM Gateway, Mock Provider, Prompts & Budget Manager**
  - Tạo `prompts/` (có version và thẻ chống Prompt Injection)[cite: 1].
  - Tạo `budget/manager.py` (kiểm tra ngân sách, giữ chỗ in-flight request song song, ghi bảng `model_calls`, raise `BudgetExhaustedError` nếu lố `budget_usd`)[cite: 1].
  - Tạo `llm_gateway/` gồm `BaseLLMAdapter`, `OpenAIAdapter`, `GeminiAdapter` và `DeterministicMockAdapter`[cite: 1].
  - **Verification Gate:** Viết và chạy `docker compose exec api pytest tests/test_budget_and_gateway.py -v` PASS 100%.

- [x] **Phase 3.3: Redis, Worker & State Machine Orchestrator**
  - Thêm `redis` và `worker` vào `docker-compose.yml`[cite: 1].
  - Xây dựng `orchestrator/` và `discussion/` xử lý luồng: `queued -> normalizing -> solving (Solver A & B song song) -> critiquing (Skeptic) -> revising -> adjudicating -> completed` (kèm nhánh `needs_review` và `budget_exhausted`)[cite: 1].
  - Phát sự kiện qua Redis Pub/Sub kênh `run:{run_id}:events`.
  - **Verification Gate:** Viết và chạy `docker compose exec api pytest tests/test_orchestrator_flow.py -v` PASS 100%.

- [x] **Phase 3.4: 9 API Endpoints Mới & SSE Streaming**
  - Triển khai `/api/v1/models`, `/runs/{id}/cancel`, `/runs/{id}/resume`, `/runs/{id}/events` (SSE), `/runs/{id}/messages`, `/runs/{id}/solutions`, `/runs/{id}/challenges`, `/runs/{id}/report`, `/runs/{id}/usage`[cite: 1].
  - **Verification Gate:** Viết và chạy `docker compose exec api pytest tests/test_api_step3.py -v` PASS 100%.

- [x] **Phase 3.5: Nâng cấp Giao diện Frontend Bước 3 & Hoàn thiện README**
  - Cập nhật `apps/web/` thêm trang `/runs/[id]/page.tsx` kết nối SSE, hiển thị thanh trạng thái trực tiếp, 4 Tabs (Solutions & Claims, Skeptic Challenges, Judge Final Report, Usage & Budget)[cite: 1].
  - Cập nhật `README.md` đầy đủ hướng dẫn kiến trúc, lệnh chạy và kiểm thử[cite: 1].
  - **Verification Gate:** Chạy toàn bộ test suite `docker compose exec api pytest -v` và build Frontend thành công không có lỗi TypeScript.