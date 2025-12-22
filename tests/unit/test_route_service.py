"""
Тесты для RouteService
"""
import pytest
from datetime import date, datetime, time
from unittest.mock import Mock, MagicMock
from sqlalchemy.orm import Session

from src.application.services.route_service import RouteService
from src.application.dto.route_dto import RouteOptimizationRequest, StartLocationDTO
from src.repositories.route_repository import RouteRepository
from src.repositories.call_status_repository import CallStatusRepository
from src.application.services.order_service import OrderService
from src.services.maps_service import MapsService
from src.models.order import RouteDataDB, StartLocationDB, OptimizedRoute, RoutePoint, Order
from src.application.dto.route_dto import RoutePointDTO


@pytest.fixture
def mock_route_repository():
    """Мок репозитория маршрутов"""
    return Mock(spec=RouteRepository)


@pytest.fixture
def mock_order_service():
    """Мок сервиса заказов"""
    return Mock(spec=OrderService)


@pytest.fixture
def mock_call_status_repository():
    """Мок репозитория статусов звонков"""
    return Mock(spec=CallStatusRepository)


@pytest.fixture
def mock_maps_service():
    """Мок сервиса карт"""
    return Mock(spec=MapsService)


@pytest.fixture
def route_service(
    mock_route_repository,
    mock_order_service,
    mock_call_status_repository,
    mock_maps_service
):
    """Сервис маршрутов с моками"""
    return RouteService(
        mock_route_repository,
        mock_order_service,
        mock_call_status_repository,
        mock_maps_service
    )


@pytest.fixture
def sample_start_location_db():
    """Пример точки старта из БД"""
    location = StartLocationDB()
    location.id = 1
    location.user_id = 123
    location.location_date = date.today()
    location.location_type = "geo"
    location.latitude = 55.7558
    location.longitude = 37.6173
    location.start_time = datetime.combine(date.today(), time(9, 0))
    return location


@pytest.fixture
def sample_route_db():
    """Пример маршрута из БД с route_summary"""
    route = RouteDataDB()
    route.id = 1
    route.user_id = 123
    route.route_date = date.today()
    route.route_order = ["ORDER1", "ORDER2", "ORDER3"]
    route.route_summary = [
        {
            "order_number": "ORDER1",
            "address": "Москва, ул. Ленина, д. 1",
            "estimated_arrival": datetime.combine(date.today(), time(10, 0)),
            "call_time": datetime.combine(date.today(), time(9, 20)),
            "distance_from_previous": 0.0,
            "time_from_previous": 0.0,
            "customer_name": "Иван Иванов",
            "phone": "+79111234567"
        },
        {
            "order_number": "ORDER2",
            "address": "Москва, ул. Пушкина, д. 2",
            "estimated_arrival": datetime.combine(date.today(), time(10, 30)),
            "call_time": datetime.combine(date.today(), time(9, 50)),
            "distance_from_previous": 5.0,
            "time_from_previous": 10.0,
            "customer_name": "Мария Петрова",
            "phone": "+79117654321"
        },
        {
            "order_number": "ORDER3",
            "address": "Москва, ул. Гагарина, д. 3",
            "estimated_arrival": datetime.combine(date.today(), time(11, 0)),
            "call_time": datetime.combine(date.today(), time(10, 20)),
            "distance_from_previous": 8.0,
            "time_from_previous": 15.0,
            "customer_name": "Петр Сидоров",
            "phone": "+79119876543"
        }
    ]
    route.total_distance = 13.0
    route.total_time = 25.0
    route.estimated_completion = datetime.combine(date.today(), time(11, 0))
    return route


class TestRouteService:
    """Тесты для RouteService"""
    
    def test_get_start_location(
        self,
        route_service,
        mock_route_repository,
        sample_start_location_db
    ):
        """Тест получения точки старта"""
        today = date.today()
        mock_route_repository.get_start_location.return_value = sample_start_location_db
        
        location = route_service.get_start_location(123, today)
        
        assert location is not None
        assert location.location_type == "geo"
        assert location.latitude == 55.7558
        mock_route_repository.get_start_location.assert_called_once_with(123, today, None)
    
    def test_get_start_location_not_found(
        self,
        route_service,
        mock_route_repository
    ):
        """Тест получения несуществующей точки старта"""
        mock_route_repository.get_start_location.return_value = None
        
        location = route_service.get_start_location(123)
        
        assert location is None
    
    def test_save_start_location(
        self,
        route_service,
        mock_route_repository,
        sample_start_location_db
    ):
        """Тест сохранения точки старта"""
        today = date.today()
        location_dto = StartLocationDTO(
            location_type="geo",
            latitude=55.7558,
            longitude=37.6173,
            start_time=datetime.combine(today, time(9, 0))
        )
        mock_route_repository.save_start_location.return_value = sample_start_location_db
        
        saved_location = route_service.save_start_location(123, location_dto, today)
        
        assert saved_location.location_type == "geo"
        mock_route_repository.save_start_location.assert_called_once()
    
    def test_get_route_not_found(
        self,
        route_service,
        mock_route_repository
    ):
        """Тест получения несуществующего маршрута"""
        mock_route_repository.get_route.return_value = None
        
        route = route_service.get_route(123)
        
        assert route is None
    
    def test_optimize_route_no_orders(
        self,
        route_service,
        mock_order_service,
        mock_route_repository
    ):
        """Тест оптимизации маршрута без заказов"""
        today = date.today()
        mock_order_service.get_orders_by_date.return_value = []
        
        result = route_service.optimize_route(123, today)
        
        assert result.success is False
        assert "Нет активных заказов" in result.error_message
    
    def test_optimize_route_no_start_location(
        self,
        route_service,
        mock_order_service,
        mock_route_repository
    ):
        """Тест оптимизации маршрута без точки старта"""
        today = date.today()
        from src.application.dto.order_dto import OrderDTO
        mock_order_service.get_orders_by_date.return_value = [
            OrderDTO(order_number="12345", address="Москва, ул. Ленина, д. 1")
        ]
        mock_route_repository.get_start_location.return_value = None
        
        result = route_service.optimize_route(123, today)
        
        assert result.success is False
        assert "Точка старта не установлена" in result.error_message
    
    def test_set_current_order_index_success(
        self,
        route_service,
        mock_route_repository,
        sample_route_db
    ):
        """Тест успешной установки текущего индекса заказа"""
        today = date.today()
        mock_route_repository.get_route.return_value = sample_route_db
        
        # Мокаем commit через session
        mock_session = MagicMock()
        mock_session.commit = MagicMock()
        # Устанавливаем, что объект уже в сессии
        if hasattr(sample_route_db, '_sa_instance_state'):
            sample_route_db._sa_instance_state = MagicMock()
        
        result = route_service.set_current_order_index(123, today, 1, mock_session)
        
        assert result is True
        # Проверяем, что индекс установлен в route_summary
        assert sample_route_db.route_summary[0].get('_current_index') == 1
        mock_session.commit.assert_called_once()
    
    def test_set_current_order_index_route_not_found(
        self,
        route_service,
        mock_route_repository
    ):
        """Тест установки индекса для несуществующего маршрута"""
        today = date.today()
        mock_route_repository.get_route.return_value = None
        
        result = route_service.set_current_order_index(123, today, 1)
        
        assert result is False
    
    def test_set_current_order_index_invalid_index_negative(
        self,
        route_service,
        mock_route_repository,
        sample_route_db
    ):
        """Тест установки отрицательного индекса"""
        today = date.today()
        mock_route_repository.get_route.return_value = sample_route_db
        
        result = route_service.set_current_order_index(123, today, -1)
        
        assert result is False
    
    def test_set_current_order_index_invalid_index_too_large(
        self,
        route_service,
        mock_route_repository,
        sample_route_db
    ):
        """Тест установки индекса больше размера маршрута"""
        today = date.today()
        mock_route_repository.get_route.return_value = sample_route_db
        
        result = route_service.set_current_order_index(123, today, 10)
        
        assert result is False
    
    def test_get_current_order_index_success(
        self,
        route_service,
        mock_route_repository,
        sample_route_db
    ):
        """Тест получения сохраненного индекса"""
        today = date.today()
        # Устанавливаем индекс в route_summary
        sample_route_db.route_summary[0]['_current_index'] = 2
        mock_route_repository.get_route.return_value = sample_route_db
        
        index = route_service.get_current_order_index(123, today)
        
        assert index == 2
    
    def test_get_current_order_index_default(
        self,
        route_service,
        mock_route_repository,
        sample_route_db
    ):
        """Тест получения индекса по умолчанию (0) когда индекс не установлен"""
        today = date.today()
        # Убираем _current_index из route_summary
        if '_current_index' in sample_route_db.route_summary[0]:
            del sample_route_db.route_summary[0]['_current_index']
        mock_route_repository.get_route.return_value = sample_route_db
        
        index = route_service.get_current_order_index(123, today)
        
        assert index == 0
    
    def test_get_current_order_index_route_not_found(
        self,
        route_service,
        mock_route_repository
    ):
        """Тест получения индекса для несуществующего маршрута"""
        today = date.today()
        mock_route_repository.get_route.return_value = None
        
        index = route_service.get_current_order_index(123, today)
        
        assert index == 0
    
    def test_get_current_order_index_empty_route_summary(
        self,
        route_service,
        mock_route_repository,
        sample_route_db
    ):
        """Тест получения индекса для маршрута с пустым route_summary"""
        today = date.today()
        sample_route_db.route_summary = []
        mock_route_repository.get_route.return_value = sample_route_db
        
        index = route_service.get_current_order_index(123, today)
        
        assert index == 0
    
    def test_set_and_get_current_order_index_cycle(
        self,
        route_service,
        mock_route_repository,
        sample_route_db
    ):
        """Тест полного цикла: установка индекса и его получение"""
        today = date.today()
        mock_route_repository.get_route.return_value = sample_route_db
        
        # Устанавливаем индекс
        mock_session = MagicMock()
        mock_session.commit = MagicMock()
        if hasattr(sample_route_db, '_sa_instance_state'):
            sample_route_db._sa_instance_state = MagicMock()
        
        set_result = route_service.set_current_order_index(123, today, 1, mock_session)
        assert set_result is True
        
        # Получаем индекс (используем тот же мок)
        index = route_service.get_current_order_index(123, today)
        assert index == 1

