"""
Сервис для работы с заказами
Содержит бизнес-логику работы с заказами
"""
import logging
from datetime import date, datetime, time
from typing import List, Optional, Dict
from sqlalchemy.orm import Session

from src.application.dto.order_dto import OrderDTO, CreateOrderDTO, UpdateOrderDTO
from src.repositories.order_repository import OrderRepository
from src.repositories.call_status_repository import CallStatusRepository
from src.models.order import Order

logger = logging.getLogger(__name__)


class OrderService:
    """Сервис для работы с заказами"""
    
    def __init__(
        self,
        order_repository: OrderRepository,
        call_status_repository: CallStatusRepository
    ):
        """
        Args:
            order_repository: Репозиторий для работы с заказами
            call_status_repository: Репозиторий для работы со статусами звонков
        """
        self.order_repository = order_repository
        self.call_status_repository = call_status_repository
    
    def get_today_orders(self, user_id: int, session: Session = None) -> List[OrderDTO]:
        """
        Получить все заказы пользователя за сегодня
        
        Args:
            user_id: ID пользователя
            session: Сессия БД (опционально)
            
        Returns:
            Список заказов в формате DTO
        """
        today = date.today()
        return self.get_orders_by_date(user_id, today, session)
    
    def get_orders_by_date(
        self, 
        user_id: int, 
        order_date: date, 
        session: Session = None
    ) -> List[OrderDTO]:
        """
        Получить все заказы пользователя за дату
        
        Args:
            user_id: ID пользователя
            order_date: Дата заказов
            session: Сессия БД (опционально)
            
        Returns:
            Список заказов в формате DTO
        """
        orders_db = self.order_repository.get_by_user_and_date(
            user_id, order_date, session
        )
        
        # Загружаем call_status для получения manual_arrival_time
        call_statuses = {}
        if session:
            call_statuses_list = self.call_status_repository.get_by_user_and_date(
                user_id, order_date, session
            )
            call_statuses = {}
            for cs in call_statuses_list:
                # Безопасно получаем order_number через __dict__
                order_num = cs.__dict__.get('order_number') if hasattr(cs, '__dict__') else getattr(cs, 'order_number', None)
                if order_num:
                    call_statuses[order_num] = cs
        else:
            # Если сессия не передана, создаем новую для call_status
            from src.database.connection import get_db_session
            with get_db_session() as session:
                call_statuses_list = self.call_status_repository.get_by_user_and_date(
                    user_id, order_date, session
                )
                call_statuses = {
                    cs.order_number: cs 
                    for cs in call_statuses_list 
                    if cs.order_number
                }
        
        result = []
        for order_db in orders_db:
            dto = self._order_db_to_dto(order_db)
            
            # Добавляем manual_arrival_time из call_status
            if order_db.order_number:
                cs = call_statuses.get(order_db.order_number)
                if cs and cs.is_manual_arrival and cs.manual_arrival_time:
                    dto.manual_arrival_time = cs.manual_arrival_time
            
            result.append(dto)
        
        return result
    
    def get_order_by_number(
        self, 
        user_id: int, 
        order_number: str, 
        order_date: date = None,
        session: Session = None
    ) -> Optional[OrderDTO]:
        """
        Получить заказ по номеру
        
        Args:
            user_id: ID пользователя
            order_number: Номер заказа
            order_date: Дата заказа (по умолчанию сегодня)
            session: Сессия БД (опционально)
            
        Returns:
            Заказ в формате DTO или None
        """
        if order_date is None:
            order_date = date.today()
        
        order_db = self.order_repository.get_by_number(
            user_id, order_number, order_date, session
        )
        
        if not order_db:
            return None
        
        dto = self._order_db_to_dto(order_db)
        
        # Добавляем manual_arrival_time из call_status
        if session:
            cs = self.call_status_repository.get_by_order(
                user_id, order_number, order_date, session
            )
        else:
            from src.database.connection import get_db_session
            with get_db_session() as session:
                cs = self.call_status_repository.get_by_order(
                    user_id, order_number, order_date, session
                )
        
        if cs:
            # Безопасно получаем атрибуты через __dict__
            is_manual_arrival = cs.__dict__.get('is_manual_arrival') if hasattr(cs, '__dict__') else getattr(cs, 'is_manual_arrival', False)
            manual_arrival_time = cs.__dict__.get('manual_arrival_time') if hasattr(cs, '__dict__') else getattr(cs, 'manual_arrival_time', None)
            if is_manual_arrival and manual_arrival_time:
                dto.manual_arrival_time = manual_arrival_time
        
        return dto
    
    def create_order(
        self, 
        user_id: int, 
        order_data: CreateOrderDTO, 
        order_date: date = None,
        session: Session = None
    ) -> OrderDTO:
        """
        Создать новый заказ
        
        Args:
            user_id: ID пользователя
            order_data: Данные заказа
            order_date: Дата заказа (по умолчанию сегодня)
            session: Сессия БД (опционально)
            
        Returns:
            Созданный заказ в формате DTO
        """
        if order_date is None:
            order_date = date.today()
        
        # Преобразуем DTO в модель Order
        order = Order(
            order_number=order_data.order_number,
            customer_name=order_data.customer_name,
            phone=order_data.phone,
            address=order_data.address,
            latitude=order_data.latitude,
            longitude=order_data.longitude,
            comment=order_data.comment,
            delivery_time_start=order_data.delivery_time_start,
            delivery_time_end=order_data.delivery_time_end,
            delivery_time_window=order_data.delivery_time_window,
            entrance_number=order_data.entrance_number,
            apartment_number=order_data.apartment_number,
            gis_id=order_data.gis_id,
            status="pending"
        )
        
        order_db = self.order_repository.save(
            user_id, order, order_date, session, partial_update=False
        )
        
        return self._order_db_to_dto(order_db)
    
    def update_order(
        self, 
        user_id: int, 
        order_number: str, 
        updates: UpdateOrderDTO, 
        order_date: date = None,
        session: Session = None
    ) -> Optional[OrderDTO]:
        """
        Обновить заказ
        
        Args:
            user_id: ID пользователя
            order_number: Номер заказа
            updates: Обновления заказа
            order_date: Дата заказа (по умолчанию сегодня)
            session: Сессия БД (опционально)
            
        Returns:
            Обновленный заказ в формате DTO или None
        """
        if order_date is None:
            order_date = date.today()
        
        # Получаем существующий заказ
        order_db = self.order_repository.get_by_number(
            user_id, order_number, order_date, session
        )
        
        if not order_db:
            return None
        
        # Обновляем поля
        update_dict = updates.dict(exclude_unset=True)
        for key, value in update_dict.items():
            if hasattr(order_db, key):
                setattr(order_db, key, value)
        
        if session:
            session.commit()
            session.refresh(order_db)
        else:
            # Если сессия не передана, нужно использовать репозиторий для сохранения
            # Создаем Order из order_db для сохранения
            order = Order(
                order_number=order_db.order_number,
                customer_name=order_db.customer_name,
                phone=order_db.phone,
                address=order_db.address,
                latitude=order_db.latitude,
                longitude=order_db.longitude,
                comment=order_db.comment,
                delivery_time_start=order_db.delivery_time_start,
                delivery_time_end=order_db.delivery_time_end,
                delivery_time_window=order_db.delivery_time_window,
                entrance_number=order_db.entrance_number,
                apartment_number=order_db.apartment_number,
                gis_id=order_db.gis_id,
                status=order_db.status
            )
            order_db = self.order_repository.save(
                user_id, order, order_date, session, partial_update=False
            )
        
        # Обновляем CallStatusDB с новыми данными
        if updates.phone or updates.customer_name:
            cs = self.call_status_repository.get_by_order(
                user_id, order_number, order_date, session
            )
            if cs:
                # Обновляем только если передана сессия (иначе нужно использовать репозиторий)
                if session:
                    if updates.phone:
                        cs.phone = updates.phone
                    if updates.customer_name:
                        cs.customer_name = updates.customer_name
                    # Если уведомление уже было отправлено, сбрасываем статус для повторной отправки
                    # Безопасно получаем статус через __dict__
                    current_status = cs.__dict__.get('status') if hasattr(cs, '__dict__') else getattr(cs, 'status', None)
                    if current_status == "confirmed":
                        cs.status = "pending"
                if session:
                    session.commit()
                else:
                    # Если сессия не передана, получаем объект заново и обновляем через сессию
                    from src.database.connection import get_db_session
                    with get_db_session() as sess:
                        # Получаем объект заново через внутренний метод репозитория
                        from src.repositories.call_status_repository import CallStatusRepository
                        actual_cs = self.call_status_repository._get_by_order(user_id, order_number, order_date, sess)
                        if actual_cs:
                            if updates.phone:
                                actual_cs.phone = updates.phone
                            if updates.customer_name:
                                actual_cs.customer_name = updates.customer_name
                            if actual_cs.status == "confirmed":
                                actual_cs.status = "pending"
                            sess.commit()
        
        return self._order_db_to_dto(order_db)
    
    def mark_delivered(
        self, 
        user_id: int, 
        order_number: str, 
        order_date: date = None,
        session: Session = None
    ) -> bool:
        """
        Отметить заказ как доставленный
        
        Args:
            user_id: ID пользователя
            order_number: Номер заказа
            order_date: Дата заказа (по умолчанию сегодня)
            session: Сессия БД (опционально)
            
        Returns:
            True если успешно
        """
        if order_date is None:
            order_date = date.today()
        
        return self.order_repository.update_status(
            user_id, order_number, "delivered", order_date, session
        )
    
    def get_delivered_orders(
        self, 
        user_id: int, 
        order_date: date = None,
        session: Session = None
    ) -> List[OrderDTO]:
        """
        Получить доставленные заказы
        
        Args:
            user_id: ID пользователя
            order_date: Дата заказов (по умолчанию сегодня)
            session: Сессия БД (опционально)
            
        Returns:
            Список доставленных заказов
        """
        if order_date is None:
            order_date = date.today()
        
        orders = self.get_orders_by_date(user_id, order_date, session)
        return [order for order in orders if order.status == "delivered"]
    
    def parse_order_from_image(
        self, 
        user_id: int, 
        image_data: bytes,
        session: Session = None
    ) -> Optional[CreateOrderDTO]:
        """
        Распарсить заказ из изображения
        
        Args:
            user_id: ID пользователя
            image_data: Байты изображения
            session: Сессия БД (опционально, не используется, но для совместимости)
            
        Returns:
            DTO для создания заказа или None
        """
        try:
            from src.services.image_parser import ImageOrderParser
            parser = ImageOrderParser()
            parsed_data = parser.parse_order_from_image(image_data)
            
            if not parsed_data:
                return None
            
            # Преобразуем delivery_time_window в delivery_time_start и delivery_time_end
            delivery_time_start = None
            delivery_time_end = None
            if parsed_data.get('delivery_time_window'):
                time_window = parsed_data.get('delivery_time_window')
                if isinstance(time_window, str) and '-' in time_window:
                    try:
                        start_str, end_str = time_window.split('-', 1)
                        start_str = start_str.strip()
                        end_str = end_str.strip()
                        delivery_time_start = datetime.strptime(start_str, '%H:%M').time()
                        delivery_time_end = datetime.strptime(end_str, '%H:%M').time()
                    except Exception as e:
                        logger.warning(f"Не удалось распарсить временное окно '{time_window}': {e}")
            
            return CreateOrderDTO(
                order_number=parsed_data.get('order_number'),
                customer_name=parsed_data.get('customer_name'),
                phone=parsed_data.get('phone'),
                address=parsed_data.get('address', ''),
                comment=parsed_data.get('comment'),
                delivery_time_start=delivery_time_start,
                delivery_time_end=delivery_time_end,
                delivery_time_window=parsed_data.get('delivery_time_window'),
                entrance_number=parsed_data.get('entrance_number'),
                apartment_number=parsed_data.get('apartment_number')
            )
        except Exception as e:
            logger.error(f"Ошибка парсинга изображения: {e}", exc_info=True)
            return None
    
    def _order_db_to_dto(self, order_db) -> OrderDTO:
        """Преобразовать OrderDB в OrderDTO"""
        # Получаем атрибуты через __dict__ напрямую, чтобы избежать DetachedInstanceError
        # Это безопасно, так как после session.refresh() все атрибуты уже загружены в __dict__
        if hasattr(order_db, '__dict__'):
            db_dict = order_db.__dict__
            # Фильтруем служебные атрибуты SQLAlchemy (начинающиеся с _)
            attrs = {k: v for k, v in db_dict.items() if not k.startswith('_')}
        else:
            # Fallback: пытаемся получить атрибуты напрямую
            try:
                attrs = {
                    'id': order_db.id,
                    'order_number': order_db.order_number,
                    'customer_name': order_db.customer_name,
                    'phone': order_db.phone,
                    'address': order_db.address,
                    'latitude': order_db.latitude,
                    'longitude': order_db.longitude,
                    'comment': order_db.comment,
                    'delivery_time_start': order_db.delivery_time_start,
                    'delivery_time_end': order_db.delivery_time_end,
                    'delivery_time_window': order_db.delivery_time_window,
                    'status': order_db.status,
                    'entrance_number': order_db.entrance_number,
                    'apartment_number': order_db.apartment_number,
                    'gis_id': order_db.gis_id
                }
            except Exception as e:
                # Если и это не работает, возвращаем пустой DTO (не должно происходить)
                import logging
                logger = logging.getLogger(__name__)
                logger.error(f"Критическая ошибка преобразования OrderDB в OrderDTO: {e}", exc_info=True)
                attrs = {}
        
        return OrderDTO(
            id=attrs.get('id'),
            order_number=attrs.get('order_number'),
            customer_name=attrs.get('customer_name'),
            phone=attrs.get('phone'),
            address=attrs.get('address'),
            latitude=attrs.get('latitude'),
            longitude=attrs.get('longitude'),
            comment=attrs.get('comment'),
            delivery_time_start=attrs.get('delivery_time_start'),
            delivery_time_end=attrs.get('delivery_time_end'),
            delivery_time_window=attrs.get('delivery_time_window'),
            status=attrs.get('status', 'pending'),
            entrance_number=attrs.get('entrance_number'),
            apartment_number=attrs.get('apartment_number'),
            gis_id=attrs.get('gis_id')
        )

