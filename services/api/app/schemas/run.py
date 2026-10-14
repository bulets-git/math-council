import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any
from pydantic import BaseModel, ConfigDict, Field, model_validator


class RunCreate(BaseModel):
    config: dict[str, Any] = Field(
        default_factory=lambda: {
            "mode": "step2_skeleton",
            "ai_enabled": False,
            "max_rounds": 2,
            "solvers": ["solver_a", "solver_b"],
        }
    )
    budget_usd: Decimal | None = Field(default=Decimal("1.000000"), ge=Decimal("0"))


class RunResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    problem_id: uuid.UUID
    status: str
    config: dict[str, Any]
    budget_usd: Decimal | None
    actual_cost_usd: Decimal
    created_at: datetime
    ai_notice: str = "Chưa chạy AI (Bước 2)"

    @model_validator(mode="after")
    def compute_ai_notice(self) -> "RunResponse":
        cfg = self.config or {}
        if cfg.get("ai_enabled") and cfg.get("mode") != "step2_skeleton":
            self.ai_notice = "Hội đồng Toán học AI (Bước 3 Multi-Agent)"
        else:
            self.ai_notice = "Chưa chạy AI (Bước 2)"
        return self
