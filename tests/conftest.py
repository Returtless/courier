"""
Общие фикстуры для всех тестов
"""
import pytest
from datetime import datetime, date, time
from unittest.mock import Mock, MagicMock
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
# Импортируем все модели для создания таблиц в тестовой БД
from src.models.order import (
    Base, OrderDB, StartLocationDB, RouteDataDB, 
    CallStatusDB, UserSettingsDB, UserCredentialsDB
)
from src.models.geocache import GeocodeCacheDB


@pytest.fixture(scope="function")
def test_db_engine():
    """
    Создает тестовую БД в памяти для каждого теста
    """
    engine = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(engine)
    yield engine
    Base.metadata.drop_all(engine)
    engine.dispose()


@pytest.fixture(scope="function")
def test_db_session(test_db_engine):
    """
    Создает новую сессию БД для каждого теста
    После теста делает rollback
    """
    SessionLocal = sessionmaker(bind=test_db_engine)
    session = SessionLocal()
    
    try:
        yield session
    finally:
        session.rollback()
        session.close()


@pytest.fixture
def mock_db_session():
    """
    Мок сессии БД для изолированных тестов
    """
    session = MagicMock(spec=Session)
    return session


@pytest.fixture
def freeze_time():
    """
    Фиксирует текущее время для тестов
    """
    from freezegun import freeze_time as _freeze_time
    frozen_time = datetime(2025, 12, 15, 9, 0, 0)
    with _freeze_time(frozen_time):
        yield frozen_time


@pytest.fixture
def sample_user():
    """
    Тестовый пользователь
    """
    return {
        'user_id': 123,
        'username': 'test_courier',
        'first_name': 'Тестовый',
        'last_name': 'Курьер'
    }


@pytest.fixture
def sample_order_data():
    """
    Базовые данные заказа для тестов
    """
    return {
        'customer_name': 'Иван Иванов',
        'phone': '+79991234567',
        'address': 'Москва, Тверская улица, 1',
        'comment': 'Тестовый заказ',
        'delivery_time_window': '10:00 - 12:00',
        'entrance_number': '2',
        'apartment_number': '42'
    }


@pytest.fixture
def sample_order_with_coords():
    """
    Данные заказа с координатами
    """
    return {
        'customer_name': 'Мария Петрова',
        'phone': '+79997654321',
        'address': 'Москва, Арбат, 10',
        'latitude': 55.7522,
        'longitude': 37.5989,
        'delivery_time_window': '12:00 - 14:00'
    }


@pytest.fixture
def mock_telegram_bot():
    """
    Мок телеграм бота
    """
    bot = Mock()
    bot.send_message = Mock()
    bot.reply_to = Mock()
    bot.edit_message_text = Mock()
    return bot


@pytest.fixture
def mock_maps_service():
    """
    Мок сервиса карт с правильными возвращаемыми значениями
    """
    maps_service = Mock()
    
    # Дефолтные ответы
    maps_service.geocode_address_sync.return_value = (55.7558, 37.6173, "gis_id_123")
    
    # Для get_route_sync - возвращает кортеж (distance, time)
    maps_service.get_route_sync.return_value = (1000, 10)
    
    # Для get_route_distance_matrix_sync - возвращает две матрицы
    maps_service.get_route_distance_matrix_sync.return_value = (
        [[0, 1000], [1000, 0]],  # distance matrix (meters)
        [[0, 5], [5, 0]]  # time matrix (minutes)
    )
    
    return maps_service


@pytest.fixture
def mock_settings_service():
    """
    Мок сервиса настроек
    """
    settings_service = Mock()
    
    # Дефолтные настройки
    mock_settings = Mock()
    mock_settings.call_advance_time_minutes = 40
    mock_settings.service_time_minutes = 10
    mock_settings.traffic_monitoring_enabled = True
    mock_settings.max_call_attempts = 3
    mock_settings.call_retry_interval_minutes = 2
    
    settings_service.get_settings.return_value = mock_settings
    
    return settings_service
