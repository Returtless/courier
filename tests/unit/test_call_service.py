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

