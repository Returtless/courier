"""
Тесты для репозиториев
"""
import pytest
from datetime import date, datetime, time
from src.repositories.order_repository import OrderRepository
from src.repositories.route_repository import RouteRepository
from src.repositories.call_status_repository import CallStatusRepository
from src.models.order import Order
from src.application.container import get_container


class TestOrderRepository:
    """Тесты для OrderRepository"""
    
    def test_repository_initialization(self):
        """Проверка инициализации репозитория"""
        repo = OrderRepository()
        assert repo is not None
        assert repo.model_class.__name__ == "OrderDB"
    
    def test_get_by_user_and_date_empty(self):
        """Проверка получения заказов для несуществующего пользователя"""
        repo = OrderRepository()
        orders = repo.get_by_user_and_date(999999, date.today())
        assert orders == []
    
    # Дополнительные тесты требуют настройки тестовой БД
    # Будет добавлено позже с использованием fixtures


class TestRouteRepository:
    """Тесты для RouteRepository"""
    
    def test_repository_initialization(self):
        """Проверка инициализации репозитория"""
        repo = RouteRepository()
        assert repo is not None
        assert repo.route_data_repo.model_class.__name__ == "RouteDataDB"
        assert repo.start_location_repo.model_class.__name__ == "StartLocationDB"
    
    def test_get_route_empty(self):
        """Проверка получения маршрута для несуществующего пользователя"""
        repo = RouteRepository()
        route = repo.get_route(999999, date.today())
        assert route is None


class TestCallStatusRepository:
    """Тесты для CallStatusRepository"""
    
    def test_repository_initialization(self):
        """Проверка инициализации репозитория"""
        repo = CallStatusRepository()
        assert repo is not None
        assert repo.model_class.__name__ == "CallStatusDB"
    
    def test_get_by_order_empty(self):
        """Проверка получения статуса для несуществующего заказа"""
        repo = CallStatusRepository()
        status = repo.get_by_order(999999, "NONEXISTENT", date.today())
        assert status is None


class TestDIContainer:
    """Тесты для DI контейнера"""
    
    def test_container_initialization(self):
        """Проверка инициализации контейнера"""
        container = get_container()
        assert container is not None
    
    def test_repositories_in_container(self):
        """Проверка наличия репозиториев в контейнере"""
        container = get_container()
        
        # Проверяем, что репозитории зарегистрированы
        assert hasattr(container, 'order_repository')
        assert hasattr(container, 'route_repository')
        assert hasattr(container, 'call_status_repository')
    
    def test_repositories_singleton(self):
        """Проверка, что репозитории - singleton"""
        container = get_container()
        
        repo1 = container.order_repository()
        repo2 = container.order_repository()
        
        # Singleton должен возвращать один и тот же экземпляр
        assert repo1 is repo2
    
    def test_repositories_types(self):
        """Проверка типов репозиториев"""
        container = get_container()
        
        order_repo = container.order_repository()
        route_repo = container.route_repository()
        call_status_repo = container.call_status_repository()
        
        assert isinstance(order_repo, OrderRepository)
        assert isinstance(route_repo, RouteRepository)
        assert isinstance(call_status_repo, CallStatusRepository)

