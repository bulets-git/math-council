import uuid
from datetime import datetime
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, field_validator
from app.schemas.run import RunResponse


class ProblemCreate(BaseModel):
    title: str | None = Field(default=None, max_length=300)
    statement_original: str = Field(..., description="Nội dung đề toán gốc hỗ trợ LaTeX")
    input_type: Literal["text", "image", "mixed"] = "text"
    subject: str | None = Field(default=None)
    difficulty: str | None = Field(default=None)

    @field_validator("statement_original")
    @classmethod
    def validate_not_blank(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("Đề toán không được để trống hoặc chỉ chứa khoảng trắng.")
        return v

    @field_validator("title")
    @classmethod
    def normalize_title(cls, v: str | None) -> str | None:
        if v is not None:
            stripped = v.strip()
            return stripped if stripped else None
        return None


class ProblemSummaryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str | None
    statement_original: str
    input_type: str
    subject: str | None
    difficulty: str | None
    created_at: datetime
    latest_run_status: str | None = None


class ProblemDetailResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str | None
    statement_original: str
    statement_normalized: str | None
    input_type: str
    subject: str | None
    difficulty: str | None
    created_at: datetime
    runs: list[RunResponse] = Field(default_factory=list)
