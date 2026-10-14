import uuid
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.run import Run
from app.schemas.run import RunCreate


class RunRepository:
    async def get_by_id(self, db: AsyncSession, run_id: uuid.UUID) -> Run | None:
        stmt = select(Run).where(Run.id == run_id)
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_problem_id(
        self, db: AsyncSession, problem_id: uuid.UUID
    ) -> list[Run]:
        stmt = (
            select(Run)
            .where(Run.problem_id == problem_id)
            .order_by(Run.created_at.desc())
        )
        result = await db.execute(stmt)
        return list(result.scalars().all())

    async def create(
        self, db: AsyncSession, problem_id: uuid.UUID, obj_in: RunCreate
    ) -> Run:
        run = Run(
            problem_id=problem_id,
            status="queued",
            config=obj_in.config,
            budget_usd=obj_in.budget_usd,
        )
        db.add(run)
        await db.commit()
        await db.refresh(run)
        return run


run_repo = RunRepository()
