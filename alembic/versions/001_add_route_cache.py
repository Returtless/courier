"""Add route_cache table

Revision ID: 001
Revises: 000
Create Date: 2026-01-17 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
import logging

logger = logging.getLogger(__name__)


# revision identifiers, used by Alembic.
revision = '001'
down_revision = '000'
branch_labels = None
depends_on = None


def upgrade():
    import sys
    print("🔄 [001_add_route_cache] Начало миграции...", file=sys.stdout, flush=True)
    logger.info("🔄 Начало миграции 001_add_route_cache...")
    
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    
    # Create route_cache table
    logger.info("📋 Проверка таблицы 'route_cache'...")
    if not inspector.has_table('route_cache'):
        logger.info("📝 Создание таблицы 'route_cache'...")
        op.create_table(
            'route_cache',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('start_lat', sa.Float(), nullable=False),
            sa.Column('start_lon', sa.Float(), nullable=False),
            sa.Column('end_lat', sa.Float(), nullable=False),
            sa.Column('end_lon', sa.Float(), nullable=False),
            sa.Column('distance_km', sa.Float(), nullable=False),
            sa.Column('time_minutes', sa.Float(), nullable=False),
            sa.Column('created_at', sa.DateTime(), nullable=True),
            sa.Column('updated_at', sa.DateTime(), nullable=True),
            sa.PrimaryKeyConstraint('id')
        )
        op.create_index(op.f('ix_route_cache_id'), 'route_cache', ['id'], unique=False)
        op.create_index('idx_route_coords', 'route_cache', ['start_lat', 'start_lon', 'end_lat', 'end_lon'], unique=False)
        logger.info("✅ Таблица 'route_cache' создана")
        print("✅ [001_add_route_cache] Таблица 'route_cache' создана", file=sys.stdout, flush=True)
    else:
        logger.info("⏭️ Таблица 'route_cache' уже существует, пропускаем создание")
        print("⏭️ [001_add_route_cache] Таблица 'route_cache' уже существует", file=sys.stdout, flush=True)
    
    print("✅ [001_add_route_cache] Миграция завершена успешно!", file=sys.stdout, flush=True)
    logger.info("✅ Миграция 001_add_route_cache завершена успешно!")


def downgrade():
    op.drop_index('idx_route_coords', table_name='route_cache')
    op.drop_index(op.f('ix_route_cache_id'), table_name='route_cache')
    op.drop_table('route_cache')
