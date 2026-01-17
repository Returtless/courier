"""Initial database schema

Revision ID: 000
Revises: 
Create Date: 2025-12-16 08:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
import logging

logger = logging.getLogger(__name__)


# revision identifiers, used by Alembic.
revision = '000'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    import sys
    print("🔄 [000_initial] Начало миграции 000_initial...", file=sys.stdout, flush=True)
    logger.info("🔄 Начало миграции 000_initial...")
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    print("✅ [000_initial] Inspector создан", file=sys.stdout, flush=True)
    logger.info("✅ Inspector создан")
    
    # Create orders table
    print("📋 [000_initial] Проверка таблицы 'orders'...", file=sys.stdout, flush=True)
    logger.info("📋 Проверка таблицы 'orders'...")
    if not inspector.has_table('orders'):
        print("📝 [000_initial] Создание таблицы 'orders'...", file=sys.stdout, flush=True)
        logger.info("📝 Создание таблицы 'orders'...")
        op.create_table(
        'orders',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('order_date', sa.Date(), nullable=False),
        sa.Column('customer_name', sa.String(), nullable=True),
        sa.Column('phone', sa.String(), nullable=True),
        sa.Column('address', sa.String(), nullable=False),
        sa.Column('latitude', sa.Float(), nullable=True),
        sa.Column('longitude', sa.Float(), nullable=True),
        sa.Column('comment', sa.Text(), nullable=True),
        sa.Column('delivery_time_start', sa.Time(), nullable=True),
        sa.Column('delivery_time_end', sa.Time(), nullable=True),
        sa.Column('delivery_time_window', sa.String(), nullable=True),
        sa.Column('status', sa.String(), nullable=True, server_default='pending'),
        sa.Column('order_number', sa.String(), nullable=True),
        sa.Column('entrance_number', sa.String(), nullable=True),
        sa.Column('apartment_number', sa.String(), nullable=True),
        sa.Column('gis_id', sa.String(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.Column('estimated_delivery_time', sa.DateTime(), nullable=True),
        sa.Column('call_time', sa.DateTime(), nullable=True),
        sa.Column('route_order', sa.Integer(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id', 'order_date', 'order_number', name='uq_orders_user_date_order')
    )
        op.create_index(op.f('ix_orders_id'), 'orders', ['id'], unique=False)
        op.create_index(op.f('ix_orders_user_id'), 'orders', ['user_id'], unique=False)
        op.create_index(op.f('ix_orders_order_date'), 'orders', ['order_date'], unique=False)
        op.create_index(op.f('ix_orders_order_number'), 'orders', ['order_number'], unique=False)
        logger.info("✅ Таблица 'orders' создана")
    else:
        logger.info("⏭️ Таблица 'orders' уже существует, пропускаем создание")

    # Create start_locations table
    logger.info("📋 Проверка таблицы 'start_locations'...")
    if not inspector.has_table('start_locations'):
        logger.info("📝 Создание таблицы 'start_locations'...")
        op.create_table(
        'start_locations',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('location_date', sa.Date(), nullable=False),
        sa.Column('location_type', sa.String(), nullable=False),
        sa.Column('address', sa.String(), nullable=True),
        sa.Column('latitude', sa.Float(), nullable=True),
        sa.Column('longitude', sa.Float(), nullable=True),
        sa.Column('start_time', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
        op.create_index(op.f('ix_start_locations_id'), 'start_locations', ['id'], unique=False)
        op.create_index(op.f('ix_start_locations_user_id'), 'start_locations', ['user_id'], unique=False)
        op.create_index(op.f('ix_start_locations_location_date'), 'start_locations', ['location_date'], unique=False)
        logger.info("✅ Таблица 'start_locations' создана")
    else:
        logger.info("⏭️ Таблица 'start_locations' уже существует, пропускаем создание")

    # Create route_data table
    logger.info("📋 Проверка таблицы 'route_data'...")
    if not inspector.has_table('route_data'):
        logger.info("📝 Создание таблицы 'route_data'...")
        op.create_table(
        'route_data',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('route_date', sa.Date(), nullable=False),
        sa.Column('route_summary', sa.JSON(), nullable=True),
        sa.Column('call_schedule', sa.JSON(), nullable=True),
        sa.Column('route_order', sa.JSON(), nullable=True),
        sa.Column('total_distance', sa.Float(), nullable=True),
        sa.Column('total_time', sa.Float(), nullable=True),
        sa.Column('estimated_completion', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
        op.create_index(op.f('ix_route_data_id'), 'route_data', ['id'], unique=False)
        op.create_index(op.f('ix_route_data_user_id'), 'route_data', ['user_id'], unique=False)
        op.create_index(op.f('ix_route_data_route_date'), 'route_data', ['route_date'], unique=False)
        logger.info("✅ Таблица 'route_data' создана")
    else:
        logger.info("⏭️ Таблица 'route_data' уже существует, пропускаем создание")

    # Create call_status table
    logger.info("📋 Проверка таблицы 'call_status'...")
    if not inspector.has_table('call_status'):
        logger.info("📝 Создание таблицы 'call_status'...")
        op.create_table(
        'call_status',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('order_number', sa.String(), nullable=False),
        sa.Column('call_date', sa.Date(), nullable=False),
        sa.Column('call_time', sa.DateTime(), nullable=False),
        sa.Column('arrival_time', sa.DateTime(), nullable=True),
        sa.Column('is_manual_call', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('is_manual_arrival', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('manual_arrival_time', sa.DateTime(), nullable=True),
        sa.Column('phone', sa.String(), nullable=False),
        sa.Column('customer_name', sa.String(), nullable=True),
        sa.Column('status', sa.String(), nullable=True, server_default='pending'),
        sa.Column('attempts', sa.Integer(), nullable=True, server_default='0'),
        sa.Column('next_attempt_time', sa.DateTime(), nullable=True),
        sa.Column('confirmation_comment', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id', 'call_date', 'order_number', name='uq_call_status_user_date_order')
    )
        op.create_index(op.f('ix_call_status_id'), 'call_status', ['id'], unique=False)
        op.create_index(op.f('ix_call_status_user_id'), 'call_status', ['user_id'], unique=False)
        op.create_index(op.f('ix_call_status_order_number'), 'call_status', ['order_number'], unique=False)
        op.create_index(op.f('ix_call_status_call_date'), 'call_status', ['call_date'], unique=False)
        op.create_index('idx_user_date', 'call_status', ['user_id', 'call_date'], unique=False)
        op.create_index('idx_status_time', 'call_status', ['status', 'call_time'], unique=False)
        logger.info("✅ Таблица 'call_status' создана")
    else:
        logger.info("⏭️ Таблица 'call_status' уже существует, проверяем столбцы...")
        # Проверяем и добавляем отсутствующие столбцы
        columns = [col['name'] for col in inspector.get_columns('call_status')]
        if 'arrival_time' not in columns:
            logger.info("📝 Добавление столбца 'arrival_time' в таблицу 'call_status'...")
            op.add_column('call_status', sa.Column('arrival_time', sa.DateTime(), nullable=True))
            logger.info("✅ Столбец 'arrival_time' добавлен")
        if 'is_manual_call' not in columns:
            logger.info("📝 Добавление столбца 'is_manual_call' в таблицу 'call_status'...")
            op.add_column('call_status', sa.Column('is_manual_call', sa.Boolean(), nullable=False, server_default=sa.false()))
            logger.info("✅ Столбец 'is_manual_call' добавлен")
        if 'is_manual_arrival' not in columns:
            logger.info("📝 Добавление столбца 'is_manual_arrival' в таблицу 'call_status'...")
            op.add_column('call_status', sa.Column('is_manual_arrival', sa.Boolean(), nullable=False, server_default=sa.false()))
            logger.info("✅ Столбец 'is_manual_arrival' добавлен")
        if 'manual_arrival_time' not in columns:
            logger.info("📝 Добавление столбца 'manual_arrival_time' в таблицу 'call_status'...")
            op.add_column('call_status', sa.Column('manual_arrival_time', sa.DateTime(), nullable=True))
            logger.info("✅ Столбец 'manual_arrival_time' добавлен")

    # Create user_settings table
    logger.info("📋 Проверка таблицы 'user_settings'...")
    if not inspector.has_table('user_settings'):
        logger.info("📝 Создание таблицы 'user_settings'...")
        op.create_table(
        'user_settings',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('call_advance_minutes', sa.Integer(), nullable=True, server_default='10'),
        sa.Column('call_retry_interval_minutes', sa.Integer(), nullable=True, server_default='2'),
        sa.Column('call_max_attempts', sa.Integer(), nullable=True, server_default='3'),
        sa.Column('service_time_minutes', sa.Integer(), nullable=True, server_default='10'),
        sa.Column('parking_time_minutes', sa.Integer(), nullable=True, server_default='7'),
        sa.Column('traffic_check_interval_minutes', sa.Integer(), nullable=True, server_default='5'),
        sa.Column('traffic_threshold_percent', sa.Integer(), nullable=True, server_default='50'),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
        op.create_index(op.f('ix_user_settings_id'), 'user_settings', ['id'], unique=False)
        op.create_index(op.f('ix_user_settings_user_id'), 'user_settings', ['user_id'], unique=True)
        logger.info("✅ Таблица 'user_settings' создана")
    else:
        logger.info("⏭️ Таблица 'user_settings' уже существует, пропускаем создание")

    # Create user_credentials table
    logger.info("📋 Проверка таблицы 'user_credentials'...")
    if not inspector.has_table('user_credentials'):
        logger.info("📝 Создание таблицы 'user_credentials'...")
        op.create_table(
        'user_credentials',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('site', sa.String(), nullable=False, server_default='chefmarket'),
        sa.Column('encrypted_login', sa.Text(), nullable=False),
        sa.Column('encrypted_password', sa.Text(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
        op.create_index(op.f('ix_user_credentials_id'), 'user_credentials', ['id'], unique=False)
        op.create_index(op.f('ix_user_credentials_user_id'), 'user_credentials', ['user_id'], unique=True)
        logger.info("✅ Таблица 'user_credentials' создана")
    else:
        logger.info("⏭️ Таблица 'user_credentials' уже существует, пропускаем создание")

    # Create geocode_cache table
    logger.info("📋 Проверка таблицы 'geocode_cache'...")
    if not inspector.has_table('geocode_cache'):
        logger.info("📝 Создание таблицы 'geocode_cache'...")
        op.create_table(
        'geocode_cache',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('address', sa.String(), nullable=False),
        sa.Column('latitude', sa.Float(), nullable=False),
        sa.Column('longitude', sa.Float(), nullable=False),
        sa.Column('gis_id', sa.String(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
        op.create_index(op.f('ix_geocode_cache_id'), 'geocode_cache', ['id'], unique=False)
        op.create_index('idx_address', 'geocode_cache', ['address'], unique=False)
        logger.info("✅ Таблица 'geocode_cache' создана")
    else:
        logger.info("⏭️ Таблица 'geocode_cache' уже существует, пропускаем создание")
    
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
    else:
        logger.info("⏭️ Таблица 'route_cache' уже существует, пропускаем создание")
    
    print("✅ [000_initial] Миграция 000_initial завершена успешно!", file=sys.stdout, flush=True)
    logger.info("✅ Миграция 000_initial завершена успешно!")


def downgrade():
    op.drop_table('route_cache')
    op.drop_table('geocode_cache')
    op.drop_table('user_credentials')
    op.drop_table('user_settings')
    op.drop_table('call_status')
    op.drop_table('route_data')
    op.drop_table('start_locations')
    op.drop_table('orders')

