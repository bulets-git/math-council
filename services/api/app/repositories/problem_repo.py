import uuid
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.problem import Problem
from app.schemas.problem import ProblemCreate


class ProblemRepository:
    async def get_by_id(self, db: AsyncSession, problem_id: uuid.UUID) -> Problem | None:
        stmt = (
            select(Problem)
            .options(selectinload(Problem.runs))
            .where(Problem.id == problem_id)
        )
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_multi(
        self, db: AsyncSession, skip: int = 0, limit: int = 100
    ) -> list[Problem]:
        stmt = (
            select(Problem)
            .options(selectinload(Problem.runs))
            .order_by(Problem.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        result = await db.execute(stmt)
        return list(result.scalars().all())

    async def create(self, db: AsyncSession, obj_in: ProblemCreate) -> Problem:
        problem = Problem(
            title=obj_in.title,
            statement_original=obj_in.statement_original,
            input_type=obj_in.input_type,
            subject=obj_in.subject,
            difficulty=obj_in.difficulty,
        )
        db.add(problem)
        await db.commit()
        refreshed = await self.get_by_id(db, problem.id)
        return refreshed if refreshed is not None else problem


problem_repo = ProblemRepository()
