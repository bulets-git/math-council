from decimal import Decimal
import pytest
from sqlalchemy import select

from app.events.publisher import event_publisher
from app.llm_gateway.base_and_adapters import MultiProviderRouter
from app.models.problem import Problem
from app.models.run import Run
from app.models.step3_models import FinalReport, Solution
from app.orchestrator.council_runner import CouncilRunner
from app.orchestrator.state_machine import council_orchestrator


@pytest.mark.asyncio
async def test_source_discovery_exact_match_fast_track(test_session_maker):
    """Test 1: Bài toán IMO 1959 Problem 1 (21n+4 và 14n+3)
    -> phát hiện exact_match -> kích hoạt fast-track
    -> verify report cuối cùng có trích dẫn nguồn gốc và điểm số.
    """
    event_publisher.clear_events()

    async with test_session_maker() as db:
        problem = Problem(
            title="Bài toán phân số tối giản IMO 1959",
            statement_original="Chứng minh rằng phân số $\\frac{21n + 4}{14n + 3}$ tối giản với mọi số tự nhiên $n$.",
            subject="Số học",
            difficulty="Olympic",
            runs=[],
        )
        db.add(problem)
        await db.commit()

        run = Run(
            problem_id=problem.id,
            status="queued",
            budget_usd=Decimal("1.000000"),
            actual_cost_usd=Decimal("0.000000"),
            config={},
        )
        db.add(run)
        await db.commit()
        run_id = run.id

        # Thực thi pipeline State Machine
        status = await council_orchestrator.run_pipeline(db, run_id)
        assert status == "completed"

        await db.refresh(run)
        assert run.status == "completed"

        # Kiểm tra run.config chứa discovered_source với exact_match
        discovered_source = run.config.get("discovered_source")
        assert discovered_source is not None
        assert discovered_source["match_type"] == "exact_match"
        assert discovered_source["source_found"] is True

        source_meta = discovered_source.get("source_metadata")
        assert source_meta is not None
        assert "IMO" in source_meta["competition_name"]
        assert source_meta["year"] == 1959
        assert "1" in source_meta["problem_number"]
        assert any("artofproblemsolving.com" in url for url in source_meta.get("reference_urls", []))

        # Kiểm tra Solutions: Phải có giải pháp canonical_source được lưu
        stmt_sol = select(Solution).where(Solution.run_id == run_id)
        res_sol = await db.execute(stmt_sol)
        solutions = res_sol.scalars().all()
        assert len(solutions) >= 1
        assert any(s.solver_role == "canonical_source" for s in solutions)

        # Kiểm tra FinalReport có trích dẫn nguồn gốc và điểm số
        stmt_rep = select(FinalReport).where(FinalReport.run_id == run_id)
        res_rep = await db.execute(stmt_rep)
        report = res_rep.scalar_one_or_none()
        assert report is not None
        assert report.score is not None and report.score > Decimal("0")
        assert "IMO" in report.final_latex_solution or "1959" in report.final_latex_solution
        assert "IMO" in report.executive_summary

        # Kiểm tra các sự kiện SSE phát ra
        events = event_publisher.get_published_events(run_id)
        event_types = [e["event_type"] for e in events]
        assert "source_discovered" in event_types
        assert "status_changed" in event_types


@pytest.mark.asyncio
async def test_source_discovery_no_match_standard_pipeline(test_session_maker):
    """Test 2: Bài toán tự chế không có trên mạng
    -> phát hiện no_match -> pipeline chạy bình thường qua các solver.
    """
    event_publisher.clear_events()

    async with test_session_maker() as db:
        problem = Problem(
            title="Phương trình bậc hai tự tạo",
            statement_original="Tìm nghiệm thực của phương trình $x^2 + 5x + 6 = 0$.",
            subject="Đại số",
            difficulty="Cơ bản",
            runs=[],
        )
        db.add(problem)
        await db.commit()

        run = Run(
            problem_id=problem.id,
            status="queued",
            budget_usd=Decimal("1.000000"),
            actual_cost_usd=Decimal("0.000000"),
            config={},
        )
        db.add(run)
        await db.commit()
        run_id = run.id

        # Thực thi pipeline State Machine
        status = await council_orchestrator.run_pipeline(db, run_id)
        assert status == "completed"

        await db.refresh(run)
        assert run.status == "completed"

        # Kiểm tra run.config chứa discovered_source với no_match
        discovered_source = run.config.get("discovered_source")
        assert discovered_source is not None
        assert discovered_source["match_type"] == "no_match"
        assert discovered_source["source_found"] is False
        assert discovered_source["source_metadata"] is None

        # Kiểm tra Solutions: chạy qua Solver A & B bình thường
        stmt_sol = select(Solution).where(Solution.run_id == run_id)
        res_sol = await db.execute(stmt_sol)
        solutions = res_sol.scalars().all()
        roles = {s.solver_role for s in solutions}
        assert "solver_a" in roles
        assert "solver_b" in roles
        assert "canonical_source" not in roles

        # Kiểm tra FinalReport bình thường
        stmt_rep = select(FinalReport).where(FinalReport.run_id == run_id)
        res_rep = await db.execute(stmt_rep)
        report = res_rep.scalar_one_or_none()
        assert report is not None
        assert report.consensus_status in ["consensus_reached", "deadlock"]


@pytest.mark.asyncio
async def test_council_runner_source_discovery_direct():
    """Kiểm tra CouncilRunner trực tiếp với MultiProviderRouter cho cả 2 trường hợp exact_match và no_match."""
    router = MultiProviderRouter()
    runner = CouncilRunner(router=router, fast_track_known_problems=True)

    # 1. Trường hợp exact_match IMO 1959
    result_imo = await runner.run(
        "Chứng minh rằng phân số $\\frac{21n + 4}{14n + 3}$ là tối giản với mọi $n$."
    )
    assert result_imo["final_status"] == "completed"
    assert result_imo["fast_track_applied"] is True
    assert result_imo["discovered_source"]["match_type"] == "exact_match"
    assert "IMO" in result_imo["discovered_source"]["source_metadata"]["competition_name"]
    assert result_imo["judge_report"] is not None

    # 2. Trường hợp no_match
    result_custom = await runner.run("Giải phương trình $3x - 9 = 0$.")
    assert result_custom["final_status"] == "completed"
    assert result_custom["fast_track_applied"] is False
    assert result_custom["discovered_source"]["match_type"] == "no_match"
