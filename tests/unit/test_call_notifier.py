"""
Тесты для CallNotifier
"""
import pytest
from unittest.mock import Mock, MagicMock
from datetime import date, datetime
from src.services.call_notifier import CallNotifier
from src.application.services.call_service import CallService
from src.bot.services.telegram_notifier import TelegramNotifier
from src.application.dto.call_dto import CallNotificationDTO


@pytest.fixture
def mock_call_service():
    """Мок CallService"""
    return Mock(spec=CallService)


@pytest.fixture
def mock_notifier():
    """Мок Notifier"""
    return Mock(spec=TelegramNotifier)


@pytest.fixture
def call_notifier(mock_call_service, mock_notifier):
    """CallNotifier с моками"""
    return CallNotifier(mock_call_service, mock_notifier)


@pytest.fixture
def sample_notification():
    """Пример уведомления"""
    return CallNotificationDTO(
        call_status_id=1,
        user_id=123,
        order_number="12345",
        call_time=datetime.now(),
        phone="+79111234567",
        customer_name="Иван Иванов",
        message="Тестовое уведомление",
        attempts=0
    )


class TestCallNotifier:
    """Тесты для CallNotifier"""
    
    def test_start(self, call_notifier):
        """Тест запуска CallNotifier"""
        assert not call_notifier.running
        call_notifier.start()
        assert call_notifier.running
        assert call_notifier.thread is not None
        call_notifier.stop()
    
    def test_stop(self, call_notifier):
        """Тест остановки CallNotifier"""
        call_notifier.start()
        assert call_notifier.running
        call_notifier.stop()
        assert not call_notifier.running
    
    def test_check_pending_calls(
        self,
        call_notifier,
        mock_call_service,
        mock_notifier,
        sample_notification
    ):
        """Тест проверки pending звонков"""
        today = date.today()
        mock_call_service.check_pending_calls.return_value = [sample_notification]
        mock_notifier.send_call_notification.return_value = True
        
        call_notifier._check_pending_calls()
        
        mock_call_service.check_pending_calls.assert_called_once_with(
            user_id=None,
            call_date=today
        )
        mock_notifier.send_call_notification.assert_called_once_with(
            sample_notification,
            is_retry=False
        )
        mock_call_service.mark_notification_sent.assert_called_once_with(
            sample_notification.call_status_id,
            is_retry=False
        )
    
    def test_check_retry_calls(
        self,
        call_notifier,
        mock_call_service,
        mock_notifier,
        sample_notification
    ):
        """Тест проверки retry звонков"""
        today = date.today()
        mock_call_service.check_retry_calls.return_value = [sample_notification]
        mock_notifier.send_call_notification.return_value = True
        
        call_notifier._check_retry_calls()
        
        mock_call_service.check_retry_calls.assert_called_once_with(
            user_id=None,
            call_date=today
        )
        mock_notifier.send_call_notification.assert_called_once_with(
            sample_notification,
            is_retry=True
        )
        mock_call_service.mark_notification_sent.assert_called_once_with(
            sample_notification.call_status_id,
            is_retry=True
        )
    
    def test_create_call_status(
        self,
        call_notifier,
        mock_call_service
    ):
        """Тест создания статуса звонка"""
        from src.application.dto.call_dto import CreateCallStatusDTO, CallStatusDTO
        
        user_id = 123
        order_number = "12345"
        call_time = datetime.now()
        phone = "+79111234567"
        customer_name = "Иван Иванов"
        call_date = date.today()
        
        expected_dto = CallStatusDTO(
            id=1,
            order_number=order_number,
            call_time=call_time,
            phone=phone,
            customer_name=customer_name,
            status="pending"
        )
        mock_call_service.create_call_status.return_value = expected_dto
        
        result = call_notifier.create_call_status(
            user_id=user_id,
            order_number=order_number,
            call_time=call_time,
            phone=phone,
            customer_name=customer_name,
            call_date=call_date
        )
        
        assert result == expected_dto
        mock_call_service.create_call_status.assert_called_once()
        call_args = mock_call_service.create_call_status.call_args
        assert call_args[0][0] == user_id
        assert isinstance(call_args[0][1], CreateCallStatusDTO)
        assert call_args[0][2] == call_date
