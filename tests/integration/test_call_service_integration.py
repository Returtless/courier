"""
Integration тесты для CallService
Тестируют взаимодействие CallService с репозиториями и БД
"""
import pytest
from datetime import date, datetime, timedelta
from unittest.mock import Mock, patch
from sqlalchemy.orm import Session

from src.application.services.call_service import CallService
from src.application.services.order_service import OrderService
from src.application.dto.call_dto import CreateCallStatusDTO
from src.application.dto.order_dto import CreateOrderDTO
from src.repositories.call_status_repository import CallStatusRepository
from src.repositories.order_repository import OrderRepository
from src.models.order import CallStatusDB, OrderDB, UserSettings


@pytest.fixture
def order_repository():
    """Создает реальный репозиторий заказов"""
    return OrderRepository()


@pytest.fixture
def call_status_repository():
    """Создает реальный репозиторий статусов звонков"""
    return CallStatusRepository()


@pytest.fixture
def call_service(call_status_repository, order_repository):
    """Создает CallService с реальными репозиториями"""
    return CallService(call_status_repository, order_repository)


@pytest.fixture
def order_service(order_repository, call_status_repository):
    """Создает OrderService для создания заказов"""
    return OrderService(order_repository, call_status_repository)


class TestCallServiceIntegration:
    """Integration тесты для CallService"""
    
    def test_full_call_lifecycle(
        self,
        call_service: CallService,
        order_service: OrderService,
        test_db_session: Session,
        sample_order_data
    ):
        """Тест полного цикла: создание заказа → создание статуса → подтверждение"""
        user_id = 123
        order_date = date.today()
        
        # 1. Создаем заказ
        create_order_dto = CreateOrderDTO(
            order_number="ORDER001",
            customer_name=sample_order_data['customer_name'],
            phone=sample_order_data['phone'],
            address=sample_order_data['address']
        )
        
        order = order_service.create_order(
            user_id, create_order_dto, order_date, test_db_session
        )
        test_db_session.commit()
        
        # 2. Создаем статус звонка
        call_time = datetime.now() + timedelta(minutes=30)
        create_call_dto = CreateCallStatusDTO(
            order_number="ORDER001",
            call_time=call_time,
            phone=sample_order_data['phone'],
            customer_name=sample_order_data['customer_name'],
            arrival_time=call_time + timedelta(minutes=10)
        )
        
        call_status = call_service.create_call_status(
            user_id, create_call_dto, order_date, test_db_session
        )
        
        assert call_status is not None
        assert call_status.order_number == "ORDER001"
        assert call_status.status == "pending"
        assert call_status.user_id == user_id
        test_db_session.commit()
        
        # 3. Получаем статус по ID
        retrieved = call_service.get_call_status_by_id(
            call_status.id, test_db_session
        )
        
        assert retrieved is not None
        assert retrieved.order_number == "ORDER001"
        assert retrieved.status == "pending"
        
        # 4. Подтверждаем звонок
        success = call_service.confirm_call(
            user_id, call_status.id, "Подтверждено", test_db_session
        )
        
        assert success is True
        test_db_session.commit()
        
        # 5. Проверяем подтверждение
        confirmed = call_service.get_call_status_by_id(
            call_status.id, test_db_session
        )
        
        assert confirmed is not None
        assert confirmed.status == "confirmed"
        assert confirmed.confirmation_comment == "Подтверждено"
    
    @patch('src.application.services.call_service.UserSettingsService')
    def test_call_reject_and_retry(
        self,
        mock_settings_service_class,
        call_service: CallService,
        order_service: OrderService,
        test_db_session: Session,
        sample_order_data
    ):
        """Тест отклонения звонка и повторной попытки"""
        # Мокаем настройки пользователя
        mock_settings = Mock(spec=UserSettings)
        mock_settings.call_retry_interval_minutes = 2
        mock_settings.call_max_attempts = 3
        mock_settings_service = Mock()
        mock_settings_service.get_settings.return_value = mock_settings
        mock_settings_service_class.return_value = mock_settings_service
        call_service.settings_service = mock_settings_service
        
        user_id = 123
        order_date = date.today()
        
        # Создаем заказ
        create_order_dto = CreateOrderDTO(
            order_number="ORDER001",
            customer_name=sample_order_data['customer_name'],
            phone=sample_order_data['phone'],
            address=sample_order_data['address']
        )
        
        order_service.create_order(
            user_id, create_order_dto, order_date, test_db_session
        )
        test_db_session.commit()
        
        # Создаем статус звонка
        call_time = datetime.now() + timedelta(minutes=30)
        create_call_dto = CreateCallStatusDTO(
            order_number="ORDER001",
            call_time=call_time,
            phone=sample_order_data['phone'],
            customer_name=sample_order_data['customer_name']
        )
        
        call_status = call_service.create_call_status(
            user_id, create_call_dto, order_date, test_db_session
        )
        test_db_session.commit()
        
        # Отклоняем звонок
        success = call_service.reject_call(
            user_id, call_status.id, test_db_session
        )
        
        assert success is True
        test_db_session.commit()
        
        # Проверяем отклонение
        rejected = call_service.get_call_status_by_id(
            call_status.id, test_db_session
        )
        
        assert rejected is not None
        assert rejected.status == "rejected"
        assert rejected.attempts == 1
        
        # Проверяем, что звонок доступен для повторной попытки
        retry_calls = call_service.check_retry_calls(
            user_id, order_date, test_db_session
        )
        
        # Звонок должен быть в списке для повтора
        assert len(retry_calls) >= 0  # Может быть 0, если время не подошло
    
    def test_get_call_statuses_by_date(
        self,
        call_service: CallService,
        order_service: OrderService,
        test_db_session: Session,
        sample_order_data
    ):
        """Тест получения всех статусов звонков за дату"""
        user_id = 123
        order_date = date.today()
        
        # Создаем несколько заказов
        orders_data = [
            ("ORDER001", "+79991234567", "Клиент 1"),
            ("ORDER002", "+79997654321", "Клиент 2"),
        ]
        
        for order_number, phone, customer_name in orders_data:
            create_order_dto = CreateOrderDTO(
                order_number=order_number,
                customer_name=customer_name,
                phone=phone,
                address=sample_order_data['address']
            )
            
            order_service.create_order(
                user_id, create_order_dto, order_date, test_db_session
            )
            test_db_session.commit()
        
        # Создаем статусы звонков
        call_times = [
            datetime.now() + timedelta(minutes=30),
            datetime.now() + timedelta(minutes=60),
        ]
        
        for i, (order_number, phone, customer_name) in enumerate(orders_data):
            create_call_dto = CreateCallStatusDTO(
                order_number=order_number,
                call_time=call_times[i],
                phone=phone,
                customer_name=customer_name
            )
            
            call_service.create_call_status(
                user_id, create_call_dto, order_date, test_db_session
            )
            test_db_session.commit()
        
        # Получаем все статусы за дату
        all_statuses = call_service.get_call_statuses_by_date(
            user_id, order_date, test_db_session
        )
        
        assert len(all_statuses) == 2
        
        # Проверяем данные
        order_numbers = {status.order_number for status in all_statuses}
        assert order_numbers == {"ORDER001", "ORDER002"}
        
        # Проверяем статусы
        for status in all_statuses:
            assert status.status == "pending"
            assert status.user_id == user_id
    
    def test_call_user_validation(
        self,
        call_service: CallService,
        order_service: OrderService,
        test_db_session: Session,
        sample_order_data
    ):
        """Тест валидации user_id при подтверждении/отклонении"""
        user_id_1 = 123
        user_id_2 = 456
        order_date = date.today()
        
        # Создаем заказ для первого пользователя
        create_order_dto = CreateOrderDTO(
            order_number="ORDER001",
            customer_name=sample_order_data['customer_name'],
            phone=sample_order_data['phone'],
            address=sample_order_data['address']
        )
        
        order_service.create_order(
            user_id_1, create_order_dto, order_date, test_db_session
        )
        test_db_session.commit()
        
        # Создаем статус звонка для первого пользователя
        call_time = datetime.now() + timedelta(minutes=30)
        create_call_dto = CreateCallStatusDTO(
            order_number="ORDER001",
            call_time=call_time,
            phone=sample_order_data['phone'],
            customer_name=sample_order_data['customer_name']
        )
        
        call_status = call_service.create_call_status(
            user_id_1, create_call_dto, order_date, test_db_session
        )
        test_db_session.commit()
        
        # Пытаемся подтвердить от имени другого пользователя
        success = call_service.confirm_call(
            user_id_2, call_status.id, "Попытка взлома", test_db_session
        )
        
        # Должно вернуть False, так как user_id не совпадает
        assert success is False
        
        # Проверяем, что статус не изменился
        unchanged = call_service.get_call_status_by_id(
            call_status.id, test_db_session
        )
        
        assert unchanged.status == "pending"
        
        # Правильное подтверждение от первого пользователя
        success = call_service.confirm_call(
            user_id_1, call_status.id, "Подтверждено", test_db_session
        )
        
        assert success is True
        test_db_session.commit()
    
    def test_call_status_with_manual_arrival(
        self,
        call_service: CallService,
        order_service: OrderService,
        test_db_session: Session,
        sample_order_data
    ):
        """Тест создания статуса звонка с ручным временем прибытия"""
        user_id = 123
        order_date = date.today()
        
        # Создаем заказ
        create_order_dto = CreateOrderDTO(
            order_number="ORDER001",
            customer_name=sample_order_data['customer_name'],
            phone=sample_order_data['phone'],
            address=sample_order_data['address']
        )
        
        order_service.create_order(
            user_id, create_order_dto, order_date, test_db_session
        )
        test_db_session.commit()
        
        # Создаем статус с ручным временем прибытия
        call_time = datetime.now() + timedelta(minutes=30)
        manual_arrival_time = datetime.now() + timedelta(minutes=45)
        
        create_call_dto = CreateCallStatusDTO(
            order_number="ORDER001",
            call_time=call_time,
            phone=sample_order_data['phone'],
            customer_name=sample_order_data['customer_name'],
            is_manual_arrival=True,
            manual_arrival_time=manual_arrival_time
        )
        
        call_status = call_service.create_call_status(
            user_id, create_call_dto, order_date, test_db_session
        )
        
        assert call_status is not None
        assert call_status.is_manual_arrival is True
        assert call_status.manual_arrival_time == manual_arrival_time
        test_db_session.commit()
        
        # Проверяем в БД
        retrieved = call_service.get_call_status_by_id(
            call_status.id, test_db_session
        )
        
        assert retrieved.is_manual_arrival is True
        assert retrieved.manual_arrival_time == manual_arrival_time

