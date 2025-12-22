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
    
    def test_save_and_get_current_order_index(self, test_db_session):
        """Тест сохранения и получения current_order_index через route_summary"""
        from src.models.order import RouteDataDB
        repo = RouteRepository()
        test_date = date.today()
        user_id = 123
        
        # Создаем маршрут с current_order_index в route_summary
        route_data = {
            'route_summary': [{'_current_index': 2}, {'order': 'ORDER1'}, {'order': 'ORDER2'}, {'order': 'ORDER3'}],
            'route_order': ['ORDER1', 'ORDER2', 'ORDER3'],
            'call_schedule': [],
            'total_distance': 1000.0,
            'total_time': 600.0
        }
        
        # Сохраняем маршрут
        saved_route = repo.save_route(user_id, test_date, route_data, test_db_session)
        assert saved_route is not None
        assert saved_route.route_summary[0]['_current_index'] == 2
        
        # Получаем маршрут
        retrieved_route = repo.get_route(user_id, test_date, test_db_session)
        assert retrieved_route is not None
        assert retrieved_route.route_summary[0]['_current_index'] == 2
    
    def test_preserve_current_order_index_on_update(self, test_db_session):
        """Тест сохранения current_order_index при обновлении маршрута"""
        from src.models.order import RouteDataDB
        repo = RouteRepository()
        test_date = date.today()
        user_id = 123
        
        # Создаем начальный маршрут с current_order_index
        initial_route_data = {
            'route_summary': [{'_current_index': 1}, {'order': 'ORDER1'}, {'order': 'ORDER2'}],
            'route_order': ['ORDER1', 'ORDER2'],
            'call_schedule': [],
            'total_distance': 500.0,
            'total_time': 300.0
        }
        repo.save_route(user_id, test_date, initial_route_data, test_db_session)
        
        # Обновляем маршрут (без current_order_index в новых данных)
        updated_route_data = {
            'route_summary': [{'order': 'ORDER1'}, {'order': 'ORDER2'}, {'order': 'ORDER3'}],
            'route_order': ['ORDER1', 'ORDER2', 'ORDER3'],
            'call_schedule': [],
            'total_distance': 800.0,
            'total_time': 500.0
        }
        
        # Сохраняем обновленный маршрут
        updated_route = repo.save_route(user_id, test_date, updated_route_data, test_db_session)
        
        # Проверяем, что current_order_index сохранен
        assert updated_route is not None
        assert updated_route.route_summary[0]['_current_index'] == 1
        # Проверяем, что остальные данные обновились
        # current_index добавляется в первый элемент, поэтому длина остается 3
        assert len(updated_route.route_summary) == 3
        # Проверяем, что первый элемент содержит и current_index, и данные заказа
        assert 'order' in updated_route.route_summary[0]
        assert updated_route.route_summary[0]['order'] == 'ORDER1'
        assert updated_route.total_distance == 800.0


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
    
    def test_get_by_id(self, test_db_session):
        """Тест получения статуса звонка по ID"""
        from src.models.order import CallStatusDB
        repo = CallStatusRepository()
        
        # Создаем тестовый статус звонка
        call_status = CallStatusDB(
            user_id=123,
            order_number="3258104",
            call_date=date.today(),
            call_time=datetime(2025, 12, 15, 10, 0),
            phone="+79991234567",
            customer_name="Иван Иванов",
            status="pending"
        )
        test_db_session.add(call_status)
        test_db_session.commit()
        test_db_session.refresh(call_status)
        
        # Получаем по ID
        retrieved_status = repo.get(call_status.id, test_db_session)
        
        assert retrieved_status is not None
        assert retrieved_status.id == call_status.id
        assert retrieved_status.user_id == 123
        assert retrieved_status.order_number == "3258104"
        assert retrieved_status.status == "pending"
    
    def test_get_by_id_not_found(self, test_db_session):
        """Тест получения несуществующего статуса по ID"""
        repo = CallStatusRepository()
        status = repo.get(999999, test_db_session)
        assert status is None
    
    def test_get_by_user_and_date(self, test_db_session):
        """Тест получения статусов звонков по пользователю и дате"""
        from src.models.order import CallStatusDB
        repo = CallStatusRepository()
        test_date = date.today()
        
        # Создаем несколько статусов для одного пользователя
        call_status1 = CallStatusDB(
            user_id=123,
            order_number="3258104",
            call_date=test_date,
            call_time=datetime(2025, 12, 15, 10, 0),
            phone="+79991234567",
            customer_name="Иван Иванов",
            status="pending"
        )
        call_status2 = CallStatusDB(
            user_id=123,
            order_number="3258105",
            call_date=test_date,
            call_time=datetime(2025, 12, 15, 11, 0),
            phone="+79991234568",
            customer_name="Мария Петрова",
            status="confirmed"
        )
        # Статус для другого пользователя
        call_status3 = CallStatusDB(
            user_id=456,
            order_number="3258106",
            call_date=test_date,
            call_time=datetime(2025, 12, 15, 12, 0),
            phone="+79991234569",
            customer_name="Петр Сидоров",
            status="pending"
        )
        # Статус для другой даты
        call_status4 = CallStatusDB(
            user_id=123,
            order_number="3258107",
            call_date=date(2025, 12, 16),
            call_time=datetime(2025, 12, 16, 10, 0),
            phone="+79991234570",
            customer_name="Анна Смирнова",
            status="pending"
        )
        
        test_db_session.add_all([call_status1, call_status2, call_status3, call_status4])
        test_db_session.commit()
        
        # Получаем статусы для user_id=123 и test_date
        statuses = repo.get_by_user_and_date(123, test_date, test_db_session)
        
        assert len(statuses) == 2
        order_numbers = [s.order_number for s in statuses]
        assert "3258104" in order_numbers
        assert "3258105" in order_numbers
        assert "3258106" not in order_numbers  # Другой пользователь
        assert "3258107" not in order_numbers  # Другая дата
    
    def test_get_by_user_and_date_empty(self, test_db_session):
        """Тест получения статусов для несуществующего пользователя/даты"""
        repo = CallStatusRepository()
        statuses = repo.get_by_user_and_date(999999, date.today(), test_db_session)
        assert statuses == []


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

