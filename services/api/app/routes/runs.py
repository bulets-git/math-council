import asyncio
import json
import uuid
from decimal import Decimal
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.session import get_db
from app.events.publisher import event_publisher
from app.models.step3_models import (
    Challenge,
    Claim,
    ClaimDependency,
    FinalReport,
    Message,
    ModelCall,
    Solution,
)
from app.orchestrator.state_machine import council_orchestrator
from app.repositories.run_repo import run_repo
from app.schemas.run import RunResponse
from app.schemas.step3_schemas import (
    ChallengeEventResponse,
    ChallengeResponse,
    ClaimResponse,
    FinalReportResponse,
    MessageResponse,
    ModelCallResponse,
    SolutionDetailResponse,
    UsageSummaryResponse,
)

router = APIRouter(prefix="/runs", tags=["runs"])


@router.get(
    "/{run_id}",
    response_model=RunResponse,
    status_code=status.HTTP_200_OK,
    summary="Chi tiết một phiên giải toán (Run)",
)
async def get_run(
    run_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> RunResponse:
    run = await run_repo.get_by_id(db, run_id)
    if not run:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Run with id '{run_id}' not found.",
        )
    return run


@router.post(
    "/{run_id}/cancel",
    response_model=RunResponse,
    status_code=status.HTTP_200_OK,
    summary="Hủy phiên giải toán đang chạy",
)
async def cancel_run(
    run_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> RunResponse:
    try:
        run = await council_orchestrator.cancel_run(db, run_id)
        return run
    except ValueError as err:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(err))


@router.post(
    "/{run_id}/resume",
    response_model=RunResponse,
    status_code=status.HTTP_200_OK,
    summary="Tiếp tục phiên giải toán đang ở trạng thái needs_review",
)
async def resume_run(
    run_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> RunResponse:
    run = await run_repo.get_by_id(db, run_id)
    if not run:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Run '{run_id}' not found.")
    if run.status != "needs_review":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Chỉ có thể tiếp tục run ở trạng thái 'needs_review', hiện tại là '{run.status}'.",
        )
    await council_orchestrator.resume_run(db, run_id)
    await db.refresh(run)
    return run


@router.get(
    "/{run_id}/events",
    summary="Stream Server-Sent Events (SSE) theo dõi tiến trình của Run",
)
async def stream_run_events(
    run_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    run = await run_repo.get_by_id(db, run_id)
    if not run:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Run '{run_id}' not found.")

    async def event_generator():
        # Gửi lại toàn bộ sự kiện đã phát trước đó
        past_events = event_publisher.get_published_events(run_id)
        for evt in past_events:
            yield f"data: {json.dumps(evt, ensure_ascii=False)}\n\n"

        if run.status in ["completed", "failed", "cancelled"]:
            return

        r = await event_publisher.get_redis()
        if r:
            pubsub = r.pubsub()
            await pubsub.subscribe(f"run:{run_id}:events")
            try:
                while True:
                    try:
                        message = await asyncio.wait_for(
                            pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0),
                            timeout=15.0,
                        )
                        if message and message.get("type") == "message":
                            yield f"data: {message['data']}\n\n"
                            try:
                                parsed = json.loads(message["data"])
                                if parsed.get("event_type") in ["run_completed", "run_failed", "run_cancelled"]:
                                    break
                            except Exception:
                                pass
                    except asyncio.TimeoutError:
                        # Heartbeat ping every 15s to keep SSE connection alive through Railway proxy
                        yield ": ping\n\n"
            finally:
                await pubsub.unsubscribe(f"run:{run_id}:events")
        else:
            # Fallback when Redis is not available: send heartbeat until completed or disconnected
            yield ": ping\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Content-Type": "text/event-stream",
            "Cache-Control": "no-cache, no-transform",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get(
    "/{run_id}/messages",
    response_model=list[MessageResponse],
    summary="Lịch sử các lượt trao đổi / prompt trong phiên giải toán",
)
async def get_run_messages(
    run_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> list[MessageResponse]:
    run = await run_repo.get_by_id(db, run_id)
    if not run:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Run '{run_id}' not found.")

    stmt = select(Message).where(Message.run_id == run_id).order_by(Message.round_number.asc(), Message.created_at.asc())
    result = await db.execute(stmt)
    return list(result.scalars().all())


@router.get(
    "/{run_id}/solutions",
    response_model=list[SolutionDetailResponse],
    summary="Danh sách các phiên bản lời giải (kèm claims và dependencies)",
)
async def get_run_solutions(
    run_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> list[SolutionDetailResponse]:
    run = await run_repo.get_by_id(db, run_id)
    if not run:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Run '{run_id}' not found.")

    stmt = (
        select(Solution)
        .where(Solution.run_id == run_id)
        .options(selectinload(Solution.claims))
        .order_by(Solution.version.asc(), Solution.created_at.asc())
    )
    result = await db.execute(stmt)
    solutions = result.scalars().all()

    # Build claim dependencies map
    stmt_deps = select(ClaimDependency)
    res_deps = await db.execute(stmt_deps)
    deps_records = res_deps.scalars().all()

    # Map claim_id to label
    all_claims = {c.id: c.claim_label for s in solutions for c in s.claims}
    claim_deps_map: dict[uuid.UUID, list[str]] = {}
    for d in deps_records:
        if d.claim_id in all_claims and d.depends_on_claim_id in all_claims:
            claim_deps_map.setdefault(d.claim_id, []).append(all_claims[d.depends_on_claim_id])

    response_list: list[SolutionDetailResponse] = []
    for s in solutions:
        claims_resp = [
            ClaimResponse(
                id=c.id,
                solution_id=c.solution_id,
                claim_label=c.claim_label,
                content=c.content,
                claim_type=c.claim_type,
                status=c.status,
                created_at=c.created_at,
                depends_on=claim_deps_map.get(c.id, []),
            )
            for c in s.claims
        ]
        response_list.append(
            SolutionDetailResponse(
                id=s.id,
                run_id=s.run_id,
                solver_role=s.solver_role,
                version=s.version,
                round_number=s.round_number,
                final_answer=s.final_answer,
                summary=s.summary,
                created_at=s.created_at,
                claims=claims_resp,
            )
        )
    return response_list


@router.get(
    "/{run_id}/challenges",
    response_model=list[ChallengeResponse],
    summary="Danh sách các phản biện từ Skeptic và lịch sử challenge_events",
)
async def get_run_challenges(
    run_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> list[ChallengeResponse]:
    run = await run_repo.get_by_id(db, run_id)
    if not run:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Run '{run_id}' not found.")

    stmt = (
        select(Challenge)
        .where(Challenge.run_id == run_id)
        .options(selectinload(Challenge.events))
        .order_by(Challenge.created_at.asc())
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())


@router.get(
    "/{run_id}/report",
    response_model=FinalReportResponse,
    summary="Báo cáo phán quyết tổng hợp cuối cùng của Chief Judge",
)
async def get_run_report(
    run_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> FinalReportResponse:
    run = await run_repo.get_by_id(db, run_id)
    if not run:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Run '{run_id}' not found.")

    stmt = select(FinalReport).where(FinalReport.run_id == run_id)
    result = await db.execute(stmt)
    report = result.scalar_one_or_none()
    if not report:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Chưa có báo cáo tổng hợp cho run '{run_id}'.",
        )
    return report


@router.get(
    "/{run_id}/usage",
    response_model=UsageSummaryResponse,
    summary="Thống kê chi tiết token, độ trễ và chi phí từ model_calls",
)
async def get_run_usage(
    run_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> UsageSummaryResponse:
    run = await run_repo.get_by_id(db, run_id)
    if not run:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Run '{run_id}' not found.")

    stmt = select(ModelCall).where(ModelCall.run_id == run_id).order_by(ModelCall.created_at.asc())
    result = await db.execute(stmt)
    calls = list(result.scalars().all())

    total_prompt = sum(c.prompt_tokens for c in calls)
    total_comp = sum(c.completion_tokens for c in calls)
    total_tokens = sum(c.total_tokens for c in calls)
    total_cost = sum((c.cost_usd for c in calls), Decimal("0.000000"))

    return UsageSummaryResponse(
        run_id=run_id,
        total_calls=len(calls),
        total_prompt_tokens=total_prompt,
        total_completion_tokens=total_comp,
        total_tokens=total_tokens,
        total_cost_usd=total_cost,
        calls=[ModelCallResponse.model_validate(c) for c in calls],
    )
