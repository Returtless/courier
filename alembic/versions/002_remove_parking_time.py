"""Remove parking_time_minutes column

Revision ID: 002
Revises: 001
Create Date: 2026-01-19 14:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '002'
down_revision = '001'
branch_labels = None
depends_on = None


def upgrade():
    """Remove parking_time_minutes column from user_settings"""
    # Проверяем, существует ли колонка перед удалением
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    columns = [col['name'] for col in inspector.get_columns('user_settings')]
    
    if 'parking_time_minutes' in columns:
        op.drop_column('user_settings', 'parking_time_minutes')


def downgrade():
    """Restore parking_time_minutes column"""
    op.add_column('user_settings', 
        sa.Column('parking_time_minutes', sa.Integer(), server_default='7', nullable=True)
    )
