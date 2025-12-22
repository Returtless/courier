"""
Тесты для REST API навигации по маршрутам
"""
import pytest
from datetime import date, datetime, time
from fastapi.testclient import TestClient
from unittest.mock import Mock, MagicMock, patch
from sqlalchemy.orm import Session

from src.api.main import app
from src.models.order import RouteDataDB, OrderDB
from src.application.dto.route_dto import RouteDTO, RoutePointDTO


@pytest.fixture
def client():
    """Тестовый клиент FastAPI"""
    return TestClient(app)


@pytest.fixture
def mock_user():
    """Мок пользователя"""
    return {"user_id": 123}


@pytest.fixture
def sample_route_db():
    """Пример маршрута из БД"""
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


@pytest.fixture
def sample_order_db():
    """Пример заказа из БД"""
    order = OrderDB()
    order.id = 1
    order.user_id = 123
    order.order_date = date.today()
    order.order_number = "ORDER1"
    order.customer_name = "Иван Иванов"
    order.phone = "+79111234567"
    order.address = "Москва, ул. Ленина, д. 1"
    order.latitude = 55.7558
    order.longitude = 37.6173
    order.status = "pending"
    return order


class TestRoutesAPINavigation:
    """Тесты для API навигации по маршрутам"""
    
    @patch('src.api.routes.routes.get_container')
    @patch('src.api.routes.routes.get_current_user')
    def test_get_current_order_default_index(
        self,
        mock_get_current_user,
        mock_get_container,
        client,
        sample_route_db,
        sample_order_db
    ):
        """Тест получения текущего заказа без сохраненного индекса (должен вернуть первый)"""
        from src.api.auth import User
        mock_get_current_user.return_value = User(user_id=123)
        
        # Мокаем контейнер и сервисы
        mock_container = MagicMock()
        mock_route_service = MagicMock()
        mock_order_service = MagicMock()
        
        # Настраиваем RouteService
        route_dto = RouteDTO(
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
        mock_route_service.get_route.return_value = route_dto
        mock_route_service.get_current_order_index.return_value = 0  # По умолчанию 0
        mock_route_service.order_service = mock_order_service
        
        # Настраиваем OrderService
        from src.application.dto.order_dto import OrderDTO
        order_dto = OrderDTO(
            order_number="ORDER1",
            customer_name="Иван Иванов",
            phone="+79111234567",
            address="Москва, ул. Ленина, д. 1",
            latitude=55.7558,
            longitude=37.6173,
            status="pending"
        )
        mock_order_service.get_order_by_number.return_value = order_dto
        
        mock_container.route_service.return_value = mock_route_service
        mock_get_container.return_value = mock_container
        
        response = client.get(
            "/api/routes/current-order",
            headers={"Authorization": "Bearer 123"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["order_number"] == "ORDER1"
        assert data["address"] == "Москва, ул. Ленина, д. 1"
        assert data["latitude"] == 55.7558
        assert data["longitude"] == 37.6173
    
    @patch('src.api.routes.routes.get_container')
    @patch('src.api.routes.routes.get_current_user')
    def test_get_current_order_with_saved_index(
        self,
        mock_get_current_user,
        mock_get_container,
        client
    ):
        """Тест получения текущего заказа с сохраненным индексом"""
        from src.api.auth import User
        mock_get_current_user.return_value = User(user_id=123)
        
        # Мокаем контейнер и сервисы
        mock_container = MagicMock()
        mock_route_service = MagicMock()
        mock_order_service = MagicMock()
        
        # Настраиваем RouteService с сохраненным индексом 1
        route_dto = RouteDTO(
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
        mock_route_service.get_route.return_value = route_dto
        mock_route_service.get_current_order_index.return_value = 1  # Сохраненный индекс
        mock_route_service.order_service = mock_order_service
        
        # Настраиваем OrderService для второго заказа
        from src.application.dto.order_dto import OrderDTO
        order_dto = OrderDTO(
            order_number="ORDER2",
            customer_name="Мария Петрова",
            phone="+79117654321",
            address="Москва, ул. Пушкина, д. 2",
            latitude=55.7522,
            longitude=37.5989,
            status="pending"
        )
        mock_order_service.get_order_by_number.return_value = order_dto
        
        mock_container.route_service.return_value = mock_route_service
        mock_get_container.return_value = mock_container
        
        response = client.get(
            "/api/routes/current-order",
            headers={"Authorization": "Bearer 123"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["order_number"] == "ORDER2"
        assert data["address"] == "Москва, ул. Пушкина, д. 2"
        assert data["latitude"] == 55.7522
        assert data["longitude"] == 37.5989
    
    @patch('src.api.routes.routes.get_container')
    @patch('src.api.routes.routes.get_current_user')
    def test_set_current_order_index_success(
        self,
        mock_get_current_user,
        mock_get_container,
        client
    ):
        """Тест успешной установки текущего индекса заказа"""
        from src.api.auth import User
        mock_get_current_user.return_value = User(user_id=123)
        
        # Мокаем контейнер и сервисы
        mock_container = MagicMock()
        mock_route_service = MagicMock()
        mock_order_service = MagicMock()
        
        # Настраиваем RouteService
        route_dto = RouteDTO(
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
        mock_route_service.get_route.return_value = route_dto
        mock_route_service.set_current_order_index.return_value = True
        mock_route_service.order_service = mock_order_service
        
        # Настраиваем OrderService
        from src.application.dto.order_dto import OrderDTO
        order_dto = OrderDTO(
            order_number="ORDER2",
            customer_name="Мария Петрова",
            phone="+79117654321",
            address="Москва, ул. Пушкина, д. 2",
            latitude=55.7522,
            longitude=37.5989,
            status="pending"
        )
        mock_order_service.get_order_by_number.return_value = order_dto
        
        mock_container.route_service.return_value = mock_route_service
        mock_get_container.return_value = mock_container
        
        response = client.put(
            "/api/routes/current-order/1",
            headers={"Authorization": "Bearer 123"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["order_number"] == "ORDER2"
        # Проверяем, что метод был вызван с правильными параметрами
        call_args = mock_route_service.set_current_order_index.call_args
        assert call_args[0][0] == 123  # user_id
        assert call_args[0][1] == date.today()  # order_date
        assert call_args[0][2] == 1  # index
    
    @patch('src.api.routes.routes.get_container')
    @patch('src.api.routes.routes.get_current_user')
    def test_set_current_order_index_invalid_negative(
        self,
        mock_get_current_user,
        mock_get_container,
        client
    ):
        """Тест установки отрицательного индекса"""
        from src.api.auth import User
        mock_get_current_user.return_value = User(user_id=123)
        
        # Мокаем контейнер и сервисы
        mock_container = MagicMock()
        mock_route_service = MagicMock()
        
        route_dto = RouteDTO(
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
                )
            ],
            route_order=["ORDER1"],
            total_distance=0.0,
            total_time=0.0,
            estimated_completion=datetime.combine(date.today(), time(10, 0))
        )
        mock_route_service.get_route.return_value = route_dto
        
        mock_container.route_service.return_value = mock_route_service
        mock_get_container.return_value = mock_container
        
        response = client.put(
            "/api/routes/current-order/-1",
            headers={"Authorization": "Bearer 123"}
        )
        
        assert response.status_code == 400
        assert "вне диапазона" in response.json()["detail"].lower()
    
    @patch('src.api.routes.routes.get_container')
    @patch('src.api.routes.routes.get_current_user')
    def test_set_current_order_index_invalid_too_large(
        self,
        mock_get_current_user,
        mock_get_container,
        client
    ):
        """Тест установки индекса больше размера маршрута"""
        from src.api.auth import User
        mock_get_current_user.return_value = User(user_id=123)
        
        # Мокаем контейнер и сервисы
        mock_container = MagicMock()
        mock_route_service = MagicMock()
        
        route_dto = RouteDTO(
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
                )
            ],
            route_order=["ORDER1"],
            total_distance=0.0,
            total_time=0.0,
            estimated_completion=datetime.combine(date.today(), time(10, 0))
        )
        mock_route_service.get_route.return_value = route_dto
        
        mock_container.route_service.return_value = mock_route_service
        mock_get_container.return_value = mock_container
        
        response = client.put(
            "/api/routes/current-order/10",
            headers={"Authorization": "Bearer 123"}
        )
        
        assert response.status_code == 400
        assert "вне диапазона" in response.json()["detail"].lower()
    
    @patch('src.api.routes.routes.get_container')
    @patch('src.api.routes.routes.get_current_user')
    def test_set_current_order_index_route_not_found(
        self,
        mock_get_current_user,
        mock_get_container,
        client
    ):
        """Тест установки индекса для несуществующего маршрута"""
        from src.api.auth import User
        mock_get_current_user.return_value = User(user_id=123)
        
        # Мокаем контейнер и сервисы
        mock_container = MagicMock()
        mock_route_service = MagicMock()
        
        mock_route_service.get_route.return_value = None
        
        mock_container.route_service.return_value = mock_route_service
        mock_get_container.return_value = mock_container
        
        response = client.put(
            "/api/routes/current-order/1",
            headers={"Authorization": "Bearer 123"}
        )
        
        assert response.status_code == 404
        assert "не найден" in response.json()["detail"].lower()
    
    @patch('src.api.routes.routes.get_container')
    @patch('src.api.routes.routes.get_current_user')
    def test_get_current_order_route_not_found(
        self,
        mock_get_current_user,
        mock_get_container,
        client
    ):
        """Тест получения текущего заказа для несуществующего маршрута"""
        from src.api.auth import User
        mock_get_current_user.return_value = User(user_id=123)
        
        # Мокаем контейнер и сервисы
        mock_container = MagicMock()
        mock_route_service = MagicMock()
        
        mock_route_service.get_route.return_value = None
        
        mock_container.route_service.return_value = mock_route_service
        mock_get_container.return_value = mock_container
        
        response = client.get(
            "/api/routes/current-order",
            headers={"Authorization": "Bearer 123"}
        )
        
        assert response.status_code == 404
        assert "не найден" in response.json()["detail"].lower()

