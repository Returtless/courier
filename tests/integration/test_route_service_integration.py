"""
Integration тесты для RouteService
Тестируют взаимодействие RouteService с OrderService, репозиториями и БД
"""
import pytest
from datetime import date, time
from unittest.mock import Mock, MagicMock
from sqlalchemy.orm import Session

from src.application.services.route_service import RouteService
from src.application.services.order_service import OrderService
from src.application.dto.order_dto import CreateOrderDTO
from src.application.dto.route_dto import StartLocationDTO
from src.repositories.route_repository import RouteRepository
from src.repositories.order_repository import OrderRepository
from src.repositories.call_status_repository import CallStatusRepository
from src.services.maps_service import MapsService
from src.models.order import OrderDB


@pytest.fixture
def mock_maps_service():
    """Мок сервиса карт"""
    maps_service = Mock(spec=MapsService)
    
    # Дефолтные ответы для геокодирования
    maps_service.geocode_address_sync.return_value = (55.7558, 37.6173, "gis_id_123")
    
    # Дефолтные ответы для маршрутов (distance в км, time в минутах)
    # RouteOptimizer использует get_route_sync для построения матриц
    maps_service.get_route_sync.return_value = (1.0, 10)  # distance (km), time (min)
    
    return maps_service


@pytest.fixture
def order_repository():
    """Создает реальный репозиторий заказов"""
    return OrderRepository()


@pytest.fixture
def call_status_repository():
    """Создает реальный репозиторий статусов звонков"""
    return CallStatusRepository()


@pytest.fixture
def order_service(order_repository, call_status_repository):
    """Создает OrderService с реальными репозиториями"""
    return OrderService(order_repository, call_status_repository)


@pytest.fixture
def route_repository():
    """Создает реальный репозиторий маршрутов"""
    return RouteRepository()


@pytest.fixture
def mock_settings_service():
    """Мок сервиса настроек"""
    from unittest.mock import Mock
    from src.models.order import UserSettings
    
    mock_settings = Mock(spec=UserSettings)
    mock_settings.service_time_minutes = 10
    mock_settings.call_advance_minutes = 40
    mock_settings.call_retry_interval_minutes = 2
    mock_settings.call_max_attempts = 3
    mock_settings.parking_time_minutes = 7
    
    mock_service = Mock()
    mock_service.get_settings.return_value = mock_settings
    
    return mock_service


@pytest.fixture
def route_service(route_repository, order_service, call_status_repository, mock_maps_service, mock_settings_service):
    """Создает RouteService с реальными зависимостями"""
    service = RouteService(
        route_repository,
        order_service,
        call_status_repository,
        mock_maps_service
    )
    # Заменяем settings_service на мок (и в RouteService, и в RouteOptimizer)
    service.settings_service = mock_settings_service
    if hasattr(service, 'route_optimizer'):
        service.route_optimizer.settings_service = mock_settings_service
    return service


class TestRouteServiceIntegration:
    """Integration тесты для RouteService"""
    
    def test_full_route_cycle(
        self,
        route_service: RouteService,
        order_service: OrderService,
        test_db_session: Session,
        sample_order_data
    ):
        """Тест полного цикла: создание заказов → установка точки старта → оптимизация → навигация"""
        user_id = 123
        order_date = date.today()
        
        # 1. Создаем несколько заказов
        orders_data = [
            ("ORDER001", "Москва, Тверская, 1", 55.7558, 37.6173),
            ("ORDER002", "Москва, Арбат, 10", 55.7522, 37.5989),
            ("ORDER003", "Москва, Красная площадь, 1", 55.7539, 37.6208),
        ]
        
        for order_number, address, lat, lon in orders_data:
            create_dto = CreateOrderDTO(
                order_number=order_number,
                customer_name=f"Клиент {order_number}",
                phone="+79991234567",
                address=address,
                latitude=lat,
                longitude=lon
            )
            
            order_service.create_order(
                user_id, create_dto, order_date, test_db_session
            )
            test_db_session.commit()
        
        # 2. Устанавливаем точку старта
        start_location = StartLocationDTO(
            location_type="geo",
            address="Москва, Кремль",
            latitude=55.7520,
            longitude=37.6175
        )
        
        route_service.save_start_location(
            user_id, start_location, order_date, test_db_session
        )
        test_db_session.commit()
        
        # 3. Проверяем, что точка старта сохранена
        saved_start = route_service.get_start_location(
            user_id, order_date, test_db_session
        )
        
        assert saved_start is not None
        assert saved_start.address == "Москва, Кремль"
        assert saved_start.latitude == 55.7520
        assert saved_start.longitude == 37.6175
        
        # 4. Оптимизируем маршрут
        optimization_result = route_service.optimize_route(
            user_id, order_date, None, test_db_session
        )
        
        assert optimization_result.success is True
        assert optimization_result.route is not None
        assert optimization_result.route.total_distance > 0
        assert optimization_result.route.total_time > 0
        assert len(optimization_result.route.route_order) == 3
        test_db_session.commit()
        
        # 5. Получаем маршрут
        route = route_service.get_route(user_id, order_date, test_db_session)
        
        assert route is not None
        assert len(route.route_points) > 0
        
        # 6. Проверяем навигацию - устанавливаем текущий индекс
        route_service.set_current_order_index(
            user_id, order_date, 1, test_db_session
        )
        test_db_session.commit()
        
        # 7. Получаем текущий индекс
        current_index = route_service.get_current_order_index(
            user_id, order_date, test_db_session
        )
        
        assert current_index == 1
        
        # 8. Получаем текущий заказ по индексу
        route_updated = route_service.get_route(user_id, order_date, test_db_session)
        assert route_updated is not None
        
        # Проверяем, что route_points содержит точки маршрута
        assert len(route_updated.route_points) > 0
    
    def test_start_location_save_and_get(
        self,
        route_service: RouteService,
        test_db_session: Session
    ):
        """Тест сохранения и получения точки старта"""
        user_id = 123
        order_date = date.today()
        
        # Сохраняем точку старта
        start_location = StartLocationDTO(
            location_type="geo",
            address="Москва, Красная площадь, 1",
            latitude=55.7539,
            longitude=37.6208
        )
        
        route_service.save_start_location(
            user_id, start_location, order_date, test_db_session
        )
        test_db_session.commit()
        
        # Получаем точку старта
        retrieved = route_service.get_start_location(
            user_id, order_date, test_db_session
        )
        
        assert retrieved is not None
        assert retrieved.address == "Москва, Красная площадь, 1"
        assert retrieved.latitude == 55.7539
        assert retrieved.longitude == 37.6208
        
        # Обновляем точку старта
        new_start = StartLocationDTO(
            location_type="geo",
            address="Москва, Кремль",
            latitude=55.7520,
            longitude=37.6175
        )
        
        route_service.save_start_location(
            user_id, new_start, order_date, test_db_session
        )
        test_db_session.commit()
        
        # Проверяем обновление
        updated = route_service.get_start_location(
            user_id, order_date, test_db_session
        )
        
        assert updated.address == "Москва, Кремль"
        assert updated.latitude == 55.7520
    
    def test_route_optimization_with_orders(
        self,
        route_service: RouteService,
        order_service: OrderService,
        test_db_session: Session,
        sample_order_data
    ):
        """Тест оптимизации маршрута с заказами"""
        user_id = 123
        order_date = date.today()
        
        # Создаем заказы с координатами
        orders_data = [
            ("ORDER001", 55.7558, 37.6173),
            ("ORDER002", 55.7522, 37.5989),
        ]
        
        for order_number, lat, lon in orders_data:
            create_dto = CreateOrderDTO(
                order_number=order_number,
                customer_name=f"Клиент {order_number}",
                phone="+79991234567",
                address=f"Адрес {order_number}",
                latitude=lat,
                longitude=lon
            )
            
            order_service.create_order(
                user_id, create_dto, order_date, test_db_session
            )
            test_db_session.commit()
        
        # Устанавливаем точку старта
        start_location = StartLocationDTO(
            location_type="geo",
            address="Москва, Кремль",
            latitude=55.7520,
            longitude=37.6175
        )
        
        route_service.save_start_location(
            user_id, start_location, order_date, test_db_session
        )
        test_db_session.commit()
        
        # Оптимизируем маршрут
        result = route_service.optimize_route(
            user_id, order_date, None, test_db_session
        )
        
        assert result.success is True
        assert result.route is not None
        assert len(result.route.route_order) == 2
        assert result.route.total_distance > 0
        assert result.route.total_time > 0
        
        # Проверяем, что маршрут сохранен в БД
        route = route_service.get_route(user_id, order_date, test_db_session)
        assert route is not None
        assert len(route.route_points) == 2
    
    def test_navigation_current_order_index(
        self,
        route_service: RouteService,
        order_service: OrderService,
        test_db_session: Session,
        sample_order_data
    ):
        """Тест навигации: установка и получение текущего индекса заказа"""
        user_id = 123
        order_date = date.today()
        
        # Создаем заказы
        for i in range(1, 4):
            create_dto = CreateOrderDTO(
                order_number=f"ORDER{i:03d}",
                customer_name=f"Клиент {i}",
                phone="+79991234567",
                address=f"Адрес {i}",
                latitude=55.7558 + i * 0.001,
                longitude=37.6173 + i * 0.001
            )
            
            order_service.create_order(
                user_id, create_dto, order_date, test_db_session
            )
            test_db_session.commit()
        
        # Устанавливаем точку старта
        start_location = StartLocationDTO(
            location_type="geo",
            address="Москва, Кремль",
            latitude=55.7520,
            longitude=37.6175
        )
        
        route_service.save_start_location(
            user_id, start_location, order_date, test_db_session
        )
        test_db_session.commit()
        
        # Оптимизируем маршрут
        optimization_result = route_service.optimize_route(
            user_id, order_date, None, test_db_session
        )
        assert optimization_result.success is True
        test_db_session.commit()
        
        # Проверяем дефолтный индекс (должен быть 0)
        default_index = route_service.get_current_order_index(
            user_id, order_date, test_db_session
        )
        assert default_index == 0
        
        # Проверяем структуру route_summary перед установкой индекса
        route_before = route_service.route_repository.get_route(user_id, order_date, test_db_session)
        if route_before and route_before.route_summary:
            print(f"DEBUG: route_summary перед установкой индекса: {route_before.route_summary[:2] if len(route_before.route_summary) > 2 else route_before.route_summary}")
        
        # Устанавливаем индекс 1
        success = route_service.set_current_order_index(
            user_id, order_date, 1, test_db_session
        )
        assert success is True
        test_db_session.commit()
        test_db_session.expire_all()  # Обновляем кэш сессии
        
        # Проверяем структуру route_summary после установки индекса
        route_after = route_service.route_repository.get_route(user_id, order_date, test_db_session)
        if route_after and route_after.route_summary:
            print(f"DEBUG: route_summary после установки индекса: {route_after.route_summary[0] if len(route_after.route_summary) > 0 else 'empty'}")
        
        # Проверяем, что индекс установлен
        current_index = route_service.get_current_order_index(
            user_id, order_date, test_db_session
        )
        assert current_index == 1, f"Ожидался индекс 1, получен {current_index}. route_summary[0] = {route_after.route_summary[0] if route_after and route_after.route_summary else 'None'}"
        
        # Устанавливаем индекс 2
        success = route_service.set_current_order_index(
            user_id, order_date, 2, test_db_session
        )
        assert success is True
        test_db_session.commit()
        test_db_session.expire_all()  # Обновляем кэш сессии
        
        # Проверяем обновление
        updated_index = route_service.get_current_order_index(
            user_id, order_date, test_db_session
        )
        assert updated_index == 2, f"Ожидался индекс 2, получен {updated_index}"
    
    def test_route_optimization_no_orders(
        self,
        route_service: RouteService,
        test_db_session: Session
    ):
        """Тест оптимизации маршрута без заказов"""
        user_id = 123
        order_date = date.today()
        
        # Пытаемся оптимизировать без заказов
        result = route_service.optimize_route(
            user_id, order_date, None, test_db_session
        )
        
        assert result.success is False
        assert "нет активных заказов" in result.error_message.lower()
    
    def test_route_isolation_by_user(
        self,
        route_service: RouteService,
        order_service: OrderService,
        test_db_session: Session,
        sample_order_data
    ):
        """Тест изоляции маршрутов по пользователям"""
        user_id_1 = 123
        user_id_2 = 456
        order_date = date.today()
        
        # Создаем заказы для первого пользователя
        create_dto_1 = CreateOrderDTO(
            order_number="ORDER001",
            customer_name="Пользователь 1",
            phone="+79991111111",
            address="Адрес 1",
            latitude=55.7558,
            longitude=37.6173
        )
        
        order_service.create_order(
            user_id_1, create_dto_1, order_date, test_db_session
        )
        test_db_session.commit()
        
        # Создаем заказы для второго пользователя
        create_dto_2 = CreateOrderDTO(
            order_number="ORDER001",
            customer_name="Пользователь 2",
            phone="+79992222222",
            address="Адрес 2",
            latitude=55.7522,
            longitude=37.5989
        )
        
        order_service.create_order(
            user_id_2, create_dto_2, order_date, test_db_session
        )
        test_db_session.commit()
        
        # Устанавливаем точки старта для обоих пользователей
        start_location_1 = StartLocationDTO(
            location_type="geo",
            address="Адрес 1",
            latitude=55.7558,
            longitude=37.6173
        )
        
        start_location_2 = StartLocationDTO(
            location_type="geo",
            address="Адрес 2",
            latitude=55.7522,
            longitude=37.5989
        )
        
        route_service.save_start_location(
            user_id_1, start_location_1, order_date, test_db_session
        )
        route_service.save_start_location(
            user_id_2, start_location_2, order_date, test_db_session
        )
        test_db_session.commit()
        
        # Оптимизируем маршруты для обоих пользователей
        result_1 = route_service.optimize_route(
            user_id_1, order_date, None, test_db_session
        )
        result_2 = route_service.optimize_route(
            user_id_2, order_date, None, test_db_session
        )
        
        assert result_1.success is True
        assert result_2.success is True
        
        # Проверяем, что каждый пользователь видит только свой маршрут
        route_1 = route_service.get_route(user_id_1, order_date, test_db_session)
        route_2 = route_service.get_route(user_id_2, order_date, test_db_session)
        
        assert route_1 is not None
        assert route_2 is not None
        # Проверяем, что маршруты содержат правильные заказы
        assert len(route_1.route_order) == 1
        assert len(route_2.route_order) == 1

