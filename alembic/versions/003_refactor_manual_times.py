"""Refactor manual times - add is_manual and arrival_time to call_status, remove manual_call_time from orders

Revision ID: 003
Revises: 002
Create Date: 2025-12-15

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '003'
down_revision = '002'
branch_labels = None
depends_on = None


def upgrade():
    """
    Добавляем поля в call_status и удаляем manual_call_time из orders
    """
    # Добавляем новые поля в call_status
    op.add_column('call_status', sa.Column('arrival_time', sa.DateTime(), nullable=True))
    op.add_column('call_status', sa.Column('is_manual', sa.Boolean(), server_default='false', nullable=False))
    
    # Удаляем manual_call_time из orders
    op.drop_column('orders', 'manual_call_time')


def downgrade():
    """
    Откат изменений
    """
    # Возвращаем manual_call_time в orders
    op.add_column('orders', sa.Column('manual_call_time', sa.DateTime(), nullable=True))
    
    # Удаляем новые поля из call_status
    op.drop_column('call_status', 'is_manual')
    op.drop_column('call_status', 'arrival_time')

