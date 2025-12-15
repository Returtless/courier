"""
Unit-тесты для CallNotifier (сервис уведомлений о звонках)
"""
import pytest
from datetime import datetime, date, timedelta
from unittest.mock import Mock, patch, MagicMock
from src.services.call_notifier import CallNotifier
from src.models.order import CallStatusDB


@pytest.mark.unit
class TestCallNotifierCreation:
    """Тесты создания записей о звонках"""
    
    @patch('src.services.call_notifier.get_db_session')
    def test_create_new_call_status(self, mock_session, mock_telegram_bot):
        """Создание новой записи о звонке"""
        session = MagicMock()
        mock_session.return_value.__enter__.return_value = session
        session.query.return_value.filter.return_value.first.return_value = None
        
        call_notifier = CallNotifier(mock_telegram_bot, Mock())
        
        call_time = datetime(2025, 12, 15, 12, 50)
        
        call_notifier.create_call_status(
            user_id=123,
            order_number="12345",
            call_time=call_time,
            phone="+79991234567",
            customer_name="Иван Иванов"
        )
        
        # Проверяем создание
        assert session.add.called
        assert session.commit.called
        
        # Проверяем параметры
        added_status = session.add.call_args[0][0]
        assert added_status.user_id == 123
        assert added_status.order_number == "12345"
        assert added_status.call_time == call_time
        assert added_status.phone == "+79991234567"
        assert added_status.customer_name == "Иван Иванов"
        assert added_status.status == "pending"
        assert added_status.attempts == 0
    
    @patch('src.services.call_notifier.get_db_session')
    def test_update_existing_automatic_call_status(self, mock_session, mock_telegram_bot):
        """Обновление существующей автоматической записи"""
        session = MagicMock()
        mock_session.return_value.__enter__.return_value = session
        
        existing = Mock(spec=CallStatusDB)
        existing.is_manual = False
        existing.status = "pending"
        session.query.return_value.filter.return_value.first.return_value = existing
        
        call_notifier = CallNotifier(mock_telegram_bot, Mock())
        
        new_call_time = datetime(2025, 12, 15, 13, 0)
        
        call_notifier.create_call_status(
            user_id=123,
            order_number="12345",
            call_time=new_call_time,
            phone="+79999999999",
            is_manual=False
        )
        
        # Проверяем обновление
        assert existing.call_time == new_call_time
        assert existing.phone == "+79999999999"
        assert session.commit.called


@pytest.mark.unit
class TestCallNotifierEdgeCases:
    """Тесты граничных случаев"""
    
    @patch('src.services.call_notifier.get_db_session')
    def test_create_call_status_without_phone(self, mock_session, mock_telegram_bot):
        """Создание call_status без телефона (допустимо)"""
        session = MagicMock()
        mock_session.return_value.__enter__.return_value = session
        session.query.return_value.filter.return_value.first.return_value = None
        
        call_notifier = CallNotifier(mock_telegram_bot, Mock())
        
        # Создаем без телефона
        call_notifier.create_call_status(
            user_id=123,
            order_number="12345",
            call_time=datetime(2025, 12, 15, 12, 50),
            phone="Не указан"  # Или None
        )
        
        # Проверяем, что запись создана
        assert session.add.called
        assert session.commit.called
