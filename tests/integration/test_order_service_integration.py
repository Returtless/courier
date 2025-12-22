"""
Integration тесты для OrderService
Тестируют взаимодействие OrderService с репозиториями и БД
"""
import pytest
from datetime import date, time
from sqlalchemy.orm import Session

from src.application.services.order_service import OrderService
from src.application.dto.order_dto import CreateOrderDTO, UpdateOrderDTO
from src.repositories.order_repository import OrderRepository
from src.repositories.call_status_repository import CallStatusRepository
from src.models.order import OrderDB


@pytest.fixture
def order_repository():
    """Создает реальный репозиторий заказов"""
    return OrderRepository()


@pytest.fixture
def call_status_repository():
    """Создает реальный репозиторий статусов звонков"""
    return CallStatusRepository()


@pytest.fixture
def order_service(order_repository, call_status_repository):
    """Создает OrderService с реальными репозиториями"""
    return OrderService(order_repository, call_status_repository)


class TestOrderServiceIntegration:
    """Integration тесты для OrderService"""
    
    def test_full_order_lifecycle(
        self,
        order_service: OrderService,
        test_db_session: Session,
        sample_order_data
    ):
        """Тест полного цикла: создание → получение → обновление → доставка"""
        user_id = 123
        order_date = date.today()
        
        # 1. Создание заказа
        create_dto = CreateOrderDTO(
            order_number="ORDER001",
            customer_name=sample_order_data['customer_name'],
            phone=sample_order_data['phone'],
            address=sample_order_data['address'],
            comment=sample_order_data['comment'],
            delivery_time_window=sample_order_data['delivery_time_window'],
            entrance_number=sample_order_data['entrance_number'],
            apartment_number=sample_order_data['apartment_number']
        )
        
        created_order = order_service.create_order(
            user_id, create_dto, order_date, test_db_session
        )
        
        assert created_order is not None
        assert created_order.order_number == "ORDER001"
        assert created_order.customer_name == sample_order_data['customer_name']
        assert created_order.status == "pending"
        test_db_session.commit()
        
        # 2. Получение заказа по номеру
        retrieved_order = order_service.get_order_by_number(
            user_id, "ORDER001", order_date, test_db_session
        )
        
        assert retrieved_order is not None
        assert retrieved_order.order_number == "ORDER001"
        assert retrieved_order.customer_name == sample_order_data['customer_name']
        
        # 3. Получение всех заказов за дату
        all_orders = order_service.get_orders_by_date(
            user_id, order_date, test_db_session
        )
        
        assert len(all_orders) == 1
        assert all_orders[0].order_number == "ORDER001"
        
        # 4. Обновление заказа
        update_dto = UpdateOrderDTO(
            customer_name="Петр Петров",
            phone="+79998887766",
            comment="Обновленный комментарий"
        )
        
        updated_order = order_service.update_order(
            user_id, "ORDER001", update_dto, order_date, test_db_session
        )
        
        assert updated_order is not None
        assert updated_order.customer_name == "Петр Петров"
        assert updated_order.phone == "+79998887766"
        assert updated_order.comment == "Обновленный комментарий"
        test_db_session.commit()
        
        # 5. Проверка обновления в БД
        retrieved_updated = order_service.get_order_by_number(
            user_id, "ORDER001", order_date, test_db_session
        )
        
        assert retrieved_updated.customer_name == "Петр Петров"
        assert retrieved_updated.phone == "+79998887766"
        
        # 6. Отметка доставленным
        success = order_service.mark_delivered(
            user_id, "ORDER001", order_date, test_db_session
        )
        
        assert success is True
        test_db_session.commit()
        
        # 7. Проверка статуса в БД
        final_order = order_service.get_order_by_number(
            user_id, "ORDER001", order_date, test_db_session
        )
        
        assert final_order is not None
        assert final_order.status == "delivered"
    
    def test_multiple_orders_same_date(
        self,
        order_service: OrderService,
        test_db_session: Session,
        sample_order_data
    ):
        """Тест создания нескольких заказов за одну дату"""
        user_id = 123
        order_date = date.today()
        
        # Создаем 3 заказа
        orders_data = [
            ("ORDER001", "Иван Иванов", "+79991234567"),
            ("ORDER002", "Мария Петрова", "+79997654321"),
            ("ORDER003", "Петр Сидоров", "+79995555555"),
        ]
        
        created_orders = []
        for order_number, customer_name, phone in orders_data:
            create_dto = CreateOrderDTO(
                order_number=order_number,
                customer_name=customer_name,
                phone=phone,
                address=sample_order_data['address'],
                comment=f"Заказ {order_number}"
            )
            
            order = order_service.create_order(
                user_id, create_dto, order_date, test_db_session
            )
            created_orders.append(order)
            test_db_session.commit()
        
        # Получаем все заказы
        all_orders = order_service.get_orders_by_date(
            user_id, order_date, test_db_session
        )
        
        assert len(all_orders) == 3
        
        # Проверяем, что все заказы на месте
        order_numbers = {order.order_number for order in all_orders}
        assert order_numbers == {"ORDER001", "ORDER002", "ORDER003"}
        
        # Проверяем данные каждого заказа
        orders_dict = {order.order_number: order for order in all_orders}
        assert orders_dict["ORDER001"].customer_name == "Иван Иванов"
        assert orders_dict["ORDER002"].customer_name == "Мария Петрова"
        assert orders_dict["ORDER003"].customer_name == "Петр Сидоров"
    
    def test_order_isolation_by_user(
        self,
        order_service: OrderService,
        test_db_session: Session,
        sample_order_data
    ):
        """Тест изоляции заказов по пользователям"""
        user_id_1 = 123
        user_id_2 = 456
        order_date = date.today()
        
        # Создаем заказ для первого пользователя
        create_dto_1 = CreateOrderDTO(
            order_number="ORDER001",
            customer_name="Пользователь 1",
            phone="+79991111111",
            address=sample_order_data['address']
        )
        
        order_1 = order_service.create_order(
            user_id_1, create_dto_1, order_date, test_db_session
        )
        test_db_session.commit()
        
        # Создаем заказ для второго пользователя
        create_dto_2 = CreateOrderDTO(
            order_number="ORDER001",  # Тот же номер, но другой пользователь
            customer_name="Пользователь 2",
            phone="+79992222222",
            address=sample_order_data['address']
        )
        
        order_2 = order_service.create_order(
            user_id_2, create_dto_2, order_date, test_db_session
        )
        test_db_session.commit()
        
        # Проверяем, что каждый пользователь видит только свои заказы
        orders_user_1 = order_service.get_orders_by_date(
            user_id_1, order_date, test_db_session
        )
        orders_user_2 = order_service.get_orders_by_date(
            user_id_2, order_date, test_db_session
        )
        
        assert len(orders_user_1) == 1
        assert len(orders_user_2) == 1
        assert orders_user_1[0].customer_name == "Пользователь 1"
        assert orders_user_2[0].customer_name == "Пользователь 2"
        
        # Проверяем, что пользователь 1 не может получить заказ пользователя 2
        order_not_found = order_service.get_order_by_number(
            user_id_1, "ORDER001", order_date, test_db_session
        )
        # Должен вернуться заказ пользователя 1, так как номер совпадает
        # Но это нормально, так как номер заказа может быть не уникальным между пользователями
        assert order_not_found is not None
        assert order_not_found.customer_name == "Пользователь 1"
    
    def test_order_update_partial(
        self,
        order_service: OrderService,
        test_db_session: Session,
        sample_order_data
    ):
        """Тест частичного обновления заказа"""
        user_id = 123
        order_date = date.today()
        
        # Создаем заказ
        create_dto = CreateOrderDTO(
            order_number="ORDER001",
            customer_name="Иван Иванов",
            phone="+79991234567",
            address=sample_order_data['address'],
            comment="Исходный комментарий",
            entrance_number="1",
            apartment_number="10"
        )
        
        order = order_service.create_order(
            user_id, create_dto, order_date, test_db_session
        )
        test_db_session.commit()
        
        # Обновляем только телефон
        update_dto = UpdateOrderDTO(phone="+79998887766")
        
        updated_order = order_service.update_order(
            user_id, "ORDER001", update_dto, order_date, test_db_session
        )
        
        assert updated_order.phone == "+79998887766"
        # Остальные поля должны остаться без изменений
        assert updated_order.customer_name == "Иван Иванов"
        assert updated_order.comment == "Исходный комментарий"
        assert updated_order.entrance_number == "1"
        assert updated_order.apartment_number == "10"
        test_db_session.commit()
        
        # Проверяем в БД
        retrieved = order_service.get_order_by_number(
            user_id, "ORDER001", order_date, test_db_session
        )
        
        assert retrieved.phone == "+79998887766"
        assert retrieved.customer_name == "Иван Иванов"
    
    def test_get_delivered_orders(
        self,
        order_service: OrderService,
        test_db_session: Session,
        sample_order_data
    ):
        """Тест получения доставленных заказов"""
        user_id = 123
        order_date = date.today()
        
        # Создаем 3 заказа
        for i in range(1, 4):
            create_dto = CreateOrderDTO(
                order_number=f"ORDER{i:03d}",
                customer_name=f"Клиент {i}",
                phone=f"+7999123456{i}",
                address=sample_order_data['address']
            )
            
            order_service.create_order(
                user_id, create_dto, order_date, test_db_session
            )
            test_db_session.commit()
        
        # Отмечаем первые 2 как доставленные
        order_service.mark_delivered(user_id, "ORDER001", order_date, test_db_session)
        order_service.mark_delivered(user_id, "ORDER002", order_date, test_db_session)
        test_db_session.commit()
        
        # Получаем доставленные заказы
        delivered_orders = order_service.get_delivered_orders(
            user_id, order_date, test_db_session
        )
        
        assert len(delivered_orders) == 2
        order_numbers = {order.order_number for order in delivered_orders}
        assert order_numbers == {"ORDER001", "ORDER002"}
        
        # Проверяем, что все доставленные имеют статус "delivered"
        for order in delivered_orders:
            assert order.status == "delivered"
        
        # Проверяем, что ORDER003 не в списке доставленных
        all_orders = order_service.get_orders_by_date(
            user_id, order_date, test_db_session
        )
        pending_orders = [o for o in all_orders if o.status == "pending"]
        assert len(pending_orders) == 1
        assert pending_orders[0].order_number == "ORDER003"

