"""
Тесты для REST API заказов
"""
import pytest
from datetime import date, time, datetime
from fastapi.testclient import TestClient
from unittest.mock import Mock, MagicMock, patch
from sqlalchemy.orm import Session

from src.api.main import app
from src.models.order import OrderDB
from src.application.dto.order_dto import OrderDTO, CreateOrderDTO, UpdateOrderDTO


@pytest.fixture
def client():
    """Тестовый клиент FastAPI"""
    return TestClient(app)


@pytest.fixture
def sample_order_dto():
    """Пример заказа в формате DTO"""
    return OrderDTO(
        id=1,
        user_id=123,
        order_date=date.today(),
        order_number="ORDER123",
        customer_name="Иван Иванов",
        phone="+79111234567",
        address="Москва, ул. Ленина, д. 1",
        latitude=55.7558,
        longitude=37.6173,
        comment="Тестовый заказ",
        delivery_time_start=time(10, 0),
        delivery_time_end=time(12, 0),
        delivery_time_window="10:00 - 12:00",
        status="pending",
        entrance_number="2",
        apartment_number="42"
    )


class TestOrdersAPI:
    """Тесты для Orders API"""
    
    @patch('src.api.routes.orders.get_container')
    @patch('src.api.routes.orders.get_current_user')
    @patch('src.api.routes.orders.get_db')
    def test_get_orders_success(
        self,
        mock_get_db,
        mock_get_current_user,
        mock_get_container,
        client,
        sample_order_dto
    ):
        """Тест успешного получения списка заказов"""
        from src.api.auth import User
        mock_get_current_user.return_value = User(user_id=123)
        
        # Мокаем контейнер и OrderService
        mock_container = MagicMock()
        mock_order_service = MagicMock()
        mock_order_service.get_orders_by_date.return_value = [sample_order_dto]
        mock_container.order_service.return_value = mock_order_service
        mock_get_container.return_value = mock_container
        
        # Мокаем сессию БД
        mock_db = MagicMock()
        mock_get_db.return_value = mock_db
        
        response = client.get(
            "/api/orders",
            headers={"Authorization": "Bearer 123"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert len(data["orders"]) == 1
        assert data["orders"][0]["order_number"] == "ORDER123"
        assert data["orders"][0]["customer_name"] == "Иван Иванов"
        assert data["orders"][0]["delivery_time_start"] == "10:00"
        assert data["orders"][0]["delivery_time_end"] == "12:00"
    
    @patch('src.api.routes.orders.get_container')
    @patch('src.api.routes.orders.get_current_user')
    @patch('src.api.routes.orders.get_db')
    def test_get_orders_with_status_filter(
        self,
        mock_get_db,
        mock_get_current_user,
        mock_get_container,
        client,
        sample_order_dto
    ):
        """Тест получения заказов с фильтром по статусу"""
        from src.api.auth import User
        mock_get_current_user.return_value = User(user_id=123)
        
        # Создаем заказы с разными статусами
        pending_order = sample_order_dto
        delivered_order = sample_order_dto.model_copy(update={
            "order_number": "ORDER456",
            "status": "delivered"
        })
        
        # Мокаем контейнер и OrderService
        mock_container = MagicMock()
        mock_order_service = MagicMock()
        mock_order_service.get_orders_by_date.return_value = [pending_order, delivered_order]
        mock_container.order_service.return_value = mock_order_service
        mock_get_container.return_value = mock_container
        
        mock_db = MagicMock()
        mock_get_db.return_value = mock_db
        
        # Фильтруем по статусу pending
        response = client.get(
            "/api/orders?status=pending",
            headers={"Authorization": "Bearer 123"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert data["orders"][0]["status"] == "pending"
    
    @patch('src.api.routes.orders.get_container')
    @patch('src.api.routes.orders.get_current_user')
    @patch('src.api.routes.orders.get_db')
    def test_get_orders_empty(
        self,
        mock_get_db,
        mock_get_current_user,
        mock_get_container,
        client
    ):
        """Тест получения пустого списка заказов"""
        from src.api.auth import User
        mock_get_current_user.return_value = User(user_id=123)
        
        # Мокаем контейнер и OrderService
        mock_container = MagicMock()
        mock_order_service = MagicMock()
        mock_order_service.get_orders_by_date.return_value = []
        mock_container.order_service.return_value = mock_order_service
        mock_get_container.return_value = mock_container
        
        mock_db = MagicMock()
        mock_get_db.return_value = mock_db
        
        response = client.get(
            "/api/orders",
            headers={"Authorization": "Bearer 123"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 0
        assert len(data["orders"]) == 0
    
    @patch('src.api.routes.orders.get_container')
    @patch('src.api.routes.orders.get_current_user')
    @patch('src.api.routes.orders.get_db')
    def test_get_order_by_number_success(
        self,
        mock_get_db,
        mock_get_current_user,
        mock_get_container,
        client,
        sample_order_dto
    ):
        """Тест успешного получения заказа по номеру"""
        from src.api.auth import User
        mock_get_current_user.return_value = User(user_id=123)
        
        # Мокаем контейнер и OrderService
        mock_container = MagicMock()
        mock_order_service = MagicMock()
        mock_order_service.get_order_by_number.return_value = sample_order_dto
        mock_container.order_service.return_value = mock_order_service
        mock_get_container.return_value = mock_container
        
        mock_db = MagicMock()
        mock_get_db.return_value = mock_db
        
        response = client.get(
            "/api/orders/ORDER123",
            headers={"Authorization": "Bearer 123"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["order_number"] == "ORDER123"
        assert data["customer_name"] == "Иван Иванов"
        assert data["address"] == "Москва, ул. Ленина, д. 1"
    
    @patch('src.api.routes.orders.get_container')
    @patch('src.api.routes.orders.get_current_user')
    @patch('src.api.routes.orders.get_db')
    def test_get_order_by_number_not_found(
        self,
        mock_get_db,
        mock_get_current_user,
        mock_get_container,
        client
    ):
        """Тест получения несуществующего заказа"""
        from src.api.auth import User
        mock_get_current_user.return_value = User(user_id=123)
        
        # Мокаем контейнер и OrderService
        mock_container = MagicMock()
        mock_order_service = MagicMock()
        mock_order_service.get_order_by_number.return_value = None
        mock_container.order_service.return_value = mock_order_service
        mock_get_container.return_value = mock_container
        
        mock_db = MagicMock()
        mock_get_db.return_value = mock_db
        
        response = client.get(
            "/api/orders/ORDER999",
            headers={"Authorization": "Bearer 123"}
        )
        
        assert response.status_code == 404
        assert "не найден" in response.json()["detail"].lower()
    
    @patch('src.api.routes.orders.get_container')
    @patch('src.api.routes.orders.get_current_user')
    @patch('src.api.routes.orders.get_db')
    def test_create_order_success(
        self,
        mock_get_db,
        mock_get_current_user,
        mock_get_container,
        client,
        sample_order_dto
    ):
        """Тест успешного создания заказа"""
        from src.api.auth import User
        mock_get_current_user.return_value = User(user_id=123)
        
        # Мокаем контейнер и OrderService
        mock_container = MagicMock()
        mock_order_service = MagicMock()
        mock_order_service.create_order.return_value = sample_order_dto
        mock_container.order_service.return_value = mock_order_service
        mock_get_container.return_value = mock_container
        
        mock_db = MagicMock()
        mock_get_db.return_value = mock_db
        
        order_data = {
            "order_number": "ORDER123",
            "customer_name": "Иван Иванов",
            "phone": "+79111234567",
            "address": "Москва, ул. Ленина, д. 1",
            "comment": "Тестовый заказ",
            "delivery_time_window": "10:00 - 12:00",
            "entrance_number": "2",
            "apartment_number": "42",
            "order_date": str(date.today())
        }
        
        response = client.post(
            "/api/orders",
            json=order_data,
            headers={"Authorization": "Bearer 123"}
        )
        
        assert response.status_code == 201
        data = response.json()
        assert data["order_number"] == "ORDER123"
        assert data["customer_name"] == "Иван Иванов"
        # Проверяем, что create_order был вызван
        mock_order_service.create_order.assert_called_once()
    
    @patch('src.api.routes.orders.get_container')
    @patch('src.api.routes.orders.get_current_user')
    @patch('src.api.routes.orders.get_db')
    def test_update_order_success(
        self,
        mock_get_db,
        mock_get_current_user,
        mock_get_container,
        client,
        sample_order_dto
    ):
        """Тест успешного обновления заказа"""
        from src.api.auth import User
        mock_get_current_user.return_value = User(user_id=123)
        
        # Обновленный заказ
        updated_order = sample_order_dto.model_copy(update={
            "customer_name": "Петр Петров",
            "phone": "+79119876543"
        })
        
        # Мокаем контейнер и OrderService
        mock_container = MagicMock()
        mock_order_service = MagicMock()
        mock_order_service.get_order_by_number.return_value = sample_order_dto
        mock_order_service.update_order.return_value = updated_order
        mock_container.order_service.return_value = mock_order_service
        mock_get_container.return_value = mock_container
        
        mock_db = MagicMock()
        mock_get_db.return_value = mock_db
        
        update_data = {
            "customer_name": "Петр Петров",
            "phone": "+79119876543"
        }
        
        response = client.put(
            "/api/orders/ORDER123",
            json=update_data,
            headers={"Authorization": "Bearer 123"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["customer_name"] == "Петр Петров"
        assert data["phone"] == "+79119876543"
        mock_order_service.update_order.assert_called_once()
    
    @patch('src.api.routes.orders.get_container')
    @patch('src.api.routes.orders.get_current_user')
    @patch('src.api.routes.orders.get_db')
    def test_update_order_not_found(
        self,
        mock_get_db,
        mock_get_current_user,
        mock_get_container,
        client
    ):
        """Тест обновления несуществующего заказа"""
        from src.api.auth import User
        mock_get_current_user.return_value = User(user_id=123)
        
        # Мокаем контейнер и OrderService
        mock_container = MagicMock()
        mock_order_service = MagicMock()
        mock_order_service.get_order_by_number.return_value = None
        mock_container.order_service.return_value = mock_order_service
        mock_get_container.return_value = mock_container
        
        mock_db = MagicMock()
        mock_get_db.return_value = mock_db
        
        update_data = {
            "customer_name": "Петр Петров"
        }
        
        response = client.put(
            "/api/orders/ORDER999",
            json=update_data,
            headers={"Authorization": "Bearer 123"}
        )
        
        assert response.status_code == 404
        assert "не найден" in response.json()["detail"].lower()
    
    @patch('src.api.routes.orders.get_container')
    @patch('src.api.routes.orders.get_current_user')
    @patch('src.api.routes.orders.get_db')
    def test_mark_order_delivered_success(
        self,
        mock_get_db,
        mock_get_current_user,
        mock_get_container,
        client,
        sample_order_dto
    ):
        """Тест успешной отметки заказа как доставленного"""
        from src.api.auth import User
        mock_get_current_user.return_value = User(user_id=123)
        
        delivered_order = sample_order_dto.model_copy(update={
            "status": "delivered"
        })
        
        # Мокаем контейнер и OrderService
        mock_container = MagicMock()
        mock_order_service = MagicMock()
        mock_order_service.mark_delivered.return_value = delivered_order
        mock_container.order_service.return_value = mock_order_service
        mock_get_container.return_value = mock_container
        
        mock_db = MagicMock()
        mock_get_db.return_value = mock_db
        
        response = client.post(
            "/api/orders/ORDER123/delivered",
            headers={"Authorization": "Bearer 123"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "delivered"
        mock_order_service.mark_delivered.assert_called_once()
    
    @patch('src.api.routes.orders.get_container')
    @patch('src.api.routes.orders.get_current_user')
    @patch('src.api.routes.orders.get_db')
    def test_mark_order_delivered_not_found(
        self,
        mock_get_db,
        mock_get_current_user,
        mock_get_container,
        client
    ):
        """Тест отметки несуществующего заказа как доставленного"""
        from src.api.auth import User
        mock_get_current_user.return_value = User(user_id=123)
        
        # Мокаем контейнер и OrderService
        mock_container = MagicMock()
        mock_order_service = MagicMock()
        mock_order_service.mark_delivered.return_value = None
        mock_container.order_service.return_value = mock_order_service
        mock_get_container.return_value = mock_container
        
        mock_db = MagicMock()
        mock_get_db.return_value = mock_db
        
        response = client.post(
            "/api/orders/ORDER999/delivered",
            headers={"Authorization": "Bearer 123"}
        )
        
        assert response.status_code == 404
        assert "не найден" in response.json()["detail"].lower()
    
    def test_get_orders_unauthorized(self, client):
        """Тест получения заказов без авторизации"""
        response = client.get("/api/orders")
        
        assert response.status_code == 403
    
    def test_get_orders_invalid_token(self, client):
        """Тест получения заказов с невалидным токеном"""
        response = client.get(
            "/api/orders",
            headers={"Authorization": "Bearer invalid_token"}
        )
        
        assert response.status_code == 401

