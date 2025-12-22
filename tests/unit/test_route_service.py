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

