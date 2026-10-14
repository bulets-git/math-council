import uuid
from decimal import Decimal
from unittest.mock import AsyncMock, patch
import pytest
from sqlalchemy import select

from app.events.publisher import event_publisher
from app.models.problem import Problem
from app.models.run import Run
from app.models.step3_models import Challenge, FinalReport, Solution
from app.orchestrator.state_machine import council_orchestrator
from app.schemas.agent_contracts import NormalizerOutput


@pytest.mark.asyncio
async def test_full_orchestrator_flow(test_session_maker):
    """Kiểm tra toàn bộ luồng hội đồng từ queued -> completed:

    queued -> normalizing -> solving -> critiquing -> revising -> adjudicating -> completed.
    """
    event_publisher.clear_events()

    async with test_session_maker() as db:
        problem = Problem(
            title="Định lý Pythagoras",
            statement_original="Cho tam giác vuông có hai cạnh góc vuông $a=3, b=4$. Tính cạnh huyền $c$.",
            subject="Hình học",
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
        )
        db.add(run)
        await db.commit()
        run_id = run.id

        # Thực thi pipeline
        status = await council_orchestrator.run_pipeline(db, run_id)
        assert status == "completed"

        await db.refresh(run)
        assert run.status == "completed"
        assert run.actual_cost_usd > Decimal("0.000000")

        # Kiểm tra Solutions (phải có phiên bản 1 của Solver A & B, và phiên bản 2 sau khi sửa đổi)
        stmt_sol = select(Solution).where(Solution.run_id == run_id)
        res_sol = await db.execute(stmt_sol)
        solutions = res_sol.scalars().all()
        assert len(solutions) >= 3

        # Kiểm tra Challenges
        stmt_ch = select(Challenge).where(Challenge.run_id == run_id)
        res_ch = await db.execute(stmt_ch)
        challenges = res_ch.scalars().all()
        assert len(challenges) >= 1

        # Kiểm tra FinalReport
        stmt_rep = select(FinalReport).where(FinalReport.run_id == run_id)
        res_rep = await db.execute(stmt_rep)
        report = res_rep.scalar_one_or_none()
        assert report is not None
        assert report.consensus_status == "consensus_reached"

        # Kiểm tra các sự kiện được phát đi
        events = event_publisher.get_published_events(run_id)
        event_types = [e["event_type"] for e in events]
        assert "status_changed" in event_types
        assert "solutions_generated" in event_types
        assert "challenges_raised" in event_types
        assert "solution_revised" in event_types
        assert "run_completed" in event_types


@pytest.mark.asyncio
async def test_normalizer_ambiguity_needs_review_and_resume(test_session_maker):
    """Kiểm tra khi Normalizer phát hiện đề mơ hồ -> chuyển 'needs_review' và dừng lại đợi resume."""
    event_publisher.clear_events()

    async with test_session_maker() as db:
        problem = Problem(
            title="Đề thiếu dữ kiện",
            statement_original="Tìm x biết $x + y = 10$",
            runs=[],
        )
        db.add(problem)
        await db.commit()

        run = Run(
            problem_id=problem.id,
            status="queued",
            budget_usd=Decimal("1.000000"),
        )
        db.add(run)
        await db.commit()
        run_id = run.id

        ambiguous_output = NormalizerOutput(
            normalized_statement="Tìm x biết $x + y = 10$",
            assumptions=[],
            extracted_variables={"x": "ẩn 1", "y": "ẩn 2"},
            has_ambiguity=True,
            ambiguity_warning="Phương trình 2 ẩn nhưng chỉ có 1 phương trình, thiếu dữ kiện về y.",
        )

        with patch("app.llm_gateway.mock_adapter.DeterministicMockAdapter.generate") as mock_gen:
            mock_res = AsyncMock()
            mock_res.parsed_json = ambiguous_output.model_dump()
            mock_res.prompt_tokens = 50
            mock_res.completion_tokens = 50
            mock_res.cost_usd = Decimal("0.001000")
            mock_res.latency_ms = 100
            mock_gen.return_value = mock_res

            # Chạy pipeline -> phải dừng ở 'needs_review'
            status = await council_orchestrator.run_pipeline(db, run_id)
            assert status == "needs_review"

            await db.refresh(run)
            assert run.status == "needs_review"

        # Gọi resume_run để tiếp tục sang solving -> completed
        resumed_status = await council_orchestrator.resume_run(db, run_id)
        assert resumed_status == "completed"

        await db.refresh(run)
        assert run.status == "completed"


@pytest.mark.asyncio
async def test_cancel_run_orchestrator(test_session_maker):
    """Kiểm tra chức năng hủy phiên chạy (cancel)."""
    async with test_session_maker() as db:
        p = Problem(statement_original="Tính $1+1$", runs=[])
        db.add(p)
        await db.commit()

        run = Run(problem_id=p.id, status="queued")
        db.add(run)
        await db.commit()

        cancelled_run = await council_orchestrator.cancel_run(db, run.id)
        assert cancelled_run.status == "cancelled"


@pytest.mark.asyncio
async def test_budget_exhaustion_in_orchestrator(test_session_maker):
    """Kiểm tra khi ngân sách cực thấp -> chuyển trạng thái 'budget_exhausted'."""
    async with test_session_maker() as db:
        p = Problem(statement_original="Tìm x", runs=[])
        db.add(p)
        await db.commit()

        # Ngân sách 0.000001 USD không đủ cho bất kỳ lời gọi nào
        run = Run(
            problem_id=p.id,
            status="queued",
            budget_usd=Decimal("0.000001"),
        )
        db.add(run)
        await db.commit()

        status = await council_orchestrator.run_pipeline(db, run.id)
        assert status == "budget_exhausted"

        await db.refresh(run)
        assert run.status == "budget_exhausted"
