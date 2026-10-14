import json
from pathlib import Path
import pytest
from app.claims.dag_validator import validate_claims_dag
from app.llm_gateway.base_and_adapters import (
    MultiProviderRouter,
    get_available_models_catalog,
)
from app.orchestrator.council_runner import MathCouncilOrchestrator
from app.schemas.agent_contracts import ClaimItemSchema


def test_models_catalog_and_router():
    """Kiểm tra catalog các model đa hãng và định tuyến MultiProviderRouter."""
    catalog = get_available_models_catalog()
    assert len(catalog) >= 5
    providers = {m["provider"] for m in catalog}
    assert "mock" in providers
    assert "gemini" in providers
    assert "openai" in providers

    router = MultiProviderRouter(force_mock=True)
    adapter, model_name = router.resolve_spec("mock:deterministic-olympiad-v1")
    assert adapter.provider_name == "mock"
    assert model_name == "deterministic-olympiad-v1"


def test_dag_circular_dependency_from_benchmark():
    """Kiểm tra kịch bản B07_DAG_CIRCULAR phát hiện chu trình bằng validate_claims_dag."""
    fixture_file = Path(__file__).parent / "fixtures" / "olympiad_benchmark_seed.json"
    assert fixture_file.exists(), "File olympiad_benchmark_seed.json phải tồn tại"

    with open(fixture_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    b07 = next((p for p in data["problems"] if p["code"] == "B07_DAG_CIRCULAR"), None)
    assert b07 is not None

    # Tạo kịch bản chu trình C1 -> C2 -> C3 -> C1
    circular_claims = [
        ClaimItemSchema(claim_id="C1", statement="Mệnh đề 1", reasoning="Suy luận 1", depends_on=["C3"]),
        ClaimItemSchema(claim_id="C2", statement="Mệnh đề 2", reasoning="Suy luận 2", depends_on=["C1"]),
        ClaimItemSchema(claim_id="C3", statement="Mệnh đề 3", reasoning="Suy luận 3", depends_on=["C2"]),
    ]

    res = validate_claims_dag(circular_claims)
    assert not res.is_valid
    assert len(res.cycles) > 0


@pytest.mark.asyncio
async def test_math_council_orchestrator_pipeline():
    """Kiểm tra chạy MathCouncilOrchestrator với MultiProviderRouter (mock)."""
    router = MultiProviderRouter(force_mock=True)
    events_emitted = []

    async def stage_callback(stage: str, payload: dict):
        events_emitted.append(stage)

    orchestrator = MathCouncilOrchestrator(router=router, on_stage_change=stage_callback)
    statement = "Tìm nghiệm nguyên dương của $x^2 + y^2 = z^2$"

    result = await orchestrator.execute_pipeline(statement, max_rounds=1)
    assert result["final_status"] == "completed"
    assert "judge_report" in result
    assert "normalizing" in events_emitted
    assert "solving" in events_emitted
    assert "critiquing" in events_emitted
    assert "adjudicating" in events_emitted
    assert "completed" in events_emitted
    assert float(result["total_cost_usd"]) >= 0
