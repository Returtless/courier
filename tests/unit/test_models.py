"""
Unit-тесты для моделей данных
"""
import pytest
from datetime import datetime, time, date
from src.models.order import Order, OrderDB, CallStatusDB


@pytest.mark.unit
class TestOrderModel:
    """Тесты модели Order (Pydantic)"""
    
    def test_order_creation_with_minimal_data(self):
        """Создание заказа с минимальными данными"""
        order = Order(
            customer_name="Тест",
            phone="+79991234567",
            address="Москва, Тверская 1"
        )
        
        assert order.customer_name == "Тест"
        assert order.phone == "+79991234567"
        assert order.address == "Москва, Тверская 1"
        assert order.status == "pending"
        assert order.latitude is None
        assert order.longitude is None
    
    def test_order_with_all_fields(self, sample_order_data):
        """Создание заказа со всеми полями"""
        order = Order(**sample_order_data)
        
        assert order.customer_name == sample_order_data['customer_name']
        assert order.phone == sample_order_data['phone']
        assert order.address == sample_order_data['address']
        assert order.comment == sample_order_data['comment']
        assert order.entrance_number == sample_order_data['entrance_number']
        assert order.apartment_number == sample_order_data['apartment_number']
    
    def test_order_time_window_parsing_valid(self):
        """Парсинг валидного временного окна"""
        order = Order(
            customer_name="Тест",
            phone="+79991234567",
            address="Москва, Тверская 1",
            delivery_time_window="14:00 - 16:00"
        )
        
        assert order.delivery_time_start == time(14, 0)
        assert order.delivery_time_end == time(16, 0)
        assert order.delivery_time_window == "14:00 - 16:00"
    
    def test_order_time_window_parsing_various_formats(self):
        """Парсинг разных форматов временного окна"""
        # Формат с пробелами
        order1 = Order(
            customer_name="Тест",
            phone="+79991234567",
            address="Москва",
            delivery_time_window="10:00 - 12:00"
        )
        assert order1.delivery_time_start == time(10, 0)
        assert order1.delivery_time_end == time(12, 0)
        
        # Формат без пробелов
        order2 = Order(
            customer_name="Тест",
            phone="+79991234567",
            address="Москва",
            delivery_time_window="10:00-12:00"
        )
        assert order2.delivery_time_start == time(10, 0)
        assert order2.delivery_time_end == time(12, 0)
    
    def test_order_time_window_parsing_invalid(self):
        """Парсинг невалидного временного окна"""
        order = Order(
            customer_name="Тест",
            phone="+79991234567",
            address="Москва",
            delivery_time_window="invalid format"
        )
        
        assert order.delivery_time_start is None
        assert order.delivery_time_end is None
    
    def test_order_with_manual_arrival_time(self):
        """Заказ с ручным временем прибытия"""
        manual_time = datetime(2025, 12, 15, 13, 30)
        
        order = Order(
            customer_name="Тест",
            phone="+79991234567",
            address="Москва",
            manual_arrival_time=manual_time
        )
        
        assert order.manual_arrival_time == manual_time
    
    def test_order_without_phone(self):
        """Заказ без телефона (допустимо)"""
        order = Order(
            customer_name="Тест",
            phone=None,
            address="Москва"
        )
        
        assert order.phone is None
        assert order.status == "pending"


@pytest.mark.unit
class TestOrderDB:
    """Тесты модели OrderDB (SQLAlchemy)"""
    
    def test_orderdb_creation(self, test_db_session):
        """Создание записи заказа в БД"""
        order_db = OrderDB(
            user_id=123,
            order_date=date.today(),
            customer_name="Тест",
            phone="+79991234567",
            address="Москва, Тверская 1",
            status="pending"
        )
        
        test_db_session.add(order_db)
        test_db_session.commit()
        
        # Проверяем, что запись создана
        saved_order = test_db_session.query(OrderDB).filter_by(user_id=123).first()
        assert saved_order is not None
        assert saved_order.customer_name == "Тест"
        assert saved_order.status == "pending"
    
    def test_orderdb_with_manual_arrival_time(self, test_db_session):
        """Сохранение ручного времени прибытия в БД"""
        manual_time = datetime(2025, 12, 15, 13, 30)
        
        order_db = OrderDB(
            user_id=777,  # Уникальный ID
            order_date=date.today(),
            customer_name="Тест Manual Time",
            phone="+79991234567",
            address="Москва",
            manual_arrival_time=manual_time
        )
        
        test_db_session.add(order_db)
        test_db_session.commit()
        
        saved_order = test_db_session.query(OrderDB).filter_by(user_id=777).first()
        assert saved_order.manual_arrival_time == manual_time
    
    def test_orderdb_no_manual_call_time_field(self, test_db_session):
        """Проверка отсутствия поля manual_call_time (удалено в рефакторинге)"""
        order_db = OrderDB(
            user_id=123,
            order_date=date.today(),
            customer_name="Тест",
            phone="+79991234567",
            address="Москва"
        )
        
        # Проверяем, что поля manual_call_time больше нет
        assert not hasattr(order_db, 'manual_call_time') or \
               'manual_call_time' not in OrderDB.__table__.columns


@pytest.mark.unit
class TestCallStatusDB:
    """Тесты модели CallStatusDB (SQLAlchemy)"""
    
    def test_call_status_creation(self, test_db_session):
        """Создание записи о звонке"""
        call_status = CallStatusDB(
            user_id=123,
            order_number="12345",
            call_date=date.today(),
            call_time=datetime(2025, 12, 15, 12, 50),
            phone="+79991234567",
            customer_name="Тест"
        )
        
        test_db_session.add(call_status)
        test_db_session.commit()
        
        saved = test_db_session.query(CallStatusDB).filter_by(order_number="12345").first()
        assert saved is not None
        assert saved.phone == "+79991234567"
        assert saved.status == "pending"
        assert saved.attempts == 0
    
    def test_call_status_with_manual_flag(self, test_db_session):
        """Запись о звонке с флагом ручной установки"""
        call_status = CallStatusDB(
            user_id=123,
            order_number="12345",
            call_date=date.today(),
            call_time=datetime(2025, 12, 15, 12, 50),
            arrival_time=datetime(2025, 12, 15, 13, 30),
            is_manual=True,
            phone="+79991234567",
            customer_name="Тест"
        )
        
        test_db_session.add(call_status)
        test_db_session.commit()
        
        saved = test_db_session.query(CallStatusDB).filter_by(order_number="12345").first()
        assert saved.is_manual is True
        assert saved.arrival_time == datetime(2025, 12, 15, 13, 30)
    
    def test_call_status_default_values(self, test_db_session):
        """Дефолтные значения при создании"""
        call_status = CallStatusDB(
            user_id=999,  # Уникальный ID
            order_number="DEFAULT_TEST",
            call_date=date.today(),
            call_time=datetime(2025, 12, 15, 12, 50),
            phone="+79991234567",
            is_manual=False  # Явно устанавливаем
        )
        
        test_db_session.add(call_status)
        test_db_session.commit()
        
        saved = test_db_session.query(CallStatusDB).filter_by(order_number="DEFAULT_TEST").first()
        assert saved.status == "pending"
        assert saved.attempts == 0
        assert saved.is_manual == False  # Используем == вместо is
        assert saved.arrival_time is None
    
    def test_call_status_update_attempts(self, test_db_session):
        """Обновление количества попыток"""
        call_status = CallStatusDB(
            user_id=888,  # Уникальный ID
            order_number="UPDATE_TEST",
            call_date=date.today(),
            call_time=datetime(2025, 12, 15, 12, 50),
            phone="+79991234567"
        )
        
        test_db_session.add(call_status)
        test_db_session.commit()
        test_db_session.refresh(call_status)  # Обновляем объект из БД
        
        # Увеличиваем попытки
        call_status.attempts = 1
        call_status.status = "sent"
        test_db_session.commit()
        
        saved = test_db_session.query(CallStatusDB).filter_by(order_number="UPDATE_TEST").first()
        assert saved.attempts == 1
        assert saved.status == "sent"

