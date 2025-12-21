"""
Unit-тесты для DatabaseService
"""
import pytest
from datetime import date, datetime, time
from unittest.mock import patch
from src.services.db_service import DatabaseService
from src.models.order import OrderDB, Order


@pytest.mark.unit
class TestDatabaseServiceOrders:
    """Тесты работы с заказами"""
    
    def test_save_order(self, test_db_session):
        """Сохранение заказа в БД"""
        db_service = DatabaseService()
        user_id = 100
        today = date.today()
        
        order = Order(
            customer_name='Иван Иванов',
            phone='+79991234567',
            address='Москва, Тверская 1',
            delivery_time_window='10:00 - 12:00',
            comment='Тестовый заказ'
        )
        
        with patch('src.services.db_service.get_db_session') as mock_session:
            mock_session.return_value.__enter__.return_value = test_db_session
            
            saved_order = db_service.save_order(user_id, order, today)
            
            assert saved_order is not None
            assert saved_order.customer_name == 'Иван Иванов'
            assert saved_order.user_id == user_id
            assert saved_order.status == 'pending'
    
    def test_get_today_orders(self, test_db_session):
        """Получение заказов на сегодня"""
        db_service = DatabaseService()
        user_id = 200
        today = date.today()
        
        # Создаем тестовый заказ напрямую
        order = OrderDB(
            user_id=user_id,
            order_date=today,
            order_number="TEST001",
            customer_name="Тест",
            phone="+79991234567",
            address="Москва",
            status="pending"
        )
        
        test_db_session.add(order)
        test_db_session.commit()
        
        with patch('src.services.db_service.get_db_session') as mock_session:
            mock_session.return_value.__enter__.return_value = test_db_session
            
            orders = db_service.get_today_orders(user_id)
            
            assert len(orders) > 0
            assert orders[0]['order_number'] == "TEST001"
            assert orders[0]['customer_name'] == "Тест"
    
    def test_update_order(self, test_db_session):
        """Обновление заказа"""
        db_service = DatabaseService()
        user_id = 300
        today = date.today()
        
        # Создаем заказ
        order = OrderDB(
            user_id=user_id,
            order_date=today,
            order_number="UPD001",
            customer_name="Старое имя",
            phone="+79991234567",
            address="Москва"
        )
        
        test_db_session.add(order)
        test_db_session.commit()
        
        with patch('src.services.db_service.get_db_session') as mock_session:
            mock_session.return_value.__enter__.return_value = test_db_session
            
            updates = {
                'customer_name': 'Новое имя',
                'phone': '+79999999999'
            }
            
            result = db_service.update_order(user_id, "UPD001", updates, today)
            
            assert result is True
            
            updated = test_db_session.query(OrderDB).filter_by(
                order_number="UPD001"
            ).first()
            
            assert updated.customer_name == 'Новое имя'
            assert updated.phone == '+79999999999'
    
    def test_delete_orders_by_date(self, test_db_session):
        """Удаление заказов за дату"""
        db_service = DatabaseService()
        user_id = 400
        today = date.today()
        
        # Создаем несколько заказов
        order1 = OrderDB(
            user_id=user_id,
            order_date=today,
            order_number="DEL001",
            customer_name="Для удаления 1",
            phone="+79991234567",
            address="Москва"
        )
        
        order2 = OrderDB(
            user_id=user_id,
            order_date=today,
            order_number="DEL002",
            customer_name="Для удаления 2",
            phone="+79991234568",
            address="Москва"
        )
        
        test_db_session.add_all([order1, order2])
        test_db_session.commit()
        
        with patch('src.services.db_service.get_db_session') as mock_session:
            mock_session.return_value.__enter__.return_value = test_db_session
            
            count = db_service.delete_orders_by_date(user_id, today)
            
            assert count == 2


@pytest.mark.unit
class TestDatabaseServiceEdgeCases:
    """Тесты граничных случаев"""
    
    def test_get_orders_empty(self, test_db_session):
        """Получение пустого списка заказов"""
        db_service = DatabaseService()
        user_id = 999
        
        with patch('src.services.db_service.get_db_session') as mock_session:
            mock_session.return_value.__enter__.return_value = test_db_session
            
            orders = db_service.get_today_orders(user_id)
            
            assert orders == []
    
    def test_order_with_manual_arrival_time(self, test_db_session):
        """Заказ с ручным временем прибытия сохраняется в БД (проверка на уровне модели)"""
        user_id = 777
        today = date.today()
        manual_time = datetime(2025, 12, 15, 13, 30)
        
        # Создаем OrderDB напрямую с ручным временем
        order_db = OrderDB(
            user_id=user_id,
            order_date=today,
            order_number="MANUAL_TIME_TEST",
            customer_name='Тест Manual Time',
            phone='+79991234567',
            address='Москва',
            manual_arrival_time=manual_time
        )
        
        test_db_session.add(order_db)
        test_db_session.commit()
        test_db_session.refresh(order_db)
        
        # Проверяем, что manual_arrival_time сохранилось
        assert order_db.manual_arrival_time == manual_time
        
        # Проверяем запросом к БД
        saved = test_db_session.query(OrderDB).filter_by(
            order_number="MANUAL_TIME_TEST"
        ).first()
        
        assert saved is not None
        assert saved.manual_arrival_time == manual_time
