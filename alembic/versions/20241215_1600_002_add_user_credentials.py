"""add user_credentials table

Revision ID: 002
Revises: 001
Create Date: 2024-12-15 16:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '002'
down_revision = '001'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Создание таблицы user_credentials
    op.create_table(
        'user_credentials',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('site', sa.String(), nullable=False),
        sa.Column('encrypted_login', sa.String(), nullable=False),
        sa.Column('encrypted_password', sa.String(), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=True),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Индексы
    op.create_index(op.f('ix_user_credentials_id'), 'user_credentials', ['id'], unique=False)
    op.create_index(op.f('ix_user_credentials_user_id'), 'user_credentials', ['user_id'], unique=False)


def downgrade() -> None:
    # Удаление индексов
    op.drop_index(op.f('ix_user_credentials_user_id'), table_name='user_credentials')
    op.drop_index(op.f('ix_user_credentials_id'), table_name='user_credentials')
    
    # Удаление таблицы
    op.drop_table('user_credentials')
