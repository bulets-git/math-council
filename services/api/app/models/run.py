import uuid
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING
from sqlalchemy import DateTime, ForeignKey, Numeric, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.session import Base

if TYPE_CHECKING:
    from app.models.problem import Problem
    from app.models.step3_models import (
        Challenge,
        FinalReport,
        Message,
        ModelCall,
        RunAgent,
        Solution,
    )


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
    agents: Mapped[list["RunAgent"]] = relationship(
        "RunAgent", cascade="all, delete-orphan", passive_deletes=True
    )
    messages: Mapped[list["Message"]] = relationship(
        "Message", cascade="all, delete-orphan", passive_deletes=True
    )
    solutions: Mapped[list["Solution"]] = relationship(
        "Solution", cascade="all, delete-orphan", passive_deletes=True
    )
    challenges: Mapped[list["Challenge"]] = relationship(
        "Challenge", cascade="all, delete-orphan", passive_deletes=True
    )
    model_calls: Mapped[list["ModelCall"]] = relationship(
        "ModelCall", cascade="all, delete-orphan", passive_deletes=True
    )
    final_report: Mapped["FinalReport | None"] = relationship(
        "FinalReport", uselist=False, cascade="all, delete-orphan", passive_deletes=True
    )
