import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any
from pydantic import BaseModel, ConfigDict, Field


class ModelInfoResponse(BaseModel):
    id: str
    name: str
    provider: str
    context_window: int = 128000
    is_default: bool = False


class MessageResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    run_id: uuid.UUID
    sender_role: str
    recipient_role: str | None = None
    round_number: int
    content: str
    metadata: dict[str, Any] = Field(default_factory=dict, validation_alias="msg_metadata", serialization_alias="metadata")
    created_at: datetime


class ClaimResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    solution_id: uuid.UUID
    claim_label: str
    content: str
    claim_type: str | None = None
    status: str
    created_at: datetime
    depends_on: list[str] = Field(default_factory=list)


class SolutionDetailResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    run_id: uuid.UUID
    solver_role: str
    version: int
    round_number: int
    final_answer: str | None = None
    summary: str | None = None
    created_at: datetime
    claims: list[ClaimResponse] = Field(default_factory=list)


class ChallengeEventResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    challenge_id: uuid.UUID
    actor_role: str
    from_status: str
    to_status: str
    comment: str | None = None
    created_at: datetime


class ChallengeResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    run_id: uuid.UUID
    target_solution_id: uuid.UUID
    target_claim_id: uuid.UUID | None = None
    challenger_role: str
    round_number: int
    error_type: str
    status: str
    argument: str
    created_at: datetime
    events: list[ChallengeEventResponse] = Field(default_factory=list)


class FinalReportResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    run_id: uuid.UUID
    judge_role: str
    consensus_status: str
    winning_solution_id: uuid.UUID | None = None
    final_latex_solution: str
    executive_summary: str
    dissenting_opinions: list[str] = Field(default_factory=list)
    score: Decimal | None = None
    created_at: datetime


class ModelCallResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    run_id: uuid.UUID
    agent_role: str
    model_name: str
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    cost_usd: Decimal
    latency_ms: int
    prompt_version: str
    created_at: datetime


class UsageSummaryResponse(BaseModel):
    run_id: uuid.UUID
    total_calls: int
    total_prompt_tokens: int
    total_completion_tokens: int
    total_tokens: int
    total_cost_usd: Decimal
    calls: list[ModelCallResponse] = Field(default_factory=list)
