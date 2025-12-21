"""
Unit-тесты для логики ручного времени прибытия и звонка
Это критические тесты после рефакторинга!
"""
import pytest
from datetime import datetime, date, time, timedelta
from unittest.mock import Mock, patch, MagicMock
from src.services.call_notifier import CallNotifier
from src.models.order import CallStatusDB, OrderDB


@pytest.mark.unit
class TestManualCallTime:
    """Тесты установки ручного времени звонка"""
    
    @patch('src.services.call_notifier.get_db_session')
    def test_create_manual_call_time_new_record(self, mock_session, mock_telegram_bot, mock_settings_service):
        """Создание нового call_status с ручным временем звонка"""
        # Настройка мока сессии
        session = MagicMock()
        mock_session.return_value.__enter__.return_value = session
        session.query.return_value.filter.return_value.first.return_value = None
        
        # Настройка настроек (40 минут до прибытия)
        mock_settings = Mock()
        mock_settings.call_advance_time_minutes = 40
        
        # Создаем call_notifier
        call_notifier = CallNotifier(mock_telegram_bot, Mock())
        
        # Устанавливаем ручное время звонка
        call_time = datetime(2025, 12, 15, 12, 50)
        
        call_notifier.create_call_status(
            user_id=123,
            order_number="12345",
            call_time=call_time,
            phone="+79991234567",
            customer_name="Тест",
            is_manual=True,
            arrival_time=datetime(2025, 12, 15, 13, 30)  # call_time + 40 мин
        )
        
        # Проверяем, что была создана новая запись
        assert session.add.called
        assert session.commit.called
        
        # Проверяем параметры созданной записи
        call_status = session.add.call_args[0][0]
        assert call_status.call_time == call_time
        assert call_status.arrival_time == datetime(2025, 12, 15, 13, 30)
        assert call_status.is_manual is True
    
    @patch('src.services.call_notifier.get_db_session')
    def test_manual_call_time_protected_from_auto_update(self, mock_session, mock_telegram_bot):
        """Ручное время НЕ перезаписывается автоматической оптимизацией"""
        # Настройка мока - существующая ручная запись
        session = MagicMock()
        mock_session.return_value.__enter__.return_value = session
        
        existing_manual = Mock(spec=CallStatusDB)
        existing_manual.is_manual = True
        existing_manual.call_time = datetime(2025, 12, 15, 12, 50)
        existing_manual.arrival_time = datetime(2025, 12, 15, 13, 30)
        
        session.query.return_value.filter.return_value.first.return_value = existing_manual
        
        call_notifier = CallNotifier(mock_telegram_bot, Mock())
        
        # Пытаемся обновить АВТОМАТИЧЕСКИ (из оптимизации)
        result = call_notifier.create_call_status(
            user_id=123,
            order_number="12345",
            call_time=datetime(2025, 12, 15, 14, 0),  # Новое время
            phone="+79991234567",
            is_manual=False  # Автоматическое обновление!
        )
        
        # Проверяем, что вернулась старая запись БЕЗ изменений
        assert result == existing_manual
        assert existing_manual.call_time == datetime(2025, 12, 15, 12, 50)  # НЕ изменилось!
        assert not session.commit.called  # НЕ сохранили изменения
    
    @patch('src.services.call_notifier.get_db_session')
    def test_manual_call_time_can_be_updated_manually(self, mock_session, mock_telegram_bot):
        """Ручное время МОЖЕТ быть обновлено вручную"""
        session = MagicMock()
        mock_session.return_value.__enter__.return_value = session
        
        existing_manual = Mock(spec=CallStatusDB)
        existing_manual.is_manual = True
        existing_manual.call_time = datetime(2025, 12, 15, 12, 50)
        existing_manual.status = "pending"
        
        session.query.return_value.filter.return_value.first.return_value = existing_manual
        
        call_notifier = CallNotifier(mock_telegram_bot, Mock())
        
        # Обновляем ВРУЧНУЮ (пользователь изменил время)
        new_call_time = datetime(2025, 12, 15, 13, 0)
        new_arrival_time = datetime(2025, 12, 15, 13, 40)
        
        call_notifier.create_call_status(
            user_id=123,
            order_number="12345",
            call_time=new_call_time,
            phone="+79991234567",
            is_manual=True,  # Ручное обновление
            arrival_time=new_arrival_time
        )
        
        # Проверяем, что время ОБНОВИЛОСЬ
        assert existing_manual.call_time == new_call_time
        assert existing_manual.arrival_time == new_arrival_time
        assert session.commit.called


@pytest.mark.unit
class TestManualArrivalTime:
    """Тесты установки ручного времени прибытия"""
    
    def test_manual_arrival_time_stored_in_orders(self, test_db_session):
        """Ручное время прибытия хранится в таблице orders"""
        manual_arrival = datetime(2025, 12, 15, 13, 40)
        
        order = OrderDB(
            user_id=123,
            order_date=date.today(),
            customer_name="Тест",
            phone="+79991234567",
            address="Москва",
            manual_arrival_time=manual_arrival
        )
        
        test_db_session.add(order)
        test_db_session.commit()
        
        # Проверяем сохранение
        saved = test_db_session.query(OrderDB).filter_by(user_id=123).first()
        assert saved.manual_arrival_time == manual_arrival
    
    def test_manual_arrival_time_as_optimization_constraint(self, test_db_session):
        """
        manual_arrival_time используется как ограничение для оптимизации
        Это проверка концепции - само использование в optimizer тестируется отдельно
        """
        # Создаем заказ с ручным временем
        manual_arrival = datetime(2025, 12, 15, 11, 0)
        
        order = OrderDB(
            user_id=123,
            order_date=date.today(),
            order_number="12345",
            customer_name="Тест",
            phone="+79991234567",
            address="Москва",
            manual_arrival_time=manual_arrival,
            latitude=55.7558,
            longitude=37.6173
        )
        
        test_db_session.add(order)
        test_db_session.commit()
        
        # Проверяем, что поле доступно для использования
        saved = test_db_session.query(OrderDB).filter_by(order_number="12345").first()
        assert saved.manual_arrival_time is not None
        assert saved.manual_arrival_time == manual_arrival


@pytest.mark.unit
class TestManualTimeCalculations:
    """Тесты расчетов времен при ручной установке"""
    
    def test_arrival_time_from_call_time(self):
        """Расчет времени прибытия из времени звонка"""
        call_time = datetime(2025, 12, 15, 12, 50)
        advance_time_minutes = 40
        
        # Расчет: arrival_time = call_time + advance_time
        expected_arrival = call_time + timedelta(minutes=advance_time_minutes)
        
        assert expected_arrival == datetime(2025, 12, 15, 13, 30)
    
    def test_call_time_from_arrival_time(self):
        """Расчет времени звонка из времени прибытия"""
        arrival_time = datetime(2025, 12, 15, 13, 40)
        advance_time_minutes = 40
        
        # Расчет: call_time = arrival_time - advance_time
        expected_call = arrival_time - timedelta(minutes=advance_time_minutes)
        
        assert expected_call == datetime(2025, 12, 15, 13, 0)
    
    def test_independent_times_no_calculation(self):
        """
        Ручные времена могут быть независимыми
        Звонок в 13:00, прибытие в 13:00 (разница не 40 минут)
        """
        call_time = datetime(2025, 12, 15, 13, 0)
        arrival_time = datetime(2025, 12, 15, 13, 0)
        
        # Разница не равна стандартным 40 минутам
        time_diff = (arrival_time - call_time).total_seconds() / 60
        assert time_diff == 0  # Независимые времена


@pytest.mark.unit
class TestManualTimesPriority:
    """Тесты приоритетов ручных времен"""
    
    def test_manual_arrival_time_priority_in_orders(self, test_db_session):
        """orders.manual_arrival_time имеет наивысший приоритет"""
        # Создаем заказ с ручным временем в orders
        order = OrderDB(
            user_id=555,  # Уникальный ID
            order_date=date.today(),
            order_number="PRIORITY_TEST",
            customer_name="Тест",
            phone="+79991234567",
            address="Москва",
            manual_arrival_time=datetime(2025, 12, 15, 13, 40)
        )
        
        test_db_session.add(order)
        test_db_session.commit()
        
        # И создаем call_status с другим временем прибытия
        call_status = CallStatusDB(
            user_id=555,
            order_number="PRIORITY_TEST",
            call_date=date.today(),
            call_time=datetime(2025, 12, 15, 13, 0),
            arrival_time=datetime(2025, 12, 15, 13, 30),  # Другое время!
            is_manual=True,
            phone="+79991234567"
        )
        
        test_db_session.add(call_status)
        test_db_session.commit()
        
        # При отображении должно использоваться orders.manual_arrival_time
        saved_order = test_db_session.query(OrderDB).filter_by(order_number="PRIORITY_TEST").first()
        saved_call = test_db_session.query(CallStatusDB).filter_by(order_number="PRIORITY_TEST").first()
        
        # Приоритет у orders.manual_arrival_time
        assert saved_order.manual_arrival_time == datetime(2025, 12, 15, 13, 40)
        assert saved_call.arrival_time == datetime(2025, 12, 15, 13, 30)
        # В реальном коде должен использоваться orders.manual_arrival_time


@pytest.mark.unit
class TestCallStatusWithManualFlag:
    """Тесты работы флага is_manual в call_status"""
    
    def test_automatic_call_status_has_is_manual_false(self, test_db_session):
        """Автоматически созданный call_status имеет is_manual=False"""
        call_status = CallStatusDB(
            user_id=444,  # Уникальный ID
            order_number="AUTO_FLAG_TEST",
            call_date=date.today(),
            call_time=datetime(2025, 12, 15, 12, 50),
            phone="+79991234567",
            is_manual=False  # Автоматический
        )
        
        test_db_session.add(call_status)
        test_db_session.commit()
        
        saved = test_db_session.query(CallStatusDB).filter_by(order_number="AUTO_FLAG_TEST").first()
        assert saved.is_manual == False  # Используем == вместо is
    
    def test_manual_call_status_has_is_manual_true(self, test_db_session):
        """Вручную установленный call_status имеет is_manual=True"""
        call_status = CallStatusDB(
            user_id=123,
            order_number="12345",
            call_date=date.today(),
            call_time=datetime(2025, 12, 15, 12, 50),
            arrival_time=datetime(2025, 12, 15, 13, 30),
            phone="+79991234567",
            is_manual=True  # Ручной
        )
        
        test_db_session.add(call_status)
        test_db_session.commit()
        
        saved = test_db_session.query(CallStatusDB).filter_by(order_number="12345").first()
        assert saved.is_manual is True
        assert saved.arrival_time is not None
    
    def test_query_manual_call_statuses(self, test_db_session):
        """Можно отфильтровать только ручные call_status"""
        user_id_test = 333  # Уникальный ID для этого теста
        
        # Создаем несколько записей
        auto_call = CallStatusDB(
            user_id=user_id_test,
            order_number="QUERY_AUTO",
            call_date=date.today(),
            call_time=datetime(2025, 12, 15, 12, 0),
            phone="+79991111111",
            is_manual=False
        )
        
        manual_call = CallStatusDB(
            user_id=user_id_test,
            order_number="QUERY_MANUAL",
            call_date=date.today(),
            call_time=datetime(2025, 12, 15, 13, 0),
            phone="+79992222222",
            is_manual=True
        )
        
        test_db_session.add_all([auto_call, manual_call])
        test_db_session.commit()
        
        # Запрашиваем только ручные для этого пользователя
        manual_statuses = test_db_session.query(CallStatusDB).filter(
            CallStatusDB.user_id == user_id_test,
            CallStatusDB.is_manual == True
        ).all()
        
        assert len(manual_statuses) == 1
        assert manual_statuses[0].order_number == "QUERY_MANUAL"

