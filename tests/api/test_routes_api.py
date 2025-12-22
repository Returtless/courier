"""
Тесты для REST API маршрутов (optimize, get routes, start-location)
"""
import pytest
from datetime import date, datetime, time
from fastapi.testclient import TestClient
from unittest.mock import Mock, MagicMock, patch
from sqlalchemy.orm import Session

from src.api.main import app
from src.application.dto.route_dto import (
    RouteDTO, RoutePointDTO, StartLocationDTO,
    RouteOptimizationRequest, RouteOptimizationResult
)


@pytest.fixture
def client():
    """Тестовый клиент FastAPI"""
    return TestClient(app)


@pytest.fixture
def sample_route_dto():
    """Пример маршрута в формате DTO"""
    return RouteDTO(
        route_points=[
            RoutePointDTO(
                order_number="ORDER1",
                address="Москва, ул. Ленина, д. 1",
                estimated_arrival=datetime.combine(date.today(), time(10, 0)),
                call_time=datetime.combine(date.today(), time(9, 20)),
                distance_from_previous=0.0,
                time_from_previous=0.0,
                customer_name="Иван Иванов",
                phone="+79111234567"
            ),
            RoutePointDTO(
                order_number="ORDER2",
                address="Москва, ул. Пушкина, д. 2",
                estimated_arrival=datetime.combine(date.today(), time(10, 30)),
                call_time=datetime.combine(date.today(), time(9, 50)),
                distance_from_previous=5.0,
                time_from_previous=10.0,
                customer_name="Мария Петрова",
                phone="+79117654321"
            )
        ],
        route_order=["ORDER1", "ORDER2"],
        total_distance=5.0,
        total_time=10.0,
        estimated_completion=datetime.combine(date.today(), time(10, 30))
    )


@pytest.fixture
def sample_start_location_dto():
    """Пример точки старта в формате DTO"""
    return StartLocationDTO(
        location_type="geo",
        latitude=55.7558,
        longitude=37.6173,
        start_time=datetime.combine(date.today(), time(9, 0))
    )


class TestRoutesAPIOptimize:
    """Тесты для POST /api/routes/optimize"""
    
    @patch('src.api.routes.routes.get_container')
    @patch('src.api.routes.routes.get_current_user')
    @patch('src.api.routes.routes.get_db')
    def test_optimize_route_success(
        self,
        mock_get_db,
        mock_get_current_user,
        mock_get_container,
        client,
        sample_route_dto
    ):
        """Тест успешной оптимизации маршрута"""
        from src.api.auth import User
        from src.application.dto.order_dto import OrderDTO
        mock_get_current_user.return_value = User(user_id=123)
        
        # Мокаем контейнер и RouteService
        mock_container = MagicMock()
        mock_route_service = MagicMock()
        mock_order_service = MagicMock()
        
        # Настраиваем успешный результат оптимизации
        result = RouteOptimizationResult(
            success=True,
            route=sample_route_dto
        )
        mock_route_service.optimize_route.return_value = result
        mock_route_service.order_service = mock_order_service
        
        # Мокаем заказы для получения координат
        order1 = OrderDTO(
            order_number="ORDER1",
            latitude=55.7558,
            longitude=37.6173,
            status="pending"
        )
        order2 = OrderDTO(
            order_number="ORDER2",
            latitude=55.7522,
            longitude=37.5989,
            status="pending"
        )
        mock_order_service.get_orders_by_date.return_value = [order1, order2]
        
        mock_container.route_service.return_value = mock_route_service
        mock_get_container.return_value = mock_container
        
        mock_db = MagicMock()
        mock_get_db.return_value = mock_db
        
        response = client.post(
            "/api/routes/optimize",
            json={},
            headers={"Authorization": "Bearer 123"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "route" in data
        assert len(data["route"]["route_points"]) == 2
        assert data["route"]["route_points"][0]["order_number"] == "ORDER1"
    
    @patch('src.api.routes.routes.get_container')
    @patch('src.api.routes.routes.get_current_user')
    @patch('src.api.routes.routes.get_db')
    def test_optimize_route_with_start_location(
        self,
        mock_get_db,
        mock_get_current_user,
        mock_get_container,
        client,
        sample_route_dto
    ):
        """Тест оптимизации маршрута с указанием точки старта"""
        from src.api.auth import User
        from src.application.dto.order_dto import OrderDTO
        mock_get_current_user.return_value = User(user_id=123)
        
        # Мокаем контейнер и RouteService
        mock_container = MagicMock()
        mock_route_service = MagicMock()
        mock_order_service = MagicMock()
        
        result = RouteOptimizationResult(
            success=True,
            route=sample_route_dto
        )
        mock_route_service.optimize_route.return_value = result
        mock_route_service.order_service = mock_order_service
        
        # Мокаем заказы для получения координат
        order1 = OrderDTO(order_number="ORDER1", latitude=55.7558, longitude=37.6173, status="pending")
        order2 = OrderDTO(order_number="ORDER2", latitude=55.7522, longitude=37.5989, status="pending")
        mock_order_service.get_orders_by_date.return_value = [order1, order2]
        
        mock_container.route_service.return_value = mock_route_service
        mock_get_container.return_value = mock_container
        
        mock_db = MagicMock()
        mock_get_db.return_value = mock_db
        
        response = client.post(
            "/api/routes/optimize",
            json={
                "start_location": {
                    "location_type": "geo",
                    "latitude": 55.7558,
                    "longitude": 37.6173,
                    "start_time": "2025-12-15T09:00:00"
                }
            },
            headers={"Authorization": "Bearer 123"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
    
    @patch('src.api.routes.routes.get_container')
    @patch('src.api.routes.routes.get_current_user')
    @patch('src.api.routes.routes.get_db')
    def test_optimize_route_without_orders(
        self,
        mock_get_db,
        mock_get_current_user,
        mock_get_container,
        client
    ):
        """Тест оптимизации маршрута без заказов"""
        from src.api.auth import User
        mock_get_current_user.return_value = User(user_id=123)
        
        # Мокаем контейнер и RouteService
        mock_container = MagicMock()
        mock_route_service = MagicMock()
        
        # Настраиваем результат с ошибкой
        result = RouteOptimizationResult(
            success=False,
            error_message="Нет активных заказов для оптимизации"
        )
        mock_route_service.optimize_route.return_value = result
        
        mock_container.route_service.return_value = mock_route_service
        mock_get_container.return_value = mock_container
        
        mock_db = MagicMock()
        mock_get_db.return_value = mock_db
        
        response = client.post(
            "/api/routes/optimize",
            json={},
            headers={"Authorization": "Bearer 123"}
        )
        
        assert response.status_code == 400
        data = response.json()
        assert "detail" in data
        assert "Нет активных заказов" in data["detail"]
    
    @patch('src.api.routes.routes.get_container')
    @patch('src.api.routes.routes.get_current_user')
    @patch('src.api.routes.routes.get_db')
    def test_optimize_route_recalculate_without_manual(
        self,
        mock_get_db,
        mock_get_current_user,
        mock_get_container,
        client,
        sample_route_dto
    ):
        """Тест оптимизации маршрута с recalculate_without_manual=True"""
        from src.api.auth import User
        from src.application.dto.order_dto import OrderDTO
        mock_get_current_user.return_value = User(user_id=123)
        
        # Мокаем контейнер и RouteService
        mock_container = MagicMock()
        mock_route_service = MagicMock()
        mock_order_service = MagicMock()
        
        result = RouteOptimizationResult(
            success=True,
            route=sample_route_dto
        )
        mock_route_service.optimize_route.return_value = result
        mock_route_service.order_service = mock_order_service
        
        # Мокаем заказы для получения координат
        order1 = OrderDTO(order_number="ORDER1", latitude=55.7558, longitude=37.6173, status="pending")
        order2 = OrderDTO(order_number="ORDER2", latitude=55.7522, longitude=37.5989, status="pending")
        mock_order_service.get_orders_by_date.return_value = [order1, order2]
        
        mock_container.route_service.return_value = mock_route_service
        mock_get_container.return_value = mock_container
        
        mock_db = MagicMock()
        mock_get_db.return_value = mock_db
        
        response = client.post(
            "/api/routes/optimize",
            json={
                "recalculate_without_manual": True
            },
            headers={"Authorization": "Bearer 123"}
        )
        
        assert response.status_code == 200
        # Проверяем, что optimize_route был вызван с recalculate_without_manual=True
        call_args = mock_route_service.optimize_route.call_args
        assert call_args is not None
        request = call_args.kwargs.get('request')
        assert request is not None
        assert request.recalculate_without_manual is True


class TestRoutesAPIGetRoute:
    """Тесты для GET /api/routes"""
    
    @patch('src.api.routes.routes.get_container')
    @patch('src.api.routes.routes.get_current_user')
    @patch('src.api.routes.routes.get_db')
    def test_get_route_success(
        self,
        mock_get_db,
        mock_get_current_user,
        mock_get_container,
        client,
        sample_route_dto
    ):
        """Тест успешного получения маршрута"""
        from src.api.auth import User
        from src.application.dto.order_dto import OrderDTO
        mock_get_current_user.return_value = User(user_id=123)
        
        # Мокаем контейнер и RouteService
        mock_container = MagicMock()
        mock_route_service = MagicMock()
        mock_order_service = MagicMock()
        
        mock_route_service.get_route.return_value = sample_route_dto
        mock_route_service.order_service = mock_order_service
        
        # Мокаем заказы для получения координат
        order1 = OrderDTO(order_number="ORDER1", latitude=55.7558, longitude=37.6173, status="pending")
        order2 = OrderDTO(order_number="ORDER2", latitude=55.7522, longitude=37.5989, status="pending")
        mock_order_service.get_orders_by_date.return_value = [order1, order2]
        
        mock_container.route_service.return_value = mock_route_service
        mock_get_container.return_value = mock_container
        
        mock_db = MagicMock()
        mock_get_db.return_value = mock_db
        
        response = client.get(
            "/api/routes",
            headers={"Authorization": "Bearer 123"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "route_date" in data
        assert len(data["route_points"]) == 2
        assert data["route_points"][0]["order_number"] == "ORDER1"
    
    @patch('src.api.routes.routes.get_container')
    @patch('src.api.routes.routes.get_current_user')
    @patch('src.api.routes.routes.get_db')
    def test_get_route_not_found(
        self,
        mock_get_db,
        mock_get_current_user,
        mock_get_container,
        client
    ):
        """Тест получения несуществующего маршрута"""
        from src.api.auth import User
        mock_get_current_user.return_value = User(user_id=123)
        
        # Мокаем контейнер и RouteService
        mock_container = MagicMock()
        mock_route_service = MagicMock()
        
        mock_route_service.get_route.return_value = None
        
        mock_container.route_service.return_value = mock_route_service
        mock_get_container.return_value = mock_container
        
        mock_db = MagicMock()
        mock_get_db.return_value = mock_db
        
        response = client.get(
            "/api/routes",
            headers={"Authorization": "Bearer 123"}
        )
        
        assert response.status_code == 404
        data = response.json()
        assert "detail" in data
        assert "не найден" in data["detail"].lower()


class TestRoutesAPIStartLocation:
    """Тесты для GET/PUT /api/routes/start-location"""
    
    @patch('src.api.routes.routes.get_container')
    @patch('src.api.routes.routes.get_current_user')
    @patch('src.api.routes.routes.get_db')
    def test_get_start_location_success(
        self,
        mock_get_db,
        mock_get_current_user,
        mock_get_container,
        client,
        sample_start_location_dto
    ):
        """Тест успешного получения точки старта"""
        from src.api.auth import User
        mock_get_current_user.return_value = User(user_id=123)
        
        # Мокаем контейнер и RouteService
        mock_container = MagicMock()
        mock_route_service = MagicMock()
        
        mock_route_service.get_start_location.return_value = sample_start_location_dto
        
        mock_container.route_service.return_value = mock_route_service
        mock_get_container.return_value = mock_container
        
        mock_db = MagicMock()
        mock_get_db.return_value = mock_db
        
        response = client.get(
            "/api/routes/start-location",
            headers={"Authorization": "Bearer 123"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["location_type"] == "geo"
        assert data["latitude"] == 55.7558
        assert data["longitude"] == 37.6173
    
    @patch('src.api.routes.routes.get_container')
    @patch('src.api.routes.routes.get_current_user')
    @patch('src.api.routes.routes.get_db')
    def test_get_start_location_not_found(
        self,
        mock_get_db,
        mock_get_current_user,
        mock_get_container,
        client
    ):
        """Тест получения несуществующей точки старта"""
        from src.api.auth import User
        mock_get_current_user.return_value = User(user_id=123)
        
        # Мокаем контейнер и RouteService
        mock_container = MagicMock()
        mock_route_service = MagicMock()
        
        mock_route_service.get_start_location.return_value = None
        
        mock_container.route_service.return_value = mock_route_service
        mock_get_container.return_value = mock_container
        
        mock_db = MagicMock()
        mock_get_db.return_value = mock_db
        
        response = client.get(
            "/api/routes/start-location",
            headers={"Authorization": "Bearer 123"}
        )
        
        assert response.status_code == 404
        data = response.json()
        assert "detail" in data
        assert "не установлена" in data["detail"].lower()
    
    @patch('src.api.routes.routes.get_container')
    @patch('src.api.routes.routes.get_current_user')
    @patch('src.api.routes.routes.get_db')
    def test_set_start_location_geo(
        self,
        mock_get_db,
        mock_get_current_user,
        mock_get_container,
        client,
        sample_start_location_dto
    ):
        """Тест установки точки старта через геопозицию"""
        from src.api.auth import User
        mock_get_current_user.return_value = User(user_id=123)
        
        # Мокаем контейнер и RouteService
        mock_container = MagicMock()
        mock_route_service = MagicMock()
        
        mock_route_service.save_start_location.return_value = sample_start_location_dto
        
        mock_container.route_service.return_value = mock_route_service
        mock_get_container.return_value = mock_container
        
        mock_db = MagicMock()
        mock_get_db.return_value = mock_db
        
        response = client.put(
            "/api/routes/start-location",
            json={
                "location_type": "geo",
                "latitude": 55.7558,
                "longitude": 37.6173,
                "start_time": "2025-12-15T09:00:00"
            },
            headers={"Authorization": "Bearer 123"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["location_type"] == "geo"
        assert data["latitude"] == 55.7558
        assert data["longitude"] == 37.6173
    
    @patch('src.api.routes.routes.get_container')
    @patch('src.api.routes.routes.get_current_user')
    @patch('src.api.routes.routes.get_db')
    def test_set_start_location_address(
        self,
        mock_get_db,
        mock_get_current_user,
        mock_get_container,
        client
    ):
        """Тест установки точки старта через адрес"""
        from src.api.auth import User
        mock_get_current_user.return_value = User(user_id=123)
        
        # Мокаем контейнер и RouteService
        mock_container = MagicMock()
        mock_route_service = MagicMock()
        
        location_dto = StartLocationDTO(
            location_type="address",
            address="Москва, Красная площадь, 1",
            start_time=datetime.combine(date.today(), time(9, 0))
        )
        mock_route_service.save_start_location.return_value = location_dto
        
        mock_container.route_service.return_value = mock_route_service
        mock_get_container.return_value = mock_container
        
        mock_db = MagicMock()
        mock_get_db.return_value = mock_db
        
        response = client.put(
            "/api/routes/start-location",
            json={
                "location_type": "address",
                "address": "Москва, Красная площадь, 1",
                "start_time": "2025-12-15T09:00:00"
            },
            headers={"Authorization": "Bearer 123"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["location_type"] == "address"
        assert data["address"] == "Москва, Красная площадь, 1"
