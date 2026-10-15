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
    assert "alibaba" in providers
    assert "deepseek" in providers
    assert "deepinfra" in providers

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
    # Solver C is configured and included in pipeline
    assert "solver_c_final" in result
    assert result["dag_validation"]["solver_c_valid"] is True


def test_prompts_anti_hallucination_and_domain_rules():
    """Kiểm tra các chỉ dẫn chống ảo giác và phân môn trong prompts."""
    from app.prompts.math_council_prompts import (
        NORMALIZER_PROMPT_V1,
        SOLVER_PROMPT_V1,
        SKEPTIC_PROMPT_V1,
    )
    # Normalizer phân loại phân môn và bắt buộc 'Tổ hợp / Toán rời rạc' cho bàn cờ
    norm_sys = NORMALIZER_PROMPT_V1.system_instruction
    assert "detected_subject" in norm_sys
    assert "Tổ hợp / Toán rời rạc" in norm_sys
    assert "bàn cờ" in norm_sys

    # Solver cấm định lý hình học liên tục cho bài toán rời rạc
    solver_sys = SOLVER_PROMPT_V1.system_instruction
    assert "đối tượng toán học" in solver_sys
    assert "hình học liên tục" in solver_sys
    assert "Dirichlet" in solver_sys or "Pigeonhole" in solver_sys
    assert "phân hoạch đường chéo" in solver_sys

    # Skeptic bắt buộc tạo critical challenge invalid_inference nếu dùng sai công cụ lý thuyết
    skeptic_sys = SKEPTIC_PROMPT_V1.system_instruction
    assert "severity='critical'" in skeptic_sys
    assert "error_type='invalid_inference'" in skeptic_sys


def test_strict_no_mock_fallback_in_live_mode(monkeypatch):
    """Kiểm tra khi DEFAULT_LLM_PROVIDER == 'live', cấm tuyệt đối fallback ngầm về Mock Adapter."""
    from app.core.config import settings
    from app.llm_gateway.factory import get_llm_adapter

    monkeypatch.setattr(settings, "DEFAULT_LLM_PROVIDER", "live")

    # Gọi với model không xác định phải văng ValueError, không được trả về DeterministicMockAdapter
    with pytest.raises(ValueError, match="Tuyệt đối cấm fallback ngầm về Mock Adapter"):
        get_llm_adapter("unknown-custom-model-xyz")

    # Kiểm tra solver_c model trong config là model Gemini chuẩn
    assert "gemini" in settings.ROLE_SOLVER_C_MODEL
