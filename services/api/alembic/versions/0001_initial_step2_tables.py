"""Initial step2 tables (problems and runs)

Revision ID: 0001
Revises: 
Create Date: 2026-10-14 09:45:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '0001'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'problems',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('title', sa.Text(), nullable=True),
        sa.Column('statement_original', sa.Text(), nullable=False),
        sa.Column('statement_normalized', sa.Text(), nullable=True),
        sa.Column('input_type', sa.Text(), server_default='text', nullable=False),
        sa.Column('subject', sa.Text(), nullable=True),
        sa.Column('difficulty', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )

    op.create_table(
        'runs',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('problem_id', sa.UUID(), nullable=False),
        sa.Column('status', sa.Text(), server_default='queued', nullable=False),
        sa.Column('config', postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column('budget_usd', sa.Numeric(precision=10, scale=6), nullable=True),
        sa.Column('actual_cost_usd', sa.Numeric(precision=10, scale=6), server_default=sa.text("'0.000000'::numeric"), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['problem_id'], ['problems.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_runs_problem_id'), 'runs', ['problem_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_runs_problem_id'), table_name='runs')
    op.drop_table('runs')
    op.drop_table('problems')
