import json
import os
import shutil
import zipfile

# ==============================================================================
# 1. DỮ LIỆU BENCHMARK TOÁN OLYMPIC & BẪY NGỤY BIỆN (10 KỊCH BẢN)
# ==============================================================================
BENCHMARK_DATA = {
    "version": "1.0",
    "description": "Bộ dữ liệu kiểm thử Toán HSG/Olympiad & Bẫy ngụy biện cho Math Council",
    "problems": [
        {
            "code": "B01_FE_MISSING_CASE",
            "title": "Phương trình hàm hiệu bình phương (Bẫy chia cho 0)",
            "subject": "Đại số & Giải tích",
            "difficulty": "VMO / Quốc gia",
            "input_type": "text",
            "statement_original": "Tìm tất cả các hàm số $f: \\mathbb{R} \\to \\mathbb{R}$ thỏa mãn:\n$$f(x^2 - y^2) = x f(x) - y f(y), \\quad \\forall x, y \\in \\mathbb{R}$$",
            "mock_scenario": "fallacious_missing_case",
            "expected_skeptic_challenge": {
                "target_claim_id": "C3",
                "error_type": "missing_case",
                "severity": "critical",
                "explanation": "Chia hai vế cho $(f(x) - x)$ khi chưa xét trường hợp biểu thức này bằng 0. Thực tế mọi hàm $f(x) = kx$ đều thỏa mãn."
            }
        },
        {
            "code": "B02_NT_INVALID_LTE",
            "title": "Phương trình mũ Diophantine (Bẫy áp dụng sai LTE cho p=2)",
            "subject": "Số học",
            "difficulty": "Chuyên / Khu vực",
            "input_type": "text",
            "statement_original": "Tìm tất cả các cặp số nguyên dương $(n, k)$ sao cho:\n$$3^n + 1 = 2^k$$",
            "mock_scenario": "fallacious_invalid_inference",
            "expected_skeptic_challenge": {
                "target_claim_id": "C2",
                "error_type": "invalid_inference",
                "severity": "critical",
                "explanation": "Áp dụng sai công thức Bổ đề nâng số mũ (LTE) của số nguyên tố lẻ cho $p=2$."
            }
        },
        {
            "code": "B03_INEQ_FALSE_WLOG",
            "title": "Bất đẳng thức hoán vị (Bẫy giả sử thứ tự WLOG sai)",
            "subject": "Bất đẳng thức",
            "difficulty": "VMO / Quốc gia",
            "input_type": "text",
            "statement_original": "Cho các số thực dương $a, b, c$ thỏa mãn $a + b + c = 3$. Chứng minh rằng:\n$$\\frac{a}{1 + b^2} + \\frac{b}{1 + c^2} + \\frac{c}{1 + a^2} \\ge \\frac{3}{2}$$",
            "mock_scenario": "fallacious_invalid_inference",
            "expected_skeptic_challenge": {
                "target_claim_id": "C1",
                "error_type": "invalid_inference",
                "severity": "critical",
                "explanation": "Biểu thức chỉ có tính hoán vị vòng quanh (cyclic), không đối xứng toàn phần nên không được giả sử $a \\ge b \\ge c$."
            }
        },
        {
            "code": "B04_COMB_UNSUPPORTED",
            "title": "Phủ bàn cờ bằng quân Domino cực tiểu (Bẫy khẳng định vô căn cứ)",
            "subject": "Tổ hợp",
            "difficulty": "VMO / TST",
            "input_type": "text",
            "statement_original": "Trên bàn cờ kích thước $2n \\times 2n$, người ta đặt một số quân domino $1 \\times 2$ hoặc $2 \\times 1$ không chồng lên nhau sao cho không thể đặt thêm bất kỳ quân domino nào nữa. Tìm giá trị nhỏ nhất của số quân domino đã được đặt.",
            "mock_scenario": "fallacious_unsupported_claim"
        },
        {
            "code": "B05_GEO_AMBIGUOUS",
            "title": "Đường thẳng qua trực tâm vuông góc trung tuyến (Bẫy cấu hình hình học)",
            "subject": "Hình học",
            "difficulty": "VMO / Quốc gia",
            "input_type": "text",
            "statement_original": "Cho tam giác $ABC$ nhọn không cân nội tiếp đường tròn $(O)$, trực tâm $H$. Gọi $M$ là trung điểm của $BC$. Đường thẳng qua $H$ vuông góc với $MH$ cắt $AB, AC$ lần lượt tại $P, Q$. Chứng minh rằng $HP = HQ$.",
            "mock_scenario": "fallacious_ambiguous"
        },
        {
            "code": "B06_POLY_CALC_ERROR",
            "title": "Ước nguyên tố của đa thức bậc 4 (Bẫy tính toán sai)",
            "subject": "Số học",
            "difficulty": "Chuyên / Khu vực",
            "input_type": "text",
            "statement_original": "Tìm tất cả các số nguyên tố $p$ sao cho tồn tại số nguyên dương $n$ thỏa mãn $p \\mid n^4 - n^2 + 1$.",
            "mock_scenario": "fallacious_calculation"
        },
        {
            "code": "B07_DAG_CIRCULAR",
            "title": "Bất đẳng thức Nesbitt biến thể (Kịch bản kiểm tra Chu trình DAG)",
            "subject": "Bất đẳng thức",
            "difficulty": "Chuyên / Khu vực",
            "input_type": "text",
            "statement_original": "Cho các số thực dương $x, y, z$ thỏa mãn $xyz = 1$. Chứng minh rằng:\n$$\\frac{x^2}{y+z} + \\frac{y^2}{z+x} + \\frac{z^2}{x+y} \\ge \\frac{3}{2}$$",
            "mock_scenario": "dag_cycle_error"
        },
        {
            "code": "B08_NEEDS_REVIEW_TYPO",
            "title": "Đề bài nghi ngờ chép sai dấu bất đẳng thức (Kiểm tra trạng thái needs_review)",
            "subject": "Bất đẳng thức",
            "difficulty": "Cơ bản",
            "input_type": "text",
            "statement_original": "Cho các số thực dương $a, b, c$ thỏa mãn $a + b + c = 3$. Chứng minh rằng:\n$$a^2 + b^2 + c^2 \\le 1$$",
            "mock_scenario": "needs_review_malformed"
        },
        {
            "code": "B09_VALID_IMO1959",
            "title": "IMO 1959 Bài 1 — Phân số tối giản (Kịch bản Lời giải Đúng chuẩn)",
            "subject": "Số học",
            "difficulty": "IMO / Quốc tế",
            "input_type": "text",
            "statement_original": "Chứng minh rằng với mọi số nguyên dương $n$, phân số sau đây là phân số tối giản:\n$$\\frac{21n + 4}{14n + 3}$$",
            "mock_scenario": "valid_complete_proof"
        },
        {
            "code": "B10_VALID_PIGEONHOLE",
            "title": "Chọn số chia hết trong tập con của {1, 2, ..., 2n} (Kịch bản Lời giải Đúng chuẩn)",
            "subject": "Tổ hợp",
            "difficulty": "Chuyên / Khu vực",
            "input_type": "text",
            "statement_original": "Cho tập hợp $S = \\{1, 2, \\dots, 2n\\}$. Từ $S$ ta chọn ra $n+1$ số phân biệt bất kỳ. Chứng minh rằng trong các số được chọn, luôn tồn tại hai số sao cho số này là bội của số kia.",
            "mock_scenario": "valid_complete_proof"
        }
    ]
}

# ==============================================================================
# 2. CẤU TRÚC TOÀN BỘ CÁC FILE CẬP NHẬT TRONG DỰ ÁN
# ==============================================================================
FILES_TO_UPDATE = {
    "math-council/.gitignore": """__pycache__/
*.py[cod]
*$py.class
.pytest_cache/
.venv/
venv/
env/
.env
.env.local
node_modules/
.next/
out/
npm-debug.log*
.vscode/
.idea/
*.swp
""",

    "math-council/.env.example": """# PostgreSQL
POSTGRES_USER=mathcouncil
POSTGRES_PASSWORD=mathcouncil_dev_secret
POSTGRES_DB=mathcouncil_db
POSTGRES_PORT=5432

# Backend FastAPI & Redis
DATABASE_URL=postgresql+asyncpg://mathcouncil:mathcouncil_dev_secret@db:5432/mathcouncil_db
REDIS_URL=redis://redis:6379/0
API_HOST=0.0.0.0
API_PORT=8000
ENVIRONMENT=development

# Chế độ AI ("mock" = Chạy giả lập tất định miễn phí để test; "live" = Gọi API thật)
DEFAULT_LLM_PROVIDER=mock

# API Keys của các hãng AI (Chỉ lưu tại Backend)
GEMINI_API_KEY=
OPENAI_API_KEY=
ANTHROPIC_API_KEY=
OPENAI_COMPATIBLE_BASE_URL=https://api.deepseek.com/v1
OPENAI_COMPATIBLE_API_KEY=

# Phân công Model mặc định cho từng vai trò (Định dạng: provider:model_name)
ROLE_NORMALIZER_MODEL=gemini:gemini-2.5-flash
ROLE_SOLVER_A_MODEL=gemini:gemini-2.5-pro
ROLE_SOLVER_B_MODEL=openai:gpt-4o
ROLE_SOLVER_C_MODEL=openai_compatible:deepseek-reasoner
ROLE_SKEPTIC_MODEL=anthropic:claude-3-7-sonnet-latest
ROLE_JUDGE_MODEL=openai:gpt-4o

# Frontend Next.js
INTERNAL_API_URL=http://api:8000
NEXT_PUBLIC_API_URL=http://localhost:8000
""",

    "math-council/docker-compose.yml": """services:
  db:
    image: postgres:16-alpine
    container_name: math_council_db
    restart: unless-stopped
    env_file:
      - .env
    environment:
      POSTGRES_USER: ${POSTGRES_USER:-mathcouncil}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD:-mathcouncil_dev_secret}
      POSTGRES_DB: ${POSTGRES_DB:-mathcouncil_db}
    ports:
      - "${POSTGRES_PORT:-5432}:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ${POSTGRES_USER:-mathcouncil} -d ${POSTGRES_DB:-mathcouncil_db}"]
      interval: 5s
      timeout: 5s
      retries: 5

  api:
    build:
      context: ./services/api
      dockerfile: Dockerfile
    container_name: math_council_api
    restart: unless-stopped
    env_file:
      - .env
    environment:
      DATABASE_URL: postgresql+asyncpg://${POSTGRES_USER:-mathcouncil}:${POSTGRES_PASSWORD:-mathcouncil_dev_secret}@db:5432/${POSTGRES_DB:-mathcouncil_db}
    ports:
      - "8000:8000"
    volumes:
      - ./services/api:/app
    depends_on:
      db:
        condition: service_healthy
    command: >
      sh -c "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload"

  web:
    build:
      context: ./apps/web
      dockerfile: Dockerfile
    container_name: math_council_web
    restart: unless-stopped
    env_file:
      - .env
    environment:
      INTERNAL_API_URL: http://api:8000
      NEXT_PUBLIC_API_URL: http://localhost:8000
    ports:
      - "3000:3000"
    volumes:
      - ./apps/web:/app
      - /app/node_modules
      - /app/.next
    depends_on:
      - api

volumes:
  postgres_data:
""",

    "math-council/services/api/Dockerfile": """FROM python:3.12-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \\
    PYTHONUNBUFFERED=1

RUN apt-get update && apt-get install -y --no-install-recommends \\
    build-essential \\
    curl \\
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml ./
RUN pip install --no-cache-dir --upgrade pip && \\
    pip install --no-cache-dir -e ".[dev]"

COPY . .

EXPOSE 8000
""",

    "math-council/services/api/pyproject.toml": """[build-system]
requires = ["setuptools>=68.0"]
build-backend = "setuptools.build_meta"

[project]
name = "math-council-api"
version = "0.1.0"
description = "Math Council Backend API"
readme = "README.md"
requires-python = ">=3.12"
dependencies = [
    "fastapi>=0.115.0",
    "uvicorn[standard]>=0.30.0",
    "sqlalchemy[asyncio]>=2.0.35",
    "asyncpg>=0.29.0",
    "alembic>=1.13.2",
    "pydantic>=2.9.0",
    "pydantic-settings>=2.5.2",
    "httpx>=0.27.2",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.3.0",
    "pytest-asyncio>=0.24.0",
]

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
pythonpath = ["."]
""",

    "math-council/services/api/app/core/config.py": """from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    PROJECT_NAME: str = "Math Council API"
    VERSION: str = "1.0.0"
    API_V1_STR: str = "/api/v1"
    DATABASE_URL: str = "postgresql+asyncpg://mathcouncil:mathcouncil_dev_secret@db:5432/mathcouncil_db"
    REDIS_URL: str = "redis://redis:6379/0"
    ENVIRONMENT: str = "development"

    # Chế độ mặc định ("mock" để chạy test miễn phí, "live" để gọi AI thật)
    DEFAULT_LLM_PROVIDER: str = "mock"

    # API Keys cho từng Provider
    GEMINI_API_KEY: str = ""
    OPENAI_API_KEY: str = ""
    ANTHROPIC_API_KEY: str = ""
    OPENAI_COMPATIBLE_BASE_URL: str = "https://api.deepseek.com/v1"
    OPENAI_COMPATIBLE_API_KEY: str = ""

    # Cấu hình Model mặc định cho từng vai trò trong Hội đồng (provider:model_name)
    ROLE_NORMALIZER_MODEL: str = "gemini:gemini-2.5-flash"
    ROLE_SOLVER_A_MODEL: str = "gemini:gemini-2.5-pro"
    ROLE_SOLVER_B_MODEL: str = "openai:gpt-4o"
    ROLE_SOLVER_C_MODEL: str = "openai_compatible:deepseek-reasoner"
    ROLE_SKEPTIC_MODEL: str = "anthropic:claude-3-7-sonnet-latest"
    ROLE_JUDGE_MODEL: str = "openai:gpt-4o"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
""",

    "math-council/services/api/app/db/session.py": """from collections.abc import AsyncGenerator
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase
from app.core.config import settings


class Base(DeclarativeBase):
    pass


engine = create_async_engine(
    settings.DATABASE_URL,
    echo=False,
    future=True,
    pool_pre_ping=True,
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        yield session
""",

    "math-council/services/api/app/models/problem.py": """import uuid
from datetime import datetime
from sqlalchemy import DateTime, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.session import Base


class Problem(Base):
    __tablename__ = "problems"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    title: Mapped[str | None] = mapped_column(Text, nullable=True)
    statement_original: Mapped[str] = mapped_column(Text, nullable=False)
    statement_normalized: Mapped[str | None] = mapped_column(Text, nullable=True)
    input_type: Mapped[str] = mapped_column(Text, nullable=False, default="text")
    subject: Mapped[str | None] = mapped_column(Text, nullable=True)
    difficulty: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    runs: Mapped[list["Run"]] = relationship(
        "Run",
        back_populates="problem",
        cascade="all, delete-orphan",
        order_by="desc(Run.created_at)",
    )
""",

    "math-council/services/api/app/models/run.py": """import uuid
from datetime import datetime
from decimal import Decimal
from sqlalchemy import DateTime, ForeignKey, Numeric, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.session import Base


class Run(Base):
    __tablename__ = "runs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    problem_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("problems.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    status: Mapped[str] = mapped_column(Text, nullable=False, default="queued")
    config: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    budget_usd: Mapped[Decimal | None] = mapped_column(Numeric(10, 6), nullable=True)
    actual_cost_usd: Mapped[Decimal] = mapped_column(
        Numeric(10, 6), nullable=False, default=Decimal("0.000000")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    problem: Mapped["Problem"] = relationship("Problem", back_populates="runs")
""",

    "math-council/services/api/app/models/__init__.py": """from app.db.session import Base
from app.models.problem import Problem
from app.models.run import Run

__all__ = ["Base", "Problem", "Run"]
""",

    "math-council/services/api/app/schemas/run.py": """import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any, Literal
from pydantic import BaseModel, ConfigDict, Field

RunStatusStep2 = Literal["queued", "failed", "cancelled"]


class RunCreate(BaseModel):
    config: dict[str, Any] = Field(
        default_factory=lambda: {
            "mode": "step2_skeleton",
            "ai_enabled": False,
            "max_rounds": 2,
            "use_third_solver": False,
            "role_models": {
                "normalizer": "gemini:gemini-2.5-flash",
                "solver_a": "gemini:gemini-2.5-pro",
                "solver_b": "openai:gpt-4o",
                "skeptic": "anthropic:claude-3-7-sonnet-latest",
                "judge": "openai:gpt-4o",
            },
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
""",

    "math-council/services/api/app/schemas/problem.py": """import uuid
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
""",

    "math-council/services/api/app/schemas/agent_contracts.py": """from typing import Literal
from pydantic import BaseModel, Field

ClaimStatus = Literal["unverified", "supported", "disputed", "rejected"]

ChallengeErrorType = Literal[
    "valid",
    "invalid_inference",
    "missing_case",
    "unsupported_claim",
    "incorrect_calculation",
    "ambiguous_statement",
    "needs_more_evidence",
]

ChallengeSeverity = Literal["minor", "major", "critical"]
ChallengeStatus = Literal["open", "accepted", "rejected", "unresolved"]
ConfidenceLevel = Literal["low", "medium", "high"]


class NormalizationOutputSchema(BaseModel):
    statement_normalized: str = Field(..., description="Đề toán đã chuẩn hóa LaTeX.")
    needs_clarification: bool = Field(default=False)
    clarification_reason: str | None = Field(default=None)
    detected_subject: str | None = Field(default=None)


class ClaimItemSchema(BaseModel):
    claim_id: str = Field(..., pattern=r"^C[1-9][0-9]*$")
    statement: str
    reasoning: str
    depends_on: list[str] = Field(default_factory=list)
    status: ClaimStatus = Field(default="unverified")


class ProofStepSchema(BaseModel):
    step_id: str = Field(..., pattern=r"^S[1-9][0-9]*$")
    claim_refs: list[str] = Field(default_factory=list)
    content: str


class SolverOutputSchema(BaseModel):
    task_type: Literal["solve", "revise"] = "solve"
    status: Literal["completed", "partial", "failed"] = "completed"
    summary: str
    claims: list[ClaimItemSchema] = Field(..., min_length=1)
    proof_steps: list[ProofStepSchema] = Field(..., min_length=1)
    unresolved_questions: list[str] = Field(default_factory=list)
    confidence: ConfidenceLevel = "medium"


class ChallengeItemSchema(BaseModel):
    target_claim_id: str
    error_type: ChallengeErrorType
    severity: ChallengeSeverity
    explanation: str
    counterexample: str | None = Field(default=None)
    required_fix: str


class SkepticOutputSchema(BaseModel):
    task_type: Literal["critique"] = "critique"
    overall_assessment: str
    challenges: list[ChallengeItemSchema] = Field(default_factory=list)
    confidence: ConfidenceLevel = "high"


class ChallengeResponseItemSchema(BaseModel):
    target_claim_id: str
    action: Literal["revised", "defended", "acknowledged_unresolved"]
    response_explanation: str


class SolverRevisionOutputSchema(BaseModel):
    task_type: Literal["revise"] = "revise"
    revised_solution: SolverOutputSchema
    challenge_responses: list[ChallengeResponseItemSchema] = Field(default_factory=list)


class ChallengeAdjudicationItemSchema(BaseModel):
    target_claim_id: str
    new_status: Literal["accepted", "rejected", "unresolved"]
    reason: str


class JudgeOutputSchema(BaseModel):
    task_type: Literal["adjudicate"] = "adjudicate"
    verdict_status: Literal["supported", "disputed", "unresolved", "rejected"]
    selected_solver_role: Literal["solver_a", "solver_b", "solver_c", "none"] = "none"
    summary: str
    final_proof_markdown: str
    challenge_adjudications: list[ChallengeAdjudicationItemSchema] = Field(default_factory=list)
    accepted_claims: list[str] = Field(default_factory=list)
    unresolved_issues: list[str] = Field(default_factory=list)
""",

    "math-council/services/api/app/prompts/math_council_prompts.py": """from dataclasses import dataclass


@dataclass(frozen=True)
class VersionedPrompt:
    version: str
    role: str
    system_instruction: str


NORMALIZER_PROMPT_V1 = VersionedPrompt(
    version="NORMALIZER_V1.0",
    role="normalizer",
    system_instruction=(
        "Bạn là Chuyên gia Chuẩn hóa Đề toán Olympic (Normalizer). "
        "Chuẩn hóa ký hiệu sang LaTeX chuẩn nhưng KHÔNG tự ý sửa bản chất đề. "
        "Nếu nghi ngờ đề bị chép sai công thức hoặc thiếu điều kiện biên nghiêm trọng, đặt needs_clarification=true."
    ),
)

SOLVER_PROMPT_V1 = VersionedPrompt(
    version="SOLVER_V1.0",
    role="solver",
    system_instruction=(
        "Bạn là Nhà Toán học Olympic độc lập (Solver). Phân rã lời giải thành các Mệnh đề (Claims: C1, C2...) "
        "có đồ thị phụ thuộc depends_on không chu trình (DAG) và các Bước chứng minh (S1, S2...). "
        "Cấm dùng từ 'hiển nhiên' để nhảy cóc. Phải kiểm tra mẫu số khác 0 và tính đối xứng trước khi giả sử WLOG."
    ),
)

SKEPTIC_PROMPT_V1 = VersionedPrompt(
    version="SKEPTIC_V1.0",
    role="skeptic",
    system_instruction=(
        "Bạn là Phản biện viên Toán học Khắt khe (Skeptic). Rà soát từng mệnh đề C1, C2... của Solver để bắt các lỗi: "
        "chia cho 0 (missing_case), giả sử WLOG sai hoặc dùng sai định lý LTE/Jensen (invalid_inference), "
        "nhảy cóc bước khó (unsupported_claim), tính toán sai (incorrect_calculation), ngụy biện hình học (ambiguous_statement)."
    ),
)

REVISER_PROMPT_V1 = VersionedPrompt(
    version="REVISER_V1.0",
    role="reviser",
    system_instruction=(
        "Bạn là Solver thực hiện bước Sửa chữa (Revising). Với mỗi phản biện của Skeptic, chọn revised (viết lại mệnh đề), "
        "defended (bảo vệ có chứng minh), hoặc acknowledged_unresolved. Không được tự ý đóng phản biện."
    ),
)

JUDGE_PROMPT_V1 = VersionedPrompt(
    version="JUDGE_V1.0",
    role="judge",
    system_instruction=(
        "Bạn là Thẩm phán Tối cao (Judge) của Math Council. Tuyệt đối không dùng biểu quyết đa số làm bằng chứng toán học. "
        "Chỉ kết luận supported khi các mệnh đề hoàn toàn chặt chẽ và các phản biện xác đáng đã được giải quyết."
    ),
)


def wrap_untrusted_content(label: str, raw_text: str) -> str:
    return f"<untrusted_math_content label='{label}'>\\n{raw_text}\\n</untrusted_math_content>"
""",

    "math-council/services/api/app/claims/dag_validator.py": """from dataclasses import dataclass, field
from app.schemas.agent_contracts import ClaimItemSchema


@dataclass
class DAGValidationResult:
    is_valid: bool
    missing_references: list[tuple[str, str]] = field(default_factory=list)
    cycles: list[list[str]] = field(default_factory=list)


def validate_claims_dag(claims: list[ClaimItemSchema]) -> DAGValidationResult:
    claim_map = {c.claim_id: c for c in claims}
    missing_refs: list[tuple[str, str]] = []

    for claim in claims:
        for dep_id in claim.depends_on:
            if dep_id not in claim_map:
                missing_refs.append((claim.claim_id, dep_id))

    state: dict[str, int] = {c.claim_id: 0 for c in claims}
    path: list[str] = []
    cycles: list[list[str]] = []

    def dfs(node_id: str) -> None:
        state[node_id] = 1
        path.append(node_id)
        for dep_id in claim_map[node_id].depends_on:
            if dep_id not in claim_map:
                continue
            if state[dep_id] == 1:
                cycle_start_idx = path.index(dep_id)
                cycles.append(path[cycle_start_idx:] + [dep_id])
            elif state[dep_id] == 0:
                dfs(dep_id)
        path.pop()
        state[node_id] = 2

    for c_id in claim_map:
        if state[c_id] == 0:
            dfs(c_id)

    return DAGValidationResult(
        is_valid=(len(missing_refs) == 0 and len(cycles) == 0),
        missing_references=missing_refs,
        cycles=cycles,
    )
""",

    "math-council/services/api/app/llm_gateway/base_and_adapters.py": """import abc
import json
import re
import time
from decimal import Decimal
from typing import Any, TypeVar
import httpx
from pydantic import BaseModel
from app.core.config import settings
from app.schemas.agent_contracts import (
    ChallengeAdjudicationItemSchema,
    ChallengeItemSchema,
    ClaimItemSchema,
    JudgeOutputSchema,
    NormalizationOutputSchema,
    ProofStepSchema,
    SkepticOutputSchema,
    SolverOutputSchema,
    SolverRevisionOutputSchema,
)

T = TypeVar("T", bound=BaseModel)

MODEL_PRICING_PER_1M: dict[str, tuple[Decimal, Decimal]] = {
    "gemini-2.5-flash": (Decimal("0.15"), Decimal("0.60")),
    "gemini-2.5-pro": (Decimal("1.25"), Decimal("5.00")),
    "gpt-4o": (Decimal("2.50"), Decimal("10.00")),
    "gpt-4o-mini": (Decimal("0.15"), Decimal("0.60")),
    "o3-mini": (Decimal("1.10"), Decimal("4.40")),
    "claude-3-7-sonnet-latest": (Decimal("3.00"), Decimal("15.00")),
    "deepseek-chat": (Decimal("0.27"), Decimal("1.10")),
    "deepseek-reasoner": (Decimal("0.55"), Decimal("2.19")),
}


def calculate_call_cost(model_name: str, input_tokens: int, output_tokens: int) -> Decimal:
    in_price, out_price = MODEL_PRICING_PER_1M.get(
        model_name, (Decimal("1.00"), Decimal("3.00"))
    )
    cost = (Decimal(input_tokens) * in_price + Decimal(output_tokens) * out_price) / Decimal("1000000")
    return cost.quantize(Decimal("0.000001"))


def extract_json_object(raw_text: str) -> str:
    cleaned = re.sub(r"<think>.*?</think>", "", raw_text, flags=re.DOTALL).strip()
    fence_match = re.search(r"```(?:json)?\\s*(\\{.*?\\})\\s*```", cleaned, flags=re.DOTALL)
    if fence_match:
        return fence_match.group(1)
    first_brace = cleaned.find("{")
    last_brace = cleaned.rfind("}")
    if first_brace != -1 and last_brace != -1 and last_brace > first_brace:
        return cleaned[first_brace : last_brace + 1]
    return cleaned


def build_schema_instruction(system_prompt: str, response_schema: type[BaseModel]) -> str:
    schema_json = json.dumps(response_schema.model_json_schema(), ensure_ascii=False)
    return (
        f"{system_prompt}\\n\\n"
        "BẮT BUỘC: Chỉ trả về một đối tượng JSON hợp lệ duy nhất tuân thủ JSON Schema sau:\\n"
        f"{schema_json}"
    )


class LLMCallResult(BaseModel):
    parsed_data: dict[str, Any]
    provider: str
    model_name: str
    prompt_version: str
    input_tokens: int
    output_tokens: int
    cost_usd: Decimal
    latency_ms: int
    provider_request_id: str | None = None


class BaseLLMAdapter(abc.ABC):
    provider_name: str = "base"

    @abc.abstractmethod
    async def generate_structured(
        self,
        *,
        model_name: str,
        prompt_version: str,
        system_prompt: str,
        user_prompt: str,
        response_schema: type[T],
        timeout_sec: float = 90.0,
    ) -> tuple[T, LLMCallResult]:
        raise NotImplementedError


class OpenAIAdapter(BaseLLMAdapter):
    provider_name = "openai"

    def __init__(self, api_key: str | None = None, base_url: str = "https://api.openai.com/v1") -> None:
        self.api_key = api_key or settings.OPENAI_API_KEY
        self.base_url = base_url.rstrip("/")

    async def generate_structured(
        self,
        *,
        model_name: str = "gpt-4o",
        prompt_version: str,
        system_prompt: str,
        user_prompt: str,
        response_schema: type[T],
        timeout_sec: float = 90.0,
    ) -> tuple[T, LLMCallResult]:
        if not self.api_key:
            raise RuntimeError(f"Thiếu API Key cho provider '{self.provider_name}'.")

        full_system_prompt = build_schema_instruction(system_prompt, response_schema)
        payload: dict[str, Any] = {
            "model": model_name,
            "messages": [
                {"role": "system", "content": full_system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "response_format": {"type": "json_object"},
            "temperature": 0.2,
        }
        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}

        start = time.perf_counter()
        async with httpx.AsyncClient(timeout=timeout_sec) as client:
            resp = await client.post(f"{self.base_url}/chat/completions", headers=headers, json=payload)
            resp.raise_for_status()
            data = resp.json()

        elapsed_ms = int((time.perf_counter() - start) * 1000)
        raw_content = data["choices"][0]["message"]["content"]
        validated = response_schema.model_validate_json(extract_json_object(raw_content))

        usage = data.get("usage", {})
        in_tok = int(usage.get("prompt_tokens", 0))
        out_tok = int(usage.get("completion_tokens", 0))

        return validated, LLMCallResult(
            parsed_data=validated.model_dump(),
            provider=self.provider_name,
            model_name=model_name,
            prompt_version=prompt_version,
            input_tokens=in_tok,
            output_tokens=out_tok,
            cost_usd=calculate_call_cost(model_name, in_tok, out_tok),
            latency_ms=elapsed_ms,
            provider_request_id=data.get("id"),
        )


class OpenAICompatibleAdapter(OpenAIAdapter):
    provider_name = "openai_compatible"

    def __init__(self) -> None:
        super().__init__(
            api_key=settings.OPENAI_COMPATIBLE_API_KEY,
            base_url=settings.OPENAI_COMPATIBLE_BASE_URL,
        )


class AnthropicAdapter(BaseLLMAdapter):
    provider_name = "anthropic"

    async def generate_structured(
        self,
        *,
        model_name: str = "claude-3-7-sonnet-latest",
        prompt_version: str,
        system_prompt: str,
        user_prompt: str,
        response_schema: type[T],
        timeout_sec: float = 90.0,
    ) -> tuple[T, LLMCallResult]:
        if not settings.ANTHROPIC_API_KEY:
            raise RuntimeError("Thiếu ANTHROPIC_API_KEY trong biến môi trường.")

        full_system_prompt = build_schema_instruction(system_prompt, response_schema)
        payload = {
            "model": model_name,
            "max_tokens": 4096,
            "temperature": 0.2,
            "system": full_system_prompt,
            "messages": [{"role": "user", "content": user_prompt}],
        }
        headers = {
            "x-api-key": settings.ANTHROPIC_API_KEY,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }

        start = time.perf_counter()
        async with httpx.AsyncClient(timeout=timeout_sec) as client:
            resp = await client.post("https://api.anthropic.com/v1/messages", headers=headers, json=payload)
            resp.raise_for_status()
            data = resp.json()

        elapsed_ms = int((time.perf_counter() - start) * 1000)
        raw_text = data["content"][0]["text"]
        validated = response_schema.model_validate_json(extract_json_object(raw_text))

        usage = data.get("usage", {})
        in_tok = int(usage.get("input_tokens", 0))
        out_tok = int(usage.get("output_tokens", 0))

        return validated, LLMCallResult(
            parsed_data=validated.model_dump(),
            provider=self.provider_name,
            model_name=model_name,
            prompt_version=prompt_version,
            input_tokens=in_tok,
            output_tokens=out_tok,
            cost_usd=calculate_call_cost(model_name, in_tok, out_tok),
            latency_ms=elapsed_ms,
            provider_request_id=data.get("id"),
        )


class GeminiAdapter(BaseLLMAdapter):
    provider_name = "gemini"

    async def generate_structured(
        self,
        *,
        model_name: str = "gemini-2.5-pro",
        prompt_version: str,
        system_prompt: str,
        user_prompt: str,
        response_schema: type[T],
        timeout_sec: float = 90.0,
    ) -> tuple[T, LLMCallResult]:
        if not settings.GEMINI_API_KEY:
            raise RuntimeError("Thiếu GEMINI_API_KEY trong biến môi trường.")

        full_system_prompt = build_schema_instruction(system_prompt, response_schema)
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent"
        payload = {
            "systemInstruction": {"parts": [{"text": full_system_prompt}]},
            "contents": [{"role": "user", "parts": [{"text": user_prompt}]}],
            "generationConfig": {"responseMimeType": "application/json", "temperature": 0.2},
        }
        start = time.perf_counter()
        async with httpx.AsyncClient(timeout=timeout_sec) as client:
            resp = await client.post(url, params={"key": settings.GEMINI_API_KEY}, json=payload)
            resp.raise_for_status()
            data = resp.json()

        elapsed_ms = int((time.perf_counter() - start) * 1000)
        raw_text = data["candidates"][0]["content"]["parts"][0]["text"]
        validated = response_schema.model_validate_json(extract_json_object(raw_text))

        usage = data.get("usageMetadata", {})
        in_tok = int(usage.get("promptTokenCount", 0))
        out_tok = int(usage.get("candidatesTokenCount", 0))

        return validated, LLMCallResult(
            parsed_data=validated.model_dump(),
            provider=self.provider_name,
            model_name=model_name,
            prompt_version=prompt_version,
            input_tokens=in_tok,
            output_tokens=out_tok,
            cost_usd=calculate_call_cost(model_name, in_tok, out_tok),
            latency_ms=elapsed_ms,
        )


class DeterministicMockAdapter(BaseLLMAdapter):
    provider_name = "mock"

    async def generate_structured(
        self,
        *,
        model_name: str,
        prompt_version: str,
        system_prompt: str,
        user_prompt: str,
        response_schema: type[T],
        timeout_sec: float = 60.0,
    ) -> tuple[T, LLMCallResult]:
        start = time.perf_counter()

        if response_schema is NormalizationOutputSchema:
            needs_review = "a^2 + b^2 + c^2 \\le 1" in user_prompt or "NEEDS_REVIEW" in user_prompt
            obj = NormalizationOutputSchema(
                statement_normalized=user_prompt.strip(),
                needs_clarification=needs_review,
                clarification_reason=(
                    "Đề bài có dấu hiệu chép sai chiều bất đẳng thức: với a=b=c=1 thì a^2+b^2+c^2 = 3 > 1."
                    if needs_review
                    else None
                ),
                detected_subject="Toán Olympic",
            )
        elif response_schema is SolverOutputSchema:
            obj = SolverOutputSchema(
                task_type="solve",
                status="completed",
                summary="Biến đổi tương đương và sử dụng tính chất chia hết / bất đẳng thức cổ điển.",
                claims=[
                    ClaimItemSchema(
                        claim_id="C1",
                        statement="Thiết lập đẳng thức cơ sở hoặc điều kiện biên của bài toán.",
                        reasoning="Biến đổi đại số trực tiếp từ giả thiết đề bài.",
                        depends_on=[],
                        status="unverified",
                    ),
                    ClaimItemSchema(
                        claim_id="C2",
                        statement="Suy ra kết luận của bài toán từ mệnh đề C1.",
                        reasoning="Kết hợp C1 và tính chất số nguyên / bất đẳng thức.",
                        depends_on=["C1"],
                        status="unverified",
                    ),
                ],
                proof_steps=[
                    ProofStepSchema(step_id="S1", claim_refs=["C1"], content="Bước 1: Thiết lập bổ đề C1."),
                    ProofStepSchema(step_id="S2", claim_refs=["C1", "C2"], content="Bước 2: Hoàn tất chứng minh C2."),
                ],
                unresolved_questions=[],
                confidence="high",
            )
        elif response_schema is SkepticOutputSchema:
            if "21n + 4" in user_prompt:
                obj = SkepticOutputSchema(
                    overall_assessment="Lời giải chặt chẽ, tổ hợp tuyến tính đúng.",
                    challenges=[],
                    confidence="high",
                )
            else:
                obj = SkepticOutputSchema(
                    overall_assessment="Cần làm rõ điều kiện biên ở bước suy luận C2.",
                    challenges=[
                        ChallengeItemSchema(
                            target_claim_id="C2",
                            error_type="missing_case",
                            severity="major",
                            explanation="Chưa kiểm tra trường hợp biên khi mẫu số hoặc nhân tử triệt tiêu bằng 0.",
                            counterexample="Thử với giá trị biên x = y hoặc n = 1.",
                            required_fix="Bổ sung xét riêng trường hợp suy biến trước khi chia.",
                        )
                    ],
                    confidence="high",
                )
        elif response_schema is SolverRevisionOutputSchema:
            revised = SolverOutputSchema(
                task_type="revise",
                status="completed",
                summary="Đã bổ sung xét trường hợp biên theo phản biện của Skeptic.",
                claims=[
                    ClaimItemSchema(
                        claim_id="C1",
                        statement="Xét trường hợp biên suy biến, đẳng thức luôn thỏa mãn.",
                        reasoning="Thay trực tiếp giá trị biên vào phương trình gốc.",
                        depends_on=[],
                        status="supported",
                    ),
                    ClaimItemSchema(
                        claim_id="C2",
                        statement="Với trường hợp khác 0, thực hiện phép biến đổi tương đương suy ra ĐPCM.",
                        reasoning="Vì đã loại trừ trường hợp bằng 0 ở C1 nên phép chia hoàn toàn hợp lệ.",
                        depends_on=["C1"],
                        status="supported",
                    ),
                ],
                proof_steps=[
                    ProofStepSchema(step_id="S1", claim_refs=["C1", "C2"], content="Chứng minh đầy đủ cả 2 trường hợp.")
                ],
                confidence="high",
            )
            obj = SolverRevisionOutputSchema(
                revised_solution=revised,
                challenge_responses=[
                    {
                        "target_claim_id": "C2",
                        "action": "revised",
                        "response_explanation": "Đã tách trường hợp mẫu bằng 0 thành mệnh đề C1 riêng biệt.",
                    }
                ],
            )
        elif response_schema is JudgeOutputSchema:
            obj = JudgeOutputSchema(
                verdict_status="supported",
                selected_solver_role="solver_a",
                summary="Lời giải sau khi chỉnh sửa đã lấp đầy lỗ hổng xét trường hợp biên.",
                final_proof_markdown="### Lời giải tổng hợp\\n1. Xét trường hợp biên (Mệnh đề C1).\\n2. Xét trường hợp tổng quát (Mệnh đề C2).",
                challenge_adjudications=[
                    ChallengeAdjudicationItemSchema(
                        target_claim_id="C2",
                        new_status="accepted",
                        reason="Solver đã bổ sung mệnh đề C1 giải quyết triệt để trường hợp chia cho 0.",
                    )
                ],
                accepted_claims=["C1", "C2"],
                unresolved_issues=[],
            )
        else:
            raise ValueError(f"Unsupported schema in MockAdapter: {response_schema}")

        elapsed_ms = max(1, int((time.perf_counter() - start) * 1000))
        validated = response_schema.model_validate(obj.model_dump())
        meta = LLMCallResult(
            parsed_data=validated.model_dump(),
            provider=self.provider_name,
            model_name=model_name,
            prompt_version=prompt_version,
            input_tokens=250,
            output_tokens=180,
            cost_usd=Decimal("0.001500"),
            latency_ms=elapsed_ms,
            provider_request_id="mock-req-001",
        )
        return validated, meta


class MultiProviderRouter:
    def __init__(self, force_mock: bool = False) -> None:
        self.force_mock = force_mock or (settings.DEFAULT_LLM_PROVIDER == "mock")
        self.adapters: dict[str, BaseLLMAdapter] = {
            "mock": DeterministicMockAdapter(),
            "gemini": GeminiAdapter(),
            "openai": OpenAIAdapter(),
            "anthropic": AnthropicAdapter(),
            "openai_compatible": OpenAICompatibleAdapter(),
        }

    def resolve_spec(self, role_model_spec: str) -> tuple[BaseLLMAdapter, str]:
        if self.force_mock or role_model_spec.startswith("mock:"):
            model_part = role_model_spec.split(":", 1)[1] if ":" in role_model_spec else role_model_spec
            return self.adapters["mock"], model_part

        if ":" in role_model_spec:
            provider_key, model_name = role_model_spec.split(":", 1)
        else:
            provider_key, model_name = settings.DEFAULT_LLM_PROVIDER, role_model_spec

        adapter = self.adapters.get(provider_key)
        if not adapter:
            raise ValueError(f"Provider '{provider_key}' không được hỗ trợ. Hỗ trợ: {list(self.adapters.keys())}")
        return adapter, model_name

    async def call_for_role(
        self,
        *,
        role_model_spec: str,
        prompt_version: str,
        system_prompt: str,
        user_prompt: str,
        response_schema: type[T],
        timeout_sec: float = 90.0,
    ) -> tuple[T, LLMCallResult]:
        adapter, model_name = self.resolve_spec(role_model_spec)
        return await adapter.generate_structured(
            model_name=model_name,
            prompt_version=prompt_version,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            response_schema=response_schema,
            timeout_sec=timeout_sec,
        )


def get_available_models_catalog() -> list[dict[str, Any]]:
    return [
        {
            "id": "gemini:gemini-2.5-pro",
            "provider": "gemini",
            "model_name": "gemini-2.5-pro",
            "configured": bool(settings.GEMINI_API_KEY),
            "recommended_roles": ["solver_a", "solver_b", "judge"],
        },
        {
            "id": "openai:gpt-4o",
            "provider": "openai",
            "model_name": "gpt-4o",
            "configured": bool(settings.OPENAI_API_KEY),
            "recommended_roles": ["solver_a", "solver_b", "judge"],
        },
        {
            "id": "openai:o3-mini",
            "provider": "openai",
            "model_name": "o3-mini",
            "configured": bool(settings.OPENAI_API_KEY),
            "recommended_roles": ["solver_a", "solver_b", "skeptic"],
        },
        {
            "id": "anthropic:claude-3-7-sonnet-latest",
            "provider": "anthropic",
            "model_name": "claude-3-7-sonnet-latest",
            "configured": bool(settings.ANTHROPIC_API_KEY),
            "recommended_roles": ["skeptic", "solver_b", "judge"],
        },
        {
            "id": "openai_compatible:deepseek-reasoner",
            "provider": "openai_compatible",
            "model_name": "deepseek-reasoner",
            "configured": bool(settings.OPENAI_COMPATIBLE_API_KEY),
            "recommended_roles": ["solver_a", "solver_c", "skeptic"],
        },
        {
            "id": "mock:deterministic-olympiad-v1",
            "provider": "mock",
            "model_name": "deterministic-olympiad-v1",
            "configured": True,
            "recommended_roles": ["normalizer", "solver_a", "solver_b", "skeptic", "judge"],
        },
    ]
""",

    "math-council/services/api/app/orchestrator/council_runner.py": """\"\"\"
Bộ máy Điều phối Hội đồng Giải toán (Math Council State Machine Orchestrator).
Đã tích hợp trực tiếp MultiProviderRouter: Mỗi vai trò (Normalizer, Solver A, Solver B, Skeptic, Judge)
có thể chạy trên một hãng AI khác nhau và tự động ghi nhận tổng chi phí USD.
\"\"\"
import asyncio
from decimal import Decimal
from typing import Any, Awaitable, Callable
from app.claims.dag_validator import validate_claims_dag
from app.core.config import settings
from app.llm_gateway.base_and_adapters import LLMCallResult, MultiProviderRouter
from app.prompts.math_council_prompts import (
    JUDGE_PROMPT_V1,
    NORMALIZER_PROMPT_V1,
    REVISER_PROMPT_V1,
    SKEPTIC_PROMPT_V1,
    SOLVER_PROMPT_V1,
    wrap_untrusted_content,
)
from app.schemas.agent_contracts import (
    JudgeOutputSchema,
    NormalizationOutputSchema,
    SkepticOutputSchema,
    SolverOutputSchema,
    SolverRevisionOutputSchema,
)


class MathCouncilOrchestrator:
    def __init__(
        self,
        router: MultiProviderRouter | None = None,
        role_models: dict[str, str] | None = None,
        on_stage_change: Callable[[str, dict[str, Any]], Awaitable[None]] | None = None,
    ) -> None:
        self.router = router or MultiProviderRouter()
        default_roles = {
            "normalizer": settings.ROLE_NORMALIZER_MODEL,
            "solver_a": settings.ROLE_SOLVER_A_MODEL,
            "solver_b": settings.ROLE_SOLVER_B_MODEL,
            "solver_c": settings.ROLE_SOLVER_C_MODEL,
            "skeptic": settings.ROLE_SKEPTIC_MODEL,
            "judge": settings.ROLE_JUDGE_MODEL,
        }
        if role_models:
            default_roles.update(role_models)
        self.role_models = default_roles
        self.on_stage_change = on_stage_change
        self.call_history: list[LLMCallResult] = []
        self.total_cost_usd: Decimal = Decimal("0.000000")

    def _record_call(self, meta: LLMCallResult) -> None:
        self.call_history.append(meta)
        self.total_cost_usd += meta.cost_usd

    async def _emit(self, stage: str, payload: dict[str, Any]) -> None:
        if self.on_stage_change:
            await self.on_stage_change(stage, payload)

    async def execute_pipeline(self, statement_original: str, max_rounds: int = 2) -> dict[str, Any]:
        # 1. NORMALIZING
        await self._emit("normalizing", {"model": self.role_models["normalizer"]})
        norm_out, norm_meta = await self.router.call_for_role(
            role_model_spec=self.role_models["normalizer"],
            prompt_version=NORMALIZER_PROMPT_V1.version,
            system_prompt=NORMALIZER_PROMPT_V1.system_instruction,
            user_prompt=wrap_untrusted_content("problem_statement", statement_original),
            response_schema=NormalizationOutputSchema,
        )
        self._record_call(norm_meta)

        if norm_out.needs_clarification:
            await self._emit(
                "needs_review",
                {"reason": norm_out.clarification_reason, "normalized": norm_out.statement_normalized},
            )
            return {
                "final_status": "needs_review",
                "normalization": norm_out.model_dump(),
                "total_cost_usd": str(self.total_cost_usd),
                "model_calls": [c.model_dump() for c in self.call_history],
            }

        problem_text = norm_out.statement_normalized

        # 2. SOLVING (Song song Solver A và Solver B trên 2 model độc lập)
        await self._emit(
            "solving",
            {"solver_a": self.role_models["solver_a"], "solver_b": self.role_models["solver_b"]},
        )
        solver_prompt_input = wrap_untrusted_content("normalized_problem", problem_text)

        (solver_a_out, meta_a), (solver_b_out, meta_b) = await asyncio.gather(
            self.router.call_for_role(
                role_model_spec=self.role_models["solver_a"],
                prompt_version=SOLVER_PROMPT_V1.version,
                system_prompt=SOLVER_PROMPT_V1.system_instruction + "\\nVai trò: Solver A.",
                user_prompt=solver_prompt_input,
                response_schema=SolverOutputSchema,
            ),
            self.router.call_for_role(
                role_model_spec=self.role_models["solver_b"],
                prompt_version=SOLVER_PROMPT_V1.version,
                system_prompt=SOLVER_PROMPT_V1.system_instruction + "\\nVai trò: Solver B.",
                user_prompt=solver_prompt_input,
                response_schema=SolverOutputSchema,
            ),
        )
        self._record_call(meta_a)
        self._record_call(meta_b)

        dag_a = validate_claims_dag(solver_a_out.claims)
        dag_b = validate_claims_dag(solver_b_out.claims)

        # 3 & 4. CRITIQUING & REVISING
        current_a = solver_a_out
        current_b = solver_b_out
        all_critiques: list[dict[str, Any]] = []

        for round_idx in range(1, max_rounds + 1):
            await self._emit("critiquing", {"round": round_idx, "skeptic": self.role_models["skeptic"]})
            (crit_a, meta_ca), (crit_b, meta_cb) = await asyncio.gather(
                self.router.call_for_role(
                    role_model_spec=self.role_models["skeptic"],
                    prompt_version=SKEPTIC_PROMPT_V1.version,
                    system_prompt=SKEPTIC_PROMPT_V1.system_instruction,
                    user_prompt=(
                        wrap_untrusted_content("problem", problem_text)
                        + "\\n"
                        + wrap_untrusted_content("solver_a_solution", current_a.model_dump_json())
                    ),
                    response_schema=SkepticOutputSchema,
                ),
                self.router.call_for_role(
                    role_model_spec=self.role_models["skeptic"],
                    prompt_version=SKEPTIC_PROMPT_V1.version,
                    system_prompt=SKEPTIC_PROMPT_V1.system_instruction,
                    user_prompt=(
                        wrap_untrusted_content("problem", problem_text)
                        + "\\n"
                        + wrap_untrusted_content("solver_b_solution", current_b.model_dump_json())
                    ),
                    response_schema=SkepticOutputSchema,
                ),
            )
            self._record_call(meta_ca)
            self._record_call(meta_cb)

            all_critiques.append({
                "round": round_idx,
                "solver_a_challenges": [c.model_dump() for c in crit_a.challenges],
                "solver_b_challenges": [c.model_dump() for c in crit_b.challenges],
            })

            if not crit_a.challenges and not crit_b.challenges:
                break

            await self._emit("revising", {"round": round_idx})
            if crit_a.challenges:
                rev_a, meta_ra = await self.router.call_for_role(
                    role_model_spec=self.role_models["solver_a"],
                    prompt_version=REVISER_PROMPT_V1.version,
                    system_prompt=REVISER_PROMPT_V1.system_instruction,
                    user_prompt=(
                        wrap_untrusted_content("problem", problem_text)
                        + "\\n"
                        + wrap_untrusted_content("previous_solution", current_a.model_dump_json())
                        + "\\n"
                        + wrap_untrusted_content("skeptic_challenges", crit_a.model_dump_json())
                    ),
                    response_schema=SolverRevisionOutputSchema,
                )
                self._record_call(meta_ra)
                current_a = rev_a.revised_solution

            if crit_b.challenges:
                rev_b, meta_rb = await self.router.call_for_role(
                    role_model_spec=self.role_models["solver_b"],
                    prompt_version=REVISER_PROMPT_V1.version,
                    system_prompt=REVISER_PROMPT_V1.system_instruction,
                    user_prompt=(
                        wrap_untrusted_content("problem", problem_text)
                        + "\\n"
                        + wrap_untrusted_content("previous_solution", current_b.model_dump_json())
                        + "\\n"
                        + wrap_untrusted_content("skeptic_challenges", crit_b.model_dump_json())
                    ),
                    response_schema=SolverRevisionOutputSchema,
                )
                self._record_call(meta_rb)
                current_b = rev_b.revised_solution

        # 5. ADJUDICATING (Judge tổng hợp)
        await self._emit("adjudicating", {"judge": self.role_models["judge"]})
        judge_input = (
            wrap_untrusted_content("problem", problem_text)
            + "\\n"
            + wrap_untrusted_content("solver_a_final", current_a.model_dump_json())
            + "\\n"
            + wrap_untrusted_content("solver_b_final", current_b.model_dump_json())
            + "\\n"
            + wrap_untrusted_content("critique_history", str(all_critiques))
        )
        judge_out, meta_j = await self.router.call_for_role(
            role_model_spec=self.role_models["judge"],
            prompt_version=JUDGE_PROMPT_V1.version,
            system_prompt=JUDGE_PROMPT_V1.system_instruction,
            user_prompt=judge_input,
            response_schema=JudgeOutputSchema,
        )
        self._record_call(meta_j)

        await self._emit("completed", {"verdict": judge_out.verdict_status})
        return {
            "final_status": "completed",
            "normalization": norm_out.model_dump(),
            "dag_validation": {"solver_a_valid": dag_a.is_valid, "solver_b_valid": dag_b.is_valid},
            "solver_a_final": current_a.model_dump(),
            "solver_b_final": current_b.model_dump(),
            "critiques": all_critiques,
            "judge_report": judge_out.model_dump(),
            "total_cost_usd": str(self.total_cost_usd),
            "model_calls": [c.model_dump() for c in self.call_history],
        }
""",

    "math-council/services/api/scripts/seed_problems.py": """\"\"\"
Script nạp nhanh 10 bài toán Olympic mẫu vào Math Council API.
Cách chạy: docker compose exec api python scripts/seed_problems.py
\"\"\"
import asyncio
import json
from pathlib import Path
import httpx

API_BASE_URL = "http://localhost:8000/api/v1"
FIXTURE_PATH = Path(__file__).resolve().parent.parent / "tests" / "fixtures" / "olympiad_benchmark_seed.json"


async def main() -> None:
    if not FIXTURE_PATH.exists():
        print(f"Không tìm thấy file fixture tại: {FIXTURE_PATH}")
        return

    data = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    problems = data.get("problems", [])

    async with httpx.AsyncClient(timeout=15.0) as client:
        for item in problems:
            payload = {
                "title": f"[{item['code']}] {item['title']}",
                "statement_original": item["statement_original"],
                "input_type": item.get("input_type", "text"),
                "subject": item.get("subject"),
                "difficulty": item.get("difficulty"),
            }
            resp = await client.post(f"{API_BASE_URL}/problems", json=payload)
            if resp.status_code == 201:
                print(f"  [201 CREATED] {payload['title']}")
            else:
                print(f"  [ERROR {resp.status_code}] {item['code']}: {resp.text}")


if __name__ == "__main__":
    asyncio.run(main())
""",

    "math-council/STEP2_AGENT_PLAN.md": """# KẾ HOẠCH THỰC THI CHO AI AGENT (MATH COUNCIL - BƯỚC 2)

1. **Phạm vi Bước 2:** Chỉ dựng bộ khung (Walking Skeleton) gồm Next.js + FastAPI + PostgreSQL + Alembic + Docker Compose.
2. **Không sửa đổi** cấu trúc bảng trong `app/models/problem.py` và `app/models/run.py` đã khóa.
3. **Quy tắc HTTP Status & Lỗi:**
   - `GET /health` -> `200 OK`
   - `POST /api/v1/problems` -> `201 Created` (Trả `422` nếu `statement_original` rỗng hoặc toàn khoảng trắng).
   - `GET /api/v1/problems` -> `200 OK`
   - `GET /api/v1/problems/{id}` -> `200 OK` (`404` nếu UUID không tồn tại).
   - `POST /api/v1/problems/{id}/runs` -> `202 Accepted` (Lưu `status = "queued"`, trả `404` nếu `problem_id` không tồn tại).
   - `GET /api/v1/runs/{id}` -> `200 OK` (`404` nếu UUID không tồn tại).
""",

    "math-council/STEP3_AGENT_PLAN.md": """# KẾ HOẠCH THỰC THI CHO AI AGENT (MATH COUNCIL - BƯỚC 3: MULTI-AGENT & ORCHESTRATOR)

## 1. Các Module Lõi Đã Được Cài Đặt Sẵn (KHÔNG XÓA, HÃY TÁI SỬ DỤNG TRỰC TIẾP)
- `app/schemas/agent_contracts.py`: Đã có đủ Pydantic Schemas cho Normalizer, Solver, Skeptic, Reviser, Judge.
- `app/prompts/math_council_prompts.py`: Đã có đủ Prompts phiên bản bất biến và hàm `wrap_untrusted_content`.
- `app/claims/dag_validator.py`: Đã có sẵn hàm `validate_claims_dag(claims)` phát hiện chu trình.
- `app/llm_gateway/base_and_adapters.py`: Đã có sẵn `MultiProviderRouter`, `GeminiAdapter`, `OpenAIAdapter`, `AnthropicAdapter`, `OpenAICompatibleAdapter`, `DeterministicMockAdapter`, và `get_available_models_catalog()`.
- `app/orchestrator/council_runner.py`: Đã có sẵn `MathCouncilOrchestrator` tích hợp `MultiProviderRouter`.
- `tests/fixtures/olympiad_benchmark_seed.json`: Đã có 10 bài toán Olympic & bẫy ngụy biện.

## 2. Nhiệm vụ của Agent ở Bước 3
1. Tạo 9 bảng SQLAlchemy mới (`run_agents`, `messages`, `solutions`, `claims`, `claim_dependencies`, `challenges`, `challenge_events`, `model_calls`, `final_reports`) và Alembic migration `0002_step3_agent_tables.py`.
2. Tạo `app/budget/manager.py` kiểm tra ngân sách `budget_usd` trước mỗi lần gọi và lưu `model_calls` từ `MathCouncilOrchestrator`.
3. Nối `MathCouncilOrchestrator` vào Worker nền (Redis) và lưu kết quả các bước vào 9 bảng Database, đồng thời bắn sự kiện SSE qua Redis Pub/Sub `run:{run_id}:events`.
4. Mở 9 API endpoints mới (`/models` dùng hàm `get_available_models_catalog()`, `/cancel`, `/resume`, `/events`, `/messages`, `/solutions`, `/challenges`, `/report`, `/usage`).
5. Cập nhật giao diện Next.js cho phép người dùng chọn AI Model cho từng vai trò (Solver A, Solver B, Skeptic, Judge) khi bấm Tạo Run và xem trực tiếp tiến trình qua SSE.
""",

    "math-council/AUTO_RUNNER_QUEUE.md": """# HÀNG ĐỢI THỰC THI TỰ ĐỘNG (AUTONOMOUS EXECUTION QUEUE)

**QUY TẮC BẮT BUỘC CHO AGENT:**
1. Thực hiện tuần tự từng Phase từ trên xuống dưới.
2. Ở cuối mỗi Phase, bắt buộc phải chạy lệnh **Verification Gate** trong terminal.
3. Ngay khi một Phase PASS 100%, đổi `[ ]` thành `[x]` trong file này và **TỰ ĐỘNG chuyển sang Phase tiếp theo ngay lập tức**.

---

## PHẦN A: HOÀN THIỆN BƯỚC 2 (WALKING SKELETON)

- [ ] **Phase 2.1: Backend Repositories, Routes, Alembic & Main App**
  - Đọc `STEP2_AGENT_PLAN.md` và các file mẫu trong `services/api/app/models/` và `schemas/`.
  - Tạo `repositories/problem_repo.py` và `run_repo.py` (`AsyncSession`).
  - Tạo `routes/problems.py` và `routes/runs.py` thực thi 5 endpoints đúng mã HTTP `201`, `202`, `404`, `422`.
  - Tạo `app/main.py` có `GET /health`, CORS, Global Exception Handler.
  - Cấu hình `alembic.ini`, `alembic/env.py` (async) và tạo migration `0001_initial_step2_tables.py`.
  - **Verification Gate:** Chạy `docker compose up -d --build db api` và kiểm tra `curl -f http://localhost:8000/health` trả về 200 OK.

- [ ] **Phase 2.2: Automated Pytest cho Bước 2**
  - Tạo `services/api/tests/conftest.py` và `tests/test_api_step2.py`.
  - **Verification Gate:** Chạy `docker compose exec api pytest tests/test_api_step2.py -v` phải PASS 100%.

- [ ] **Phase 2.3: Frontend Next.js + KaTeX & Nghiệm thu Bước 2**
  - Tạo `apps/web/` (Next.js App Router, TypeScript, TailwindCSS, `Dockerfile`, `next.config.mjs` rewrites `/api/v1` sang `http://api:8000`).
  - Tạo `components/MathRenderer.tsx` (`react-markdown` + `remark-math` + `rehype-katex` với `throwOnError: false`).
  - Tạo các trang `/`, `/problems`, `/problems/new` (Live LaTeX Preview), `/problems/[id]`.
  - **Verification Gate:** Chạy `docker compose up -d --build web`, kiểm tra `curl -f http://localhost:3000` trả về 200 OK.

---

## PHẦN B: TRIỂN KHAI BƯỚC 3 (MULTI-AGENT & MULTI-LLM ORCHESTRATOR)

- [ ] **Phase 3.1: Mở rộng 9 Bảng Database & Kiểm thử `dag_validator.py`**
  - Đọc `STEP3_AGENT_PLAN.md`. Lưu ý giữ nguyên và tái sử dụng các file lõi đã có sẵn trong `schemas/agent_contracts.py`, `claims/dag_validator.py`, `prompts/`, `llm_gateway/`, `orchestrator/`.
  - Tạo SQLAlchemy models cho 9 bảng mới và Alembic migration `0002_step3_agent_tables.py`, chạy `docker compose exec api alembic upgrade head`.
  - Viết unit test `tests/test_dag_validator.py` kiểm tra `validate_claims_dag` với kịch bản chu trình `B07_DAG_CIRCULAR` trong `tests/fixtures/olympiad_benchmark_seed.json`.
  - **Verification Gate:** Chạy `docker compose exec api pytest tests/test_dag_validator.py -v` PASS 100%.

- [ ] **Phase 3.2: Kiểm thử MultiProviderRouter & Budget Manager**
  - Tạo `app/budget/manager.py` kiểm tra ngân sách `budget_usd`, dự phòng chi phí song song và raise `BudgetExhaustedError` nếu vượt hạn mức.
  - Viết unit test `tests/test_budget_and_gateway.py` kiểm tra `MultiProviderRouter`, `get_available_models_catalog()` và `BudgetExhaustedError`.
  - **Verification Gate:** Chạy `docker compose exec api pytest tests/test_budget_and_gateway.py -v` PASS 100%.

- [ ] **Phase 3.3: Redis, Worker & Kết nối `MathCouncilOrchestrator` vào Database**
  - Cập nhật `pyproject.toml` (thêm `redis>=5.0.0`) và thêm `redis` + `worker` vào `docker-compose.yml`.
  - Kết nối `MathCouncilOrchestrator` (trong `app/orchestrator/council_runner.py`) với tầng Repository để lưu từng bước (`solutions`, `claims`, `challenges`, `model_calls`, `final_reports`) vào PostgreSQL và bắn sự kiện qua Redis Pub/Sub `run:{run_id}:events`.
  - **Verification Gate:** Viết và chạy `docker compose exec api pytest tests/test_orchestrator_flow.py -v` PASS 100%.

- [ ] **Phase 3.4: 9 API Endpoints Mới & SSE Streaming**
  - Triển khai `/api/v1/models` (dùng `get_available_models_catalog()`), `/runs/{id}/cancel`, `/runs/{id}/resume`, `/runs/{id}/events` (SSE), `/runs/{id}/messages`, `/runs/{id}/solutions`, `/runs/{id}/challenges`, `/runs/{id}/report`, `/runs/{id}/usage`.
  - **Verification Gate:** Viết và chạy `docker compose exec api pytest tests/test_api_step3.py -v` PASS 100%.

- [ ] **Phase 3.5: Giao diện Chọn Model Đa Hãng, Theo dõi SSE & Hoàn thiện README**
  - Cập nhật trang chi tiết bài toán cho phép chọn Model AI cho từng vai trò (`solver_a`, `solver_b`, `skeptic`, `judge`) từ danh sách `/api/v1/models` khi bấm Tạo Run.
  - Tạo trang `/runs/[id]/page.tsx` kết nối SSE, hiển thị Live State Stepper và 4 Tabs (Solutions & Claims, Skeptic Challenges, Judge Final Report, Usage & Budget).
  - Cập nhật `README.md` hướng dẫn chạy dự án và cách cấu hình API keys cho Gemini, OpenAI, Claude, DeepSeek/OpenRouter.
  - **Verification Gate:** Chạy `docker compose exec api pytest -v` PASS 100% và build Frontend thành công.
"""
}


def main() -> None:
    print("Đang cập nhật toàn bộ cài đặt Đa AI Agent, Multi-LLM Router và Benchmark vào dự án...")

    for file_path, content in FILES_TO_UPDATE.items():
        dir_name = os.path.dirname(file_path)
        if dir_name:
            os.makedirs(dir_name, exist_ok=True)
            # Tự động tạo __init__.py cho các package trong app/
            if "services/api/app/" in dir_name:
                init_path = os.path.join(dir_name, "__init__.py")
                if not os.path.exists(init_path):
                    with open(init_path, "w", encoding="utf-8") as f:
                        f.write("")
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(content)
        print(f"  [UPDATED] {file_path}")

    # Lưu file JSON Benchmark
    fixture_path = "math-council/services/api/tests/fixtures/olympiad_benchmark_seed.json"
    os.makedirs(os.path.dirname(fixture_path), exist_ok=True)
    with open(fixture_path, "w", encoding="utf-8") as f:
        json.dump(BENCHMARK_DATA, f, ensure_ascii=False, indent=2)
    print(f"  [UPDATED] {fixture_path}")

    # Tạo file .env từ .env.example nếu chưa có (không ghi đè nếu bạn đã điền key)
    env_path = "math-council/.env"
    if not os.path.exists(env_path):
        shutil.copyfile("math-council/.env.example", env_path)
        print(f"  [CREATED] {env_path} (từ .env.example)")
    else:
        print(f"  [KEPT]    {env_path} (giữ nguyên file .env hiện tại của bạn)")

    # Đóng gói lại thành file zip mới nhất
    zip_filename = "math-council-complete-setup.zip"
    with zipfile.ZipFile(zip_filename, "w", zipfile.ZIP_DEFLATED) as zipf:
        for root, _, files in os.walk("math-council"):
            for file in files:
                full_path = os.path.join(root, file)
                zipf.write(full_path, os.path.relpath(full_path, "."))

    print(f"\nHOÀN TẤT 100%! Đã cập nhật thư mục 'math-council/' và đóng gói vào '{zip_filename}'.")


if __name__ == "__main__":
    main()