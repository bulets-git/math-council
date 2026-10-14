import uuid
from decimal import Decimal
import pytest
from httpx import AsyncClient

from app.models.problem import Problem
from app.models.run import Run
from app.orchestrator.state_machine import council_orchestrator


@pytest.mark.asyncio
async def test_get_models_list(client: AsyncClient):
    """GET /api/v1/models trả về danh sách các model đã cấu hình."""
    response = await client.get("/api/v1/models")
    assert response.status_code == 200
    models = response.json()
    assert len(models) >= 1
    assert any(m["id"] == "mock-math-council" for m in models)


@pytest.mark.asyncio
async def test_cancel_run_endpoint(client: AsyncClient, test_session_maker):
    """POST /api/v1/runs/{id}/cancel chuyển trạng thái sang cancelled."""
    async with test_session_maker() as db:
        p = Problem(statement_original="Tính $e^{i\\pi} + 1 = 0$", runs=[])
        db.add(p)
        await db.commit()

        run = Run(problem_id=p.id, status="queued")
        db.add(run)
        await db.commit()
        run_id = str(run.id)

    response = await client.post(f"/api/v1/runs/{run_id}/cancel")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "cancelled"


@pytest.mark.asyncio
async def test_resume_run_endpoint(client: AsyncClient, test_session_maker):
    """POST /api/v1/runs/{id}/resume tiếp tục chạy khi run đang ở needs_review."""
    async with test_session_maker() as db:
        p = Problem(statement_original="Đề cần làm rõ", statement_normalized="Đề chuẩn hóa", runs=[])
        db.add(p)
        await db.commit()

        run = Run(problem_id=p.id, status="needs_review", budget_usd=Decimal("1.0"))
        db.add(run)
        await db.commit()
        run_id = str(run.id)

    # 1. Gọi resume
    response = await client.post(f"/api/v1/runs/{run_id}/resume")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "completed"

    # 2. Gọi resume lại khi đã completed -> 400 Bad Request
    res_invalid = await client.post(f"/api/v1/runs/{run_id}/resume")
    assert res_invalid.status_code == 400


@pytest.mark.asyncio
async def test_run_events_sse_endpoint(client: AsyncClient, test_session_maker):
    """GET /api/v1/runs/{id}/events trả về SSE stream."""
    async with test_session_maker() as db:
        p = Problem(statement_original="Tính $2+2$", runs=[])
        db.add(p)
        await db.commit()

        run = Run(problem_id=p.id, status="completed")
        db.add(run)
        await db.commit()
        run_id = str(run.id)

    response = await client.get(f"/api/v1/runs/{run_id}/events")
    assert response.status_code == 200
    assert "text/event-stream" in response.headers.get("content-type", "")


@pytest.mark.asyncio
async def test_step3_data_endpoints(client: AsyncClient, test_session_maker):
    """Kiểm tra các endpoints đọc dữ liệu sau khi chạy pipeline:

    /messages, /solutions, /challenges, /report, /usage.
    """
    async with test_session_maker() as db:
        p = Problem(statement_original="Tính tổng cấp số cộng $S = 1 + 2 + ... + 100$", runs=[])
        db.add(p)
        await db.commit()

        run = Run(problem_id=p.id, status="queued", budget_usd=Decimal("1.000000"))
        db.add(run)
        await db.commit()
        run_id = run.id

        # Cho pipeline chạy hoàn tất
        await council_orchestrator.run_pipeline(db, run_id)

    str_id = str(run_id)

    # 1. GET /runs/{id}/messages
    res_msg = await client.get(f"/api/v1/runs/{str_id}/messages")
    assert res_msg.status_code == 200
    messages = res_msg.json()
    assert len(messages) >= 1
    assert messages[0]["sender_role"] == "normalizer"

    # 2. GET /runs/{id}/solutions
    res_sol = await client.get(f"/api/v1/runs/{str_id}/solutions")
    assert res_sol.status_code == 200
    solutions = res_sol.json()
    assert len(solutions) >= 3
    # Mỗi solution có claims
    assert len(solutions[0]["claims"]) >= 1

    # 3. GET /runs/{id}/challenges
    res_ch = await client.get(f"/api/v1/runs/{str_id}/challenges")
    assert res_ch.status_code == 200
    challenges = res_ch.json()
    assert len(challenges) >= 1
    assert challenges[0]["challenger_role"] == "skeptic"
    assert len(challenges[0]["events"]) >= 1

    # 4. GET /runs/{id}/report
    res_rep = await client.get(f"/api/v1/runs/{str_id}/report")
    assert res_rep.status_code == 200
    report = res_rep.json()
    assert report["consensus_status"] == "consensus_reached"
    assert "final_latex_solution" in report

    # 5. GET /runs/{id}/usage
    res_usage = await client.get(f"/api/v1/runs/{str_id}/usage")
    assert res_usage.status_code == 200
    usage = res_usage.json()
    assert usage["total_calls"] >= 4
    assert usage["total_tokens"] > 0
    assert float(usage["total_cost_usd"]) > 0


@pytest.mark.asyncio
async def test_non_existent_run_endpoints_404(client: AsyncClient):
    """Kiểm tra gọi các endpoint mới với UUID ngẫu nhiên không tồn tại -> 404."""
    random_id = str(uuid.uuid4())
    assert (await client.post(f"/api/v1/runs/{random_id}/cancel")).status_code == 404
    assert (await client.post(f"/api/v1/runs/{random_id}/resume")).status_code == 404
    assert (await client.get(f"/api/v1/runs/{random_id}/events")).status_code == 404
    assert (await client.get(f"/api/v1/runs/{random_id}/messages")).status_code == 404
    assert (await client.get(f"/api/v1/runs/{random_id}/solutions")).status_code == 404
    assert (await client.get(f"/api/v1/runs/{random_id}/challenges")).status_code == 404
    assert (await client.get(f"/api/v1/runs/{random_id}/report")).status_code == 404
    assert (await client.get(f"/api/v1/runs/{random_id}/usage")).status_code == 404
