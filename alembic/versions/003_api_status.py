"""Add api_status table

Revision ID: 003
Revises: 002
Create Date: 2026-01-20 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

revision = '003'
down_revision = '002'
branch_labels = None
depends_on = None


def upgrade():
    """Create api_status table"""
    op.create_table(
        'api_status',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('provider', sa.String(), nullable=False),
        sa.Column('is_available', sa.Boolean(), nullable=True, default=False),
        sa.Column('last_check', sa.DateTime(), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('response_time_ms', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_api_status_user_id', 'api_status', ['user_id'])
    op.create_index('ix_api_status_provider', 'api_status', ['provider'])
    op.create_index('idx_user_provider', 'api_status', ['user_id', 'provider'], unique=True)


def downgrade():
    """Drop api_status table"""
    op.drop_index('idx_user_provider', table_name='api_status')
    op.drop_index('ix_api_status_provider', table_name='api_status')
    op.drop_index('ix_api_status_user_id', table_name='api_status')
    op.drop_table('api_status')
