"""
Репозиторий для работы с заказами
"""
import logging
from typing import List, Optional, Dict
from datetime import date
from sqlalchemy.orm import Session
from sqlalchemy import and_
from src.database.connection import get_db_session
from src.models.order import OrderDB, Order, CallStatusDB
from .base_repository import BaseRepository

logger = logging.getLogger(__name__)


class OrderRepository(BaseRepository[OrderDB]):
    """Репозиторий для работы с заказами"""
    
    def __init__(self):
        super().__init__(OrderDB)
    
    def get_by_user_and_date(
        self, 
        user_id: int, 
        order_date: date, 
        session: Session = None
    ) -> List[OrderDB]:
        """
        Получить все заказы пользователя за дату
        
        Args:
            user_id: ID пользователя
            order_date: Дата заказов
            session: Сессия БД (опционально)
            
        Returns:
            Список заказов (последняя версия для каждого order_number)
        """
        if session is None:
            with get_db_session() as session:
                return self._get_by_user_and_date(user_id, order_date, session)
        return self._get_by_user_and_date(user_id, order_date, session)
    
    def _get_by_user_and_date(
        self, 
        user_id: int, 
        order_date: date, 
        session: Session
    ) -> List[OrderDB]:
        """Внутренний метод получения заказов"""
        # Получаем все заказы за дату, отсортированные по id (desc)
        all_orders = session.query(OrderDB).filter(
            and_(
                OrderDB.user_id == user_id,
                OrderDB.order_date == order_date
            )
        ).order_by(OrderDB.id.desc()).all()
        
        logger.debug(f"📦 Найдено {len(all_orders)} заказов в БД для user_id={user_id}, date={order_date}")
        
        # Группируем по order_number, беря последнюю запись для каждого
        orders_dict = {}
        for order in all_orders:
            key = order.order_number if order.order_number else f"id_{order.id}"
            if key not in orders_dict:
                orders_dict[key] = order
        
        orders = list(orders_dict.values())
        logger.debug(f"📦 После дедупликации: {len(orders)} уникальных заказов")
        
        return orders
    
    def get_by_number(
        self, 
        user_id: int, 
        order_number: str, 
        order_date: date, 
        session: Session = None
    ) -> Optional[OrderDB]:
        """
        Получить заказ по номеру
        
        Args:
            user_id: ID пользователя
            order_number: Номер заказа
            order_date: Дата заказа
            session: Сессия БД (опционально)
            
        Returns:
            Заказ или None
        """
        if session is None:
            with get_db_session() as session:
                return self._get_by_number(user_id, order_number, order_date, session)
        return self._get_by_number(user_id, order_number, order_date, session)
    
    def _get_by_number(
        self, 
        user_id: int, 
        order_number: str, 
        order_date: date, 
        session: Session
    ) -> Optional[OrderDB]:
        """Внутренний метод получения заказа по номеру"""
        return session.query(OrderDB).filter(
            and_(
                OrderDB.user_id == user_id,
                OrderDB.order_number == order_number,
                OrderDB.order_date == order_date
            )
        ).order_by(OrderDB.id.desc()).first()
    
    def get_active_orders(
        self, 
        user_id: int, 
        order_date: date, 
        session: Session = None
    ) -> List[OrderDB]:
        """
        Получить активные (не доставленные) заказы
        
        Args:
            user_id: ID пользователя
            order_date: Дата заказов
            session: Сессия БД (опционально)
            
        Returns:
            Список активных заказов
        """
        orders = self.get_by_user_and_date(user_id, order_date, session)
        return [order for order in orders if order.status != 'delivered']
    
    def save(
        self, 
        user_id: int, 
        order: Order, 
        order_date: date, 
        session: Session = None,
        partial_update: bool = False
    ) -> OrderDB:
        """
        Сохранить заказ
        
        Args:
            user_id: ID пользователя
            order: Объект заказа (Pydantic модель)
            order_date: Дата заказа
            session: Сессия БД (опционально)
            partial_update: Если True, обновляются только незаполненные поля
            
        Returns:
            Сохраненный заказ (OrderDB)
        """
        if session is None:
            with get_db_session() as session:
                result = self._save(user_id, order, order_date, session, partial_update)
                # Загружаем все атрибуты перед отсоединением, чтобы избежать DetachedInstanceError
                session.refresh(result)
                # Принудительно загружаем все атрибуты, обращаясь к каждому
                # Это гарантирует, что они будут доступны после expunge
                from sqlalchemy import inspect
                mapper = inspect(result)
                for attr in mapper.attrs:
                    try:
                        _ = getattr(result, attr.key)
                    except Exception:
                        pass  # Игнорируем ошибки для deferred/lazy атрибутов
                session.expunge(result)
                return result
        return self._save(user_id, order, order_date, session, partial_update)
    
    def _save(
        self, 
        user_id: int, 
        order: Order, 
        order_date: date, 
        session: Session,
        partial_update: bool
    ) -> OrderDB:
        """Внутренний метод сохранения заказа"""
        # Проверяем, существует ли заказ
        existing_order = None
        if order.order_number:
            existing_order = self._get_by_number(user_id, order.order_number, order_date, session)
        
        if existing_order:
            # Обновляем существующий заказ
            if partial_update:
                # Обновляем только незаполненные поля
                if order.customer_name and not existing_order.customer_name:
                    existing_order.customer_name = order.customer_name
                if order.phone and not existing_order.phone:
                    existing_order.phone = order.phone
                if order.address and not existing_order.address:
                    existing_order.address = order.address
                if order.latitude is not None and existing_order.latitude is None:
                    existing_order.latitude = order.latitude
                if order.longitude is not None and existing_order.longitude is None:
                    existing_order.longitude = order.longitude
                if order.comment and not existing_order.comment:
                    existing_order.comment = order.comment
                if order.delivery_time_start and not existing_order.delivery_time_start:
                    existing_order.delivery_time_start = order.delivery_time_start
                if order.delivery_time_end and not existing_order.delivery_time_end:
                    existing_order.delivery_time_end = order.delivery_time_end
                if order.delivery_time_window and not existing_order.delivery_time_window:
                    existing_order.delivery_time_window = order.delivery_time_window
                if order.entrance_number and not existing_order.entrance_number:
                    existing_order.entrance_number = order.entrance_number
                if order.apartment_number and not existing_order.apartment_number:
                    existing_order.apartment_number = order.apartment_number
                if order.gis_id and not existing_order.gis_id:
                    existing_order.gis_id = order.gis_id
                logger.info(f"🔄 Частичное обновление заказа {order.order_number}")
            else:
                # Полное обновление
                existing_order.customer_name = order.customer_name
                existing_order.phone = order.phone
                existing_order.address = order.address or ""  # address не может быть None
                existing_order.latitude = order.latitude
                existing_order.longitude = order.longitude
                existing_order.comment = order.comment
                existing_order.delivery_time_start = order.delivery_time_start
                existing_order.delivery_time_end = order.delivery_time_end
                existing_order.delivery_time_window = order.delivery_time_window
                existing_order.entrance_number = order.entrance_number
                existing_order.apartment_number = order.apartment_number
                existing_order.gis_id = order.gis_id
                logger.info(f"🔄 Полное обновление заказа {order.order_number}")
            
            session.commit()
            session.refresh(existing_order)
            return existing_order
        else:
            # Создаем новый заказ
            order_db = OrderDB(
                user_id=user_id,
                order_date=order_date,
                customer_name=order.customer_name,
                phone=order.phone,
                address=order.address or "",  # address не может быть None
                latitude=order.latitude,
                longitude=order.longitude,
                comment=order.comment,
                delivery_time_start=order.delivery_time_start,
                delivery_time_end=order.delivery_time_end,
                delivery_time_window=order.delivery_time_window,
                status=order.status,
                order_number=order.order_number,
                entrance_number=order.entrance_number,
                apartment_number=order.apartment_number,
                gis_id=order.gis_id
            )
            session.add(order_db)
            session.commit()
            session.refresh(order_db)
            logger.info(f"✅ Создан новый заказ {order.order_number}")
            return order_db
    
    def update_status(
        self, 
        user_id: int, 
        order_number: str, 
        status: str, 
        order_date: date,
        session: Session = None
    ) -> bool:
        """
        Обновить статус заказа
        
        Args:
            user_id: ID пользователя
            order_number: Номер заказа
            status: Новый статус
            order_date: Дата заказа
            session: Сессия БД (опционально)
            
        Returns:
            True если обновление успешно
        """
        if session is None:
            with get_db_session() as session:
                return self._update_status(user_id, order_number, status, order_date, session)
        return self._update_status(user_id, order_number, status, order_date, session)
    
    def _update_status(
        self, 
        user_id: int, 
        order_number: str, 
        status: str, 
        order_date: date,
        session: Session
    ) -> bool:
        """Внутренний метод обновления статуса"""
        order = self._get_by_number(user_id, order_number, order_date, session)
        if order:
            order.status = status
            session.commit()
            logger.info(f"✅ Обновлен статус заказа {order_number}: {status}")
            return True
        return False

