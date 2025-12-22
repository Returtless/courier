"""
Тесты для OrderService
"""
import pytest
from datetime import date, time, datetime
from unittest.mock import Mock, MagicMock, patch
from sqlalchemy.orm import Session

from src.application.services.order_service import OrderService
from src.application.dto.order_dto import CreateOrderDTO, UpdateOrderDTO
from src.repositories.order_repository import OrderRepository
from src.repositories.call_status_repository import CallStatusRepository
from src.models.order import OrderDB, CallStatusDB


@pytest.fixture
def mock_order_repository():
    """Мок репозитория заказов"""
    return Mock(spec=OrderRepository)


@pytest.fixture
def mock_call_status_repository():
    """Мок репозитория статусов звонков"""
    return Mock(spec=CallStatusRepository)


@pytest.fixture
def order_service(mock_order_repository, mock_call_status_repository):
    """Сервис заказов с моками"""
    return OrderService(mock_order_repository, mock_call_status_repository)


@pytest.fixture
def sample_order_db():
    """Пример заказа из БД"""
    order = OrderDB()
    order.id = 1
    order.user_id = 123
    order.order_date = date.today()
    order.order_number = "12345"
    order.customer_name = "Иван Иванов"
    order.phone = "+79111234567"
    order.address = "Москва, ул. Ленина, д. 1"
    order.latitude = 55.7558
    order.longitude = 37.6173
    order.comment = "Комментарий"
    order.status = "pending"
    return order


class TestOrderService:
    """Тесты для OrderService"""
    
    def test_get_today_orders(self, order_service, mock_order_repository, mock_call_status_repository, sample_order_db):
        """Тест получения заказов за сегодня"""
        today = date.today()
        mock_order_repository.get_by_user_and_date.return_value = [sample_order_db]
        mock_call_status_repository.get_by_user_and_date.return_value = []
        
        orders = order_service.get_today_orders(123)
        
        assert len(orders) == 1
        assert orders[0].order_number == "12345"
        mock_order_repository.get_by_user_and_date.assert_called_once_with(123, today, None)
    
    def test_get_order_by_number(self, order_service, mock_order_repository, mock_call_status_repository, sample_order_db):
        """Тест получения заказа по номеру"""
        today = date.today()
        mock_order_repository.get_by_number.return_value = sample_order_db
        mock_call_status_repository.get_by_order.return_value = None
        
        order = order_service.get_order_by_number(123, "12345")
        
        assert order is not None
        assert order.order_number == "12345"
        mock_order_repository.get_by_number.assert_called_once_with(123, "12345", today, None)
    
    def test_get_order_by_number_not_found(self, order_service, mock_order_repository):
        """Тест получения несуществующего заказа"""
        mock_order_repository.get_by_number.return_value = None
        
        order = order_service.get_order_by_number(123, "99999")
        
        assert order is None
    
    def test_create_order(self, order_service, mock_order_repository, sample_order_db):
        """Тест создания заказа"""
        today = date.today()
        create_dto = CreateOrderDTO(
            order_number="12345",
            customer_name="Иван Иванов",
            phone="+79111234567",
            address="Москва, ул. Ленина, д. 1"
        )
        mock_order_repository.save.return_value = sample_order_db
        
        order = order_service.create_order(123, create_dto)
        
        assert order.order_number == "12345"
        mock_order_repository.save.assert_called_once()
        call_args = mock_order_repository.save.call_args
        assert call_args[0][0] == 123  # user_id
        assert call_args[0][2] == today  # order_date
    
    def test_update_order(self, order_service, mock_order_repository, mock_call_status_repository, sample_order_db):
        """Тест обновления заказа"""
        today = date.today()
        update_dto = UpdateOrderDTO(phone="+79999999999")
        mock_order_repository.get_by_number.return_value = sample_order_db
        mock_call_status_repository.get_by_order.return_value = None
        
        # Мокаем обновление через сессию
        mock_session = Mock(spec=Session)
        mock_session.commit = Mock()
        mock_session.refresh = Mock()
        
        order = order_service.update_order(123, "12345", update_dto, today, mock_session)
        
        assert order is not None
        assert order.phone == "+79999999999"
        mock_order_repository.get_by_number.assert_called_once_with(123, "12345", today, mock_session)
    
    def test_mark_delivered(self, order_service, mock_order_repository):
        """Тест отметки заказа как доставленного"""
        today = date.today()
        mock_order_repository.update_status.return_value = True
        
        result = order_service.mark_delivered(123, "12345")
        
        assert result is True
        mock_order_repository.update_status.assert_called_once_with(
            123, "12345", "delivered", today, None
        )
    
    def test_get_delivered_orders(self, order_service, mock_order_repository, mock_call_status_repository):
        """Тест получения доставленных заказов"""
        today = date.today()
        delivered_order = OrderDB()
        delivered_order.id = 1
        delivered_order.order_number = "12345"
        delivered_order.status = "delivered"
        delivered_order.address = "Адрес"
        
        pending_order = OrderDB()
        pending_order.id = 2
        pending_order.order_number = "12346"
        pending_order.status = "pending"
        pending_order.address = "Адрес 2"
        
        mock_order_repository.get_by_user_and_date.return_value = [delivered_order, pending_order]
        mock_call_status_repository.get_by_user_and_date.return_value = []
        
        orders = order_service.get_delivered_orders(123)
        
        assert len(orders) == 1
        assert orders[0].status == "delivered"
        assert orders[0].order_number == "12345"
    
    def test_parse_order_from_image(self, order_service):
        """Тест парсинга заказа из изображения"""
        # Мокаем ImageOrderParser
        with patch('src.application.services.order_service.ImageOrderParser') as mock_parser_class:
            mock_parser = Mock()
            mock_parser_class.return_value = mock_parser
            mock_parser.parse_order_from_image.return_value = {
                'order_number': '12345',
                'address': 'Москва, ул. Ленина, д. 1',
                'customer_name': 'Иван Иванов',
                'phone': '+79111234567'
            }
            
            image_data = b'fake_image_data'
            result = order_service.parse_order_from_image(123, image_data)
            
            assert result is not None
            assert result.order_number == '12345'
            assert result.address == 'Москва, ул. Ленина, д. 1'
            mock_parser.parse_order_from_image.assert_called_once_with(image_data)
    
    def test_parse_order_from_image_failed(self, order_service):
        """Тест парсинга заказа из изображения при ошибке"""
        with patch('src.application.services.order_service.ImageOrderParser') as mock_parser_class:
            mock_parser = Mock()
            mock_parser_class.return_value = mock_parser
            mock_parser.parse_order_from_image.return_value = None
            
            image_data = b'fake_image_data'
            result = order_service.parse_order_from_image(123, image_data)
            
            assert result is None
    
    def test_get_orders_by_date(self, order_service, mock_order_repository, mock_call_status_repository, sample_order_db):
        """Тест получения заказов за конкретную дату"""
        test_date = date(2025, 12, 15)
        mock_order_repository.get_by_user_and_date.return_value = [sample_order_db]
        mock_call_status_repository.get_by_user_and_date.return_value = []
        
        orders = order_service.get_orders_by_date(123, test_date)
        
        assert len(orders) == 1
        assert orders[0].order_number == "12345"
        mock_order_repository.get_by_user_and_date.assert_called_once_with(123, test_date, None)
    
    def test_get_orders_by_date_empty(self, order_service, mock_order_repository, mock_call_status_repository):
        """Тест получения заказов за дату (пустой список)"""
        test_date = date(2025, 12, 15)
        mock_order_repository.get_by_user_and_date.return_value = []
        mock_call_status_repository.get_by_user_and_date.return_value = []
        
        orders = order_service.get_orders_by_date(123, test_date)
        
        assert len(orders) == 0
        mock_order_repository.get_by_user_and_date.assert_called_once_with(123, test_date, None)

