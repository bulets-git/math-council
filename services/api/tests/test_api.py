import uuid
from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.exc import OperationalError

from app.db.session import get_db
from app.main import app
from app.models.problem import Problem
from app.models.run import Run


@pytest.fixture
def mock_db():
    return AsyncMock()


@pytest.fixture
async def client(mock_db):
    app.dependency_overrides[get_db] = lambda: mock_db
    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_health_check_success(client, mock_db):
    mock_db.execute.return_value = None
    response = await client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "database": "connected"}


@pytest.mark.asyncio
async def test_health_check_db_failure(client, mock_db):
    mock_db.execute.side_effect = OperationalError("conn failed", None, None)
    response = await client.get("/health")
    assert response.status_code == 503
    assert response.json() == {"detail": "Database connection error"}


@pytest.mark.asyncio
async def test_create_problem_success(client):
    problem_id = uuid.uuid4()
    now = datetime.now(timezone.utc)
    mock_problem = Problem(
        id=problem_id,
        title="Test Problem",
        statement_original="Solve for x: $x^2 - 4 = 0$",
        input_type="text",
        subject="Algebra",
        difficulty="Easy",
        created_at=now,
        runs=[],
    )
    with patch("app.routes.problems.problem_repo.create", new_callable=AsyncMock) as mock_create:
        mock_create.return_value = mock_problem
        response = await client.post(
            "/api/v1/problems",
            json={
                "title": "Test Problem",
                "statement_original": "Solve for x: $x^2 - 4 = 0$",
                "input_type": "text",
                "subject": "Algebra",
                "difficulty": "Easy",
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert data["id"] == str(problem_id)
        assert data["statement_original"] == "Solve for x: $x^2 - 4 = 0$"


@pytest.mark.asyncio
async def test_create_problem_validation_error_empty_statement(client):
    # Empty string
    response = await client.post(
        "/api/v1/problems",
        json={"statement_original": ""},
    )
    assert response.status_code == 422

    # Whitespace only
    response = await client.post(
        "/api/v1/problems",
        json={"statement_original": "   \n\t  "},
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_list_problems(client):
    p_id = uuid.uuid4()
    now = datetime.now(timezone.utc)
    p = Problem(
        id=p_id,
        title="Prob 1",
        statement_original="Find x",
        input_type="text",
        subject=None,
        difficulty=None,
        created_at=now,
        runs=[
            Run(
                id=uuid.uuid4(),
                problem_id=p_id,
                status="queued",
                config={},
                actual_cost_usd=Decimal("0"),
                created_at=now,
            )
        ],
    )
    with patch("app.routes.problems.problem_repo.get_multi", new_callable=AsyncMock) as mock_get_multi:
        mock_get_multi.return_value = [p]
        response = await client.get("/api/v1/problems")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["id"] == str(p_id)
        assert data[0]["latest_run_status"] == "queued"


@pytest.mark.asyncio
async def test_get_problem_detail_found(client):
    p_id = uuid.uuid4()
    now = datetime.now(timezone.utc)
    p = Problem(
        id=p_id,
        title="Prob 1",
        statement_original="Find x",
        statement_normalized=None,
        input_type="text",
        subject=None,
        difficulty=None,
        created_at=now,
        runs=[],
    )
    with patch("app.routes.problems.problem_repo.get_by_id", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = p
        response = await client.get(f"/api/v1/problems/{p_id}")
        assert response.status_code == 200
        assert response.json()["id"] == str(p_id)


@pytest.mark.asyncio
async def test_get_problem_detail_not_found(client):
    non_existent_id = uuid.uuid4()
    with patch("app.routes.problems.problem_repo.get_by_id", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = None
        response = await client.get(f"/api/v1/problems/{non_existent_id}")
        assert response.status_code == 404


@pytest.mark.asyncio
async def test_create_run_for_problem_success(client):
    p_id = uuid.uuid4()
    run_id = uuid.uuid4()
    now = datetime.now(timezone.utc)
    mock_problem = Problem(id=p_id, statement_original="Find x", created_at=now, runs=[])
    mock_run = Run(
        id=run_id,
        problem_id=p_id,
        status="queued",
        config={"mode": "step2_skeleton"},
        budget_usd=Decimal("1.0"),
        actual_cost_usd=Decimal("0"),
        created_at=now,
    )
    with (
        patch("app.routes.problems.problem_repo.get_by_id", new_callable=AsyncMock) as mock_p_get,
        patch("app.routes.problems.run_repo.create", new_callable=AsyncMock) as mock_run_create,
    ):
        mock_p_get.return_value = mock_problem
        mock_run_create.return_value = mock_run

        response = await client.post(
            f"/api/v1/problems/{p_id}/runs",
            json={"budget_usd": 1.0},
        )
        assert response.status_code == 202
        data = response.json()
        assert data["id"] == str(run_id)
        assert data["status"] == "queued"
        assert data["ai_notice"] == "Chưa chạy AI (Bước 2)"


@pytest.mark.asyncio
async def test_create_run_problem_not_found(client):
    p_id = uuid.uuid4()
    with patch("app.routes.problems.problem_repo.get_by_id", new_callable=AsyncMock) as mock_p_get:
        mock_p_get.return_value = None
        response = await client.post(f"/api/v1/problems/{p_id}/runs", json={})
        assert response.status_code == 404


@pytest.mark.asyncio
async def test_get_run_found(client):
    run_id = uuid.uuid4()
    p_id = uuid.uuid4()
    now = datetime.now(timezone.utc)
    mock_run = Run(
        id=run_id,
        problem_id=p_id,
        status="queued",
        config={},
        budget_usd=Decimal("1.0"),
        actual_cost_usd=Decimal("0"),
        created_at=now,
    )
    with patch("app.routes.runs.run_repo.get_by_id", new_callable=AsyncMock) as mock_r_get:
        mock_r_get.return_value = mock_run
        response = await client.get(f"/api/v1/runs/{run_id}")
        assert response.status_code == 200
        assert response.json()["id"] == str(run_id)


@pytest.mark.asyncio
async def test_get_run_not_found(client):
    run_id = uuid.uuid4()
    with patch("app.routes.runs.run_repo.get_by_id", new_callable=AsyncMock) as mock_r_get:
        mock_r_get.return_value = None
        response = await client.get(f"/api/v1/runs/{run_id}")
        assert response.status_code == 404


@pytest.mark.asyncio
async def test_global_exception_handler_sanitizes_errors(client):
    with patch("app.routes.problems.problem_repo.get_by_id", side_effect=RuntimeError("postgresql://user:secret@db:5432/db leak attempt")):
        response = await client.get(f"/api/v1/problems/{uuid.uuid4()}")
        assert response.status_code == 500
        assert "secret" not in response.text
        assert "RuntimeError" not in response.text
        assert response.json() == {"detail": "Internal server error. Please try again later."}
