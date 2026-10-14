"""Add step3 multi-agent and orchestrator tables

Revision ID: 0002
Revises: 0001
Create Date: 2026-10-14 10:15:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '0002'
down_revision: Union[str, None] = '0001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. run_agents
    op.create_table(
        'run_agents',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('run_id', sa.UUID(), nullable=False),
        sa.Column('role', sa.Text(), nullable=False),
        sa.Column('model_name', sa.Text(), nullable=False),
        sa.Column('system_prompt', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['run_id'], ['runs.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_run_agents_run_id'), 'run_agents', ['run_id'], unique=False)

    # 2. messages
    op.create_table(
        'messages',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('run_id', sa.UUID(), nullable=False),
        sa.Column('sender_role', sa.Text(), nullable=False),
        sa.Column('recipient_role', sa.Text(), nullable=True),
        sa.Column('round_number', sa.Integer(), server_default='1', nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('metadata', postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['run_id'], ['runs.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_messages_run_id'), 'messages', ['run_id'], unique=False)

    # 3. solutions
    op.create_table(
        'solutions',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('run_id', sa.UUID(), nullable=False),
        sa.Column('solver_role', sa.Text(), nullable=False),
        sa.Column('version', sa.Integer(), server_default='1', nullable=False),
        sa.Column('round_number', sa.Integer(), server_default='1', nullable=False),
        sa.Column('final_answer', sa.Text(), nullable=True),
        sa.Column('summary', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['run_id'], ['runs.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_solutions_run_id'), 'solutions', ['run_id'], unique=False)

    # 4. claims
    op.create_table(
        'claims',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('solution_id', sa.UUID(), nullable=False),
        sa.Column('claim_label', sa.Text(), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('claim_type', sa.Text(), nullable=True),
        sa.Column('status', sa.Text(), server_default='unverified', nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['solution_id'], ['solutions.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_claims_solution_id'), 'claims', ['solution_id'], unique=False)

    # 5. claim_dependencies
    op.create_table(
        'claim_dependencies',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('claim_id', sa.UUID(), nullable=False),
        sa.Column('depends_on_claim_id', sa.UUID(), nullable=False),
        sa.Column('dependency_type', sa.Text(), server_default='requires', nullable=False),
        sa.ForeignKeyConstraint(['claim_id'], ['claims.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['depends_on_claim_id'], ['claims.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_claim_dependencies_claim_id'), 'claim_dependencies', ['claim_id'], unique=False)
    op.create_index(op.f('ix_claim_dependencies_depends_on_claim_id'), 'claim_dependencies', ['depends_on_claim_id'], unique=False)

    # 6. challenges
    op.create_table(
        'challenges',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('run_id', sa.UUID(), nullable=False),
        sa.Column('target_solution_id', sa.UUID(), nullable=False),
        sa.Column('target_claim_id', sa.UUID(), nullable=True),
        sa.Column('challenger_role', sa.Text(), server_default='skeptic', nullable=False),
        sa.Column('round_number', sa.Integer(), server_default='1', nullable=False),
        sa.Column('error_type', sa.Text(), nullable=False),
        sa.Column('status', sa.Text(), server_default='open', nullable=False),
        sa.Column('argument', sa.Text(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['run_id'], ['runs.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['target_solution_id'], ['solutions.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['target_claim_id'], ['claims.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_challenges_run_id'), 'challenges', ['run_id'], unique=False)
    op.create_index(op.f('ix_challenges_target_solution_id'), 'challenges', ['target_solution_id'], unique=False)
    op.create_index(op.f('ix_challenges_target_claim_id'), 'challenges', ['target_claim_id'], unique=False)

    # 7. challenge_events
    op.create_table(
        'challenge_events',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('challenge_id', sa.UUID(), nullable=False),
        sa.Column('actor_role', sa.Text(), nullable=False),
        sa.Column('from_status', sa.Text(), nullable=False),
        sa.Column('to_status', sa.Text(), nullable=False),
        sa.Column('comment', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['challenge_id'], ['challenges.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_challenge_events_challenge_id'), 'challenge_events', ['challenge_id'], unique=False)

    # 8. model_calls
    op.create_table(
        'model_calls',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('run_id', sa.UUID(), nullable=False),
        sa.Column('agent_role', sa.Text(), nullable=False),
        sa.Column('model_name', sa.Text(), nullable=False),
        sa.Column('prompt_tokens', sa.Integer(), server_default='0', nullable=False),
        sa.Column('completion_tokens', sa.Integer(), server_default='0', nullable=False),
        sa.Column('total_tokens', sa.Integer(), server_default='0', nullable=False),
        sa.Column('cost_usd', sa.Numeric(precision=10, scale=6), server_default=sa.text("'0.000000'::numeric"), nullable=False),
        sa.Column('latency_ms', sa.Integer(), server_default='0', nullable=False),
        sa.Column('prompt_version', sa.Text(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['run_id'], ['runs.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_model_calls_run_id'), 'model_calls', ['run_id'], unique=False)

    # 9. final_reports
    op.create_table(
        'final_reports',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('run_id', sa.UUID(), nullable=False),
        sa.Column('judge_role', sa.Text(), server_default='judge', nullable=False),
        sa.Column('consensus_status', sa.Text(), nullable=False),
        sa.Column('winning_solution_id', sa.UUID(), nullable=True),
        sa.Column('final_latex_solution', sa.Text(), nullable=False),
        sa.Column('executive_summary', sa.Text(), nullable=False),
        sa.Column('dissenting_opinions', postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'[]'::jsonb"), nullable=False),
        sa.Column('score', sa.Numeric(precision=3, scale=2), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['run_id'], ['runs.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['winning_solution_id'], ['solutions.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('run_id')
    )
    op.create_index(op.f('ix_final_reports_run_id'), 'final_reports', ['run_id'], unique=True)


def downgrade() -> None:
    op.drop_table('final_reports')
    op.drop_table('model_calls')
    op.drop_table('challenge_events')
    op.drop_table('challenges')
    op.drop_table('claim_dependencies')
    op.drop_table('claims')
    op.drop_table('solutions')
    op.drop_table('messages')
    op.drop_table('run_agents')
