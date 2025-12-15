"""add manual time fields to orders

Revision ID: 001
Revises: 
Create Date: 2024-12-15 15:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '001'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add manual_arrival_time and manual_call_time columns to orders table"""
    # Add manual_arrival_time column if it doesn't exist
    op.execute("""
        DO $$ 
        BEGIN 
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns 
                WHERE table_name='orders' AND column_name='manual_arrival_time'
            ) THEN
                ALTER TABLE orders ADD COLUMN manual_arrival_time TIMESTAMP NULL;
            END IF;
        END $$;
    """)
    
    # Add manual_call_time column if it doesn't exist
    op.execute("""
        DO $$ 
        BEGIN 
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns 
                WHERE table_name='orders' AND column_name='manual_call_time'
            ) THEN
                ALTER TABLE orders ADD COLUMN manual_call_time TIMESTAMP NULL;
            END IF;
        END $$;
    """)


def downgrade() -> None:
    """Remove manual_arrival_time and manual_call_time columns from orders table"""
    op.drop_column('orders', 'manual_call_time')
    op.drop_column('orders', 'manual_arrival_time')

