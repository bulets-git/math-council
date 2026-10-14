import uuid
from typing import Any
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.step3_models import (
    Challenge,
    ChallengeEvent,
    Claim,
    ClaimDependency,
    FinalReport,
    Message,
    Solution,
)
from app.schemas.agent_contracts import ChallengeItem, ClaimItem, JudgeOutput


class DiscussionEngine:
    async def record_message(
        self,
        db: AsyncSession,
        run_id: uuid.UUID,
        sender_role: str,
        content: str,
        recipient_role: str | None = None,
        round_number: int = 1,
        metadata: dict[str, Any] | None = None,
    ) -> Message:
        msg = Message(
            run_id=run_id,
            sender_role=sender_role,
            recipient_role=recipient_role,
            round_number=round_number,
            content=content,
            msg_metadata=metadata or {},
        )
        db.add(msg)
        await db.commit()
        await db.refresh(msg)
        return msg

    async def save_solution_with_claims(
        self,
        db: AsyncSession,
        run_id: uuid.UUID,
        solver_role: str,
        version: int,
        round_number: int,
        summary: str,
        final_answer: str,
        claims_items: list[ClaimItem],
    ) -> Solution:
        solution = Solution(
            run_id=run_id,
            solver_role=solver_role,
            version=version,
            round_number=round_number,
            summary=summary,
            final_answer=final_answer,
        )
        db.add(solution)
        await db.flush()

        claim_label_to_id: dict[str, uuid.UUID] = {}
        claims_to_create: list[Claim] = []

        for item in claims_items:
            c_label = getattr(item, "label", None) or getattr(item, "claim_id", "C1")
            c_content = getattr(item, "content", None) or getattr(item, "statement", "")
            c_type = getattr(item, "claim_type", "inference")
            claim = Claim(
                solution_id=solution.id,
                claim_label=c_label,
                content=c_content,
                claim_type=c_type,
                status="unverified",
            )
            db.add(claim)
            claims_to_create.append(claim)

        await db.flush()

        for c in claims_to_create:
            claim_label_to_id[c.claim_label] = c.id

        # Save claim dependencies
        for item in claims_items:
            c_label = getattr(item, "label", None) or getattr(item, "claim_id", "C1")
            c_id = claim_label_to_id.get(c_label)
            if not c_id:
                continue
            depends = getattr(item, "depends_on", [])
            for dep_label in depends:
                dep_id = claim_label_to_id.get(dep_label)
                if dep_id:
                    dep_record = ClaimDependency(
                        claim_id=c_id,
                        depends_on_claim_id=dep_id,
                        dependency_type="requires",
                    )
                    db.add(dep_record)

        await db.commit()
        await db.refresh(solution)
        return solution

    async def save_challenges(
        self,
        db: AsyncSession,
        run_id: uuid.UUID,
        target_solution_id: uuid.UUID,
        challenges_items: list[ChallengeItem],
        round_number: int = 1,
    ) -> list[Challenge]:
        created: list[Challenge] = []
        for ch in challenges_items:
            record = Challenge(
                run_id=run_id,
                target_solution_id=target_solution_id,
                target_claim_id=None,
                challenger_role="skeptic",
                round_number=round_number,
                error_type=ch.error_type,
                status="open",
                argument=ch.argument,
            )
            db.add(record)
            await db.flush()

            # Record initial challenge event
            event = ChallengeEvent(
                challenge_id=record.id,
                actor_role="skeptic",
                from_status="none",
                to_status="open",
                comment="Phản biện được ghi nhận từ Skeptic",
            )
            db.add(event)
            created.append(record)

        await db.commit()
        return created

    async def save_final_report(
        self,
        db: AsyncSession,
        run_id: uuid.UUID,
        winning_solution_id: uuid.UUID | None,
        judge_output: JudgeOutput,
    ) -> FinalReport:
        report = FinalReport(
            run_id=run_id,
            judge_role="judge",
            consensus_status=judge_output.consensus_status,
            winning_solution_id=winning_solution_id,
            final_latex_solution=judge_output.final_latex_solution,
            executive_summary=judge_output.executive_summary,
            dissenting_opinions=judge_output.dissenting_opinions,
            score=round(judge_output.confidence_score * 10, 2),
        )
        db.add(report)
        await db.commit()
        await db.refresh(report)
        return report


discussion_engine = DiscussionEngine()
