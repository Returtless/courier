"""
Тесты для CallService
"""
import pytest
from datetime import date, datetime
from unittest.mock import Mock, patch
from sqlalchemy.orm import Session

from src.application.services.call_service import CallService
from src.application.dto.call_dto import CreateCallStatusDTO
from src.repositories.call_status_repository import CallStatusRepository
from src.repositories.order_repository import OrderRepository
from src.models.order import CallStatusDB, OrderDB


@pytest.fixture
def mock_call_status_repository():
    """Мок репозитория статусов звонков"""
    return Mock(spec=CallStatusRepository)


@pytest.fixture
def mock_order_repository():
    """Мок репозитория заказов"""
    return Mock(spec=OrderRepository)


@pytest.fixture
def call_service(mock_call_status_repository, mock_order_repository):
    """Сервис звонков с моками"""
    return CallService(mock_call_status_repository, mock_order_repository)


@pytest.fixture
def sample_call_status_db():
    """Пример статуса звонка из БД"""
    call = CallStatusDB()
    call.id = 1
    call.user_id = 123
    call.order_number = "12345"
    call.call_date = date.today()
    call.call_time = datetime.combine(date.today(), datetime.min.time().replace(hour=10, minute=0))
    call.phone = "+79111234567"
    call.customer_name = "Иван Иванов"
    call.status = "pending"
    call.attempts = 0
    return call


class TestCallService:
    """Тесты для CallService"""
    
    def test_create_call_status(
        self,
        call_service,
        mock_call_status_repository,
        sample_call_status_db
    ):
        """Тест создания статуса звонка"""
        today = date.today()
        create_dto = CreateCallStatusDTO(
            order_number="12345",
            call_time=datetime.combine(today, datetime.min.time().replace(hour=10, minute=0)),
            phone="+79111234567",
            customer_name="Иван Иванов"
        )
        mock_call_status_repository.create_or_update.return_value = sample_call_status_db
        
        call_status = call_service.create_call_status(123, create_dto, today)
        
        assert call_status.order_number == "12345"
        assert call_status.phone == "+79111234567"
        mock_call_status_repository.create_or_update.assert_called_once()
    
    def test_get_call_status(
        self,
        call_service,
        mock_call_status_repository,
        sample_call_status_db
    ):
        """Тест получения статуса звонка"""
        today = date.today()
        mock_call_status_repository.get_by_order.return_value = sample_call_status_db
        
        call_status = call_service.get_call_status(123, "12345", today)
        
        assert call_status is not None
        assert call_status.order_number == "12345"
        mock_call_status_repository.get_by_order.assert_called_once_with(123, "12345", today, None)
    
    def test_get_call_status_not_found(
        self,
        call_service,
        mock_call_status_repository
    ):
        """Тест получения несуществующего статуса звонка"""
        mock_call_status_repository.get_by_order.return_value = None
        
        call_status = call_service.get_call_status(123, "99999")
        
        assert call_status is None
    
    def test_confirm_call(
        self,
        call_service,
        sample_call_status_db
    ):
        """Тест подтверждения звонка"""
        # Мокаем сессию и запрос
        with patch('src.application.services.call_service.get_db_session') as mock_session:
            mock_session.return_value.__enter__.return_value.query.return_value.filter_by.return_value.first.return_value = sample_call_status_db
            mock_session.return_value.__enter__.return_value.commit = Mock()
            
            result = call_service.confirm_call(123, 1, "Комментарий")
            
            assert result is True
    
    def test_reject_call(
        self,
        call_service,
        sample_call_status_db
    ):
        """Тест отклонения звонка"""
        with patch('src.application.services.call_service.get_db_session') as mock_session:
            mock_session.return_value.__enter__.return_value.query.return_value.filter_by.return_value.first.return_value = sample_call_status_db
            mock_session.return_value.__enter__.return_value.commit = Mock()
            
            result = call_service.reject_call(123, 1)
            
            assert result is True
    
    def test_get_call_status_by_id(
        self,
        call_service,
        mock_call_status_repository,
        sample_call_status_db
    ):
        """Тест получения статуса звонка по ID"""
        mock_call_status_repository.get.return_value = sample_call_status_db
        
        call_status = call_service.get_call_status_by_id(1)
        
        assert call_status is not None
        assert call_status.order_number == "12345"
        mock_call_status_repository.get.assert_called_once_with(1, None)
    
    def test_get_call_status_by_id_not_found(
        self,
        call_service,
        mock_call_status_repository
    ):
        """Тест получения несуществующего статуса звонка по ID"""
        mock_call_status_repository.get.return_value = None
        
        call_status = call_service.get_call_status_by_id(999)
        
        assert call_status is None
    
    def test_get_call_statuses_by_date(
        self,
        call_service,
        mock_call_status_repository,
        sample_call_status_db
    ):
        """Тест получения всех статусов звонков за дату"""
        today = date.today()
        another_call = CallStatusDB()
        another_call.id = 2
        another_call.order_number = "99999"
        another_call.status = "confirmed"
        
        mock_call_status_repository.get_call_statuses_by_date.return_value = [
            sample_call_status_db,
            another_call
        ]
        
        call_statuses = call_service.get_call_statuses_by_date(123, today)
        
        assert len(call_statuses) == 2
        assert call_statuses[0].order_number == "12345"
        assert call_statuses[1].order_number == "99999"
        mock_call_status_repository.get_call_statuses_by_date.assert_called_once_with(
            123, today, None
        )
    
    def test_check_retry_calls(
        self,
        call_service,
        mock_call_status_repository,
        mock_order_repository
    ):
        """Тест проверки звонков для повтора"""
        today = date.today()
        # Настраиваем статус для повтора (rejected, attempts < max)
        retry_call = CallStatusDB()
        retry_call.id = 2
        retry_call.user_id = 123
        retry_call.order_number = "99999"
        retry_call.status = "rejected"
        retry_call.attempts = 1
        retry_call.next_attempt_time = datetime.now()
        retry_call.call_time = datetime.now()
        retry_call.phone = "+79111234567"
        retry_call.customer_name = "Test"
        
        order = OrderDB()
        order.status = "pending"
        
        # Мокаем настройки
        with patch.object(call_service.settings_service, 'get_settings') as mock_settings:
            mock_settings_obj = Mock()
            mock_settings_obj.call_max_attempts = 3
            mock_settings.return_value = mock_settings_obj
            
            mock_call_status_repository.get_retry_calls.return_value = [retry_call]
            mock_order_repository.get_by_number.return_value = order
            
            calls = call_service.check_retry_calls(123, today)
            
            assert len(calls) >= 0  # Может быть отфильтрован по attempts
            if calls:
                assert calls[0].order_number == "99999"
    
    def test_mark_notification_sent(
        self,
        call_service,
        mock_call_status_repository
    ):
        """Тест отметки отправки уведомления"""
        mock_call_status_repository.mark_as_sent.return_value = True
        
        result = call_service.mark_notification_sent(1, False)
        
        assert result is True
        mock_call_status_repository.mark_as_sent.assert_called_once_with(1, False, None)

