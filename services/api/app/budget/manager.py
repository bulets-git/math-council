import asyncio
import uuid
from decimal import Decimal
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.run import Run
from app.models.step3_models import ModelCall


class BudgetExhaustedError(Exception):
    """Raised when an operation would exceed the configured run budget."""
    pass


class BudgetManager:
    def __init__(self):
        self._lock = asyncio.Lock()
        self._reservations: dict[uuid.UUID, Decimal] = {}

    def get_reserved_amount(self, run_id: uuid.UUID) -> Decimal:
        return self._reservations.get(run_id, Decimal("0.000000"))

    async def check_and_reserve(
        self,
        db: AsyncSession,
        run_id: uuid.UUID,
        estimated_cost: Decimal = Decimal("0.010000"),
    ) -> Decimal:
        """Atomically checks remaining budget and reserves estimated amount for in-flight calls."""
        async with self._lock:
            run = await db.get(Run, run_id)
            if not run:
                raise ValueError(f"Run '{run_id}' not found.")

            current_reserved = self.get_reserved_amount(run_id)

            if run.budget_usd is not None:
                total_projected = run.actual_cost_usd + current_reserved + estimated_cost
                if total_projected > run.budget_usd:
                    run.status = "budget_exhausted"
                    await db.commit()
                    raise BudgetExhaustedError(
                        f"Ngân sách bị vượt quá: Hiện tại ${run.actual_cost_usd} + "
                        f"Đang giữ ${current_reserved} + Dự kiến ${estimated_cost} > "
                        f"Giới hạn ${run.budget_usd} USD."
                    )

            self._reservations[run_id] = current_reserved + estimated_cost
            return estimated_cost

    async def record_call_and_release(
        self,
        db: AsyncSession,
        run_id: uuid.UUID,
        agent_role: str,
        model_name: str,
        prompt_tokens: int,
        completion_tokens: int,
        actual_cost: Decimal,
        latency_ms: int,
        prompt_version: str,
        reserved_cost: Decimal,
    ) -> ModelCall:
        """Releases the reserved amount, records ModelCall and updates actual_cost_usd."""
        async with self._lock:
            current_reserved = self.get_reserved_amount(run_id)
            self._reservations[run_id] = max(Decimal("0.000000"), current_reserved - reserved_cost)

        run = await db.get(Run, run_id)
        if run:
            run.actual_cost_usd = run.actual_cost_usd + actual_cost

        model_call = ModelCall(
            run_id=run_id,
            agent_role=agent_role,
            model_name=model_name,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=prompt_tokens + completion_tokens,
            cost_usd=actual_cost,
            latency_ms=latency_ms,
            prompt_version=prompt_version,
        )
        db.add(model_call)
        await db.commit()
        await db.refresh(model_call)
        return model_call

    async def release_reservation(self, run_id: uuid.UUID, reserved_cost: Decimal) -> None:
        """Safely releases a reservation if an LLM call failed or was cancelled."""
        async with self._lock:
            current_reserved = self.get_reserved_amount(run_id)
            self._reservations[run_id] = max(Decimal("0.000000"), current_reserved - reserved_cost)


budget_manager = BudgetManager()
