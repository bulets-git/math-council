import uuid
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.repositories.problem_repo import problem_repo
from app.repositories.run_repo import run_repo
from app.schemas.problem import ProblemCreate, ProblemDetailResponse, ProblemSummaryResponse
from app.schemas.run import RunCreate, RunResponse

router = APIRouter(prefix="/problems", tags=["problems"])


@router.post(
    "",
    response_model=ProblemDetailResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Tạo bài toán mới",
)
async def create_problem(
    problem_in: ProblemCreate,
    db: AsyncSession = Depends(get_db),
) -> ProblemDetailResponse:
    problem = await problem_repo.create(db, problem_in)
    return problem


@router.get(
    "",
    response_model=list[ProblemSummaryResponse],
    status_code=status.HTTP_200_OK,
    summary="Danh sách bài toán mới nhất trước kèm latest_run_status",
)
async def list_problems(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
) -> list[ProblemSummaryResponse]:
    problems = await problem_repo.get_multi(db, skip=skip, limit=limit)
    return [
        ProblemSummaryResponse(
            id=p.id,
            title=p.title,
            statement_original=p.statement_original,
            input_type=p.input_type,
            subject=p.subject,
            difficulty=p.difficulty,
            created_at=p.created_at,
            latest_run_status=p.runs[0].status if p.runs else None,
        )
        for p in problems
    ]


@router.get(
    "/{problem_id}",
    response_model=ProblemDetailResponse,
    status_code=status.HTTP_200_OK,
    summary="Chi tiết bài toán kèm lịch sử các run",
)
async def get_problem(
    problem_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> ProblemDetailResponse:
    problem = await problem_repo.get_by_id(db, problem_id)
    if not problem:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Problem with id '{problem_id}' not found.",
        )
    return problem


@router.post(
    "/{problem_id}/runs",
    response_model=RunResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Tạo một phiên giải toán (Run) ở trạng thái queued",
)
async def create_run_for_problem(
    problem_id: uuid.UUID,
    run_in: RunCreate | None = None,
    db: AsyncSession = Depends(get_db),
) -> RunResponse:
    problem = await problem_repo.get_by_id(db, problem_id)
    if not problem:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Problem with id '{problem_id}' not found.",
        )
    if run_in is None:
        run_in = RunCreate()
    run = await run_repo.create(db, problem_id=problem_id, obj_in=run_in)
    return run
