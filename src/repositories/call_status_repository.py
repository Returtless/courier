"""
Репозиторий для работы со статусами звонков
"""
import logging
from typing import List, Optional
from datetime import date, datetime
from sqlalchemy.orm import Session
from sqlalchemy import and_
from src.database.connection import get_db_session
from src.models.order import CallStatusDB
from .base_repository import BaseRepository

logger = logging.getLogger(__name__)


class CallStatusRepository(BaseRepository[CallStatusDB]):
    """Репозиторий для работы со статусами звонков"""
    
    def __init__(self):
        super().__init__(CallStatusDB)
    
    def get_by_order(
        self, 
        user_id: int, 
        order_number: str, 
        call_date: date, 
        session: Session = None
    ) -> Optional[CallStatusDB]:
        """
        Получить статус звонка по номеру заказа
        
        Args:
            user_id: ID пользователя
            order_number: Номер заказа
            call_date: Дата звонка
            session: Сессия БД (опционально)
            
        Returns:
            Статус звонка или None
        """
        if session is None:
            with get_db_session() as session:
                result = self._get_by_order(user_id, order_number, call_date, session)
                if result:
                    session.refresh(result)
                    loaded_attrs = {}
                    for key, value in result.__dict__.items():
                        if not key.startswith('_sa_'):
                            loaded_attrs[key] = value
                    session.expunge(result)
                    for key, value in loaded_attrs.items():
                        object.__setattr__(result, key, value)
                return result
        return self._get_by_order(user_id, order_number, call_date, session)
    
    def _get_by_order(
        self, 
        user_id: int, 
        order_number: str, 
        call_date: date, 
        session: Session
    ) -> Optional[CallStatusDB]:
        """Внутренний метод получения статуса по заказу"""
        return session.query(CallStatusDB).filter(
            and_(
                CallStatusDB.user_id == user_id,
                CallStatusDB.order_number == order_number,
                CallStatusDB.call_date == call_date
            )
        ).first()
    
    def get_pending_calls(
        self, 
        user_id: int, 
        call_date: date, 
        session: Session = None
    ) -> List[CallStatusDB]:
        """
        Получить все pending звонки за дату
        
        Args:
            user_id: ID пользователя
            call_date: Дата звонков
            session: Сессия БД (опционально)
            
        Returns:
            Список pending звонков
        """
        if session is None:
            with get_db_session() as session:
                results = self._get_pending_calls(user_id, call_date, session)
                expunged_results = []
                for result in results:
                    session.refresh(result)
                    loaded_attrs = {}
                    for key, value in result.__dict__.items():
                        if not key.startswith('_sa_'):
                            loaded_attrs[key] = value
                    session.expunge(result)
                    for key, value in loaded_attrs.items():
                        object.__setattr__(result, key, value)
                    expunged_results.append(result)
                return expunged_results
        return self._get_pending_calls(user_id, call_date, session)
    
    def _get_pending_calls(
        self, 
        user_id: int, 
        call_date: date, 
        session: Session
    ) -> List[CallStatusDB]:
        """Внутренний метод получения pending звонков"""
        filters = [
            CallStatusDB.call_date == call_date,
            CallStatusDB.status == "pending"
        ]
        if user_id is not None:
            filters.append(CallStatusDB.user_id == user_id)
        return session.query(CallStatusDB).filter(and_(*filters)).all()
    
    def get_all_pending_calls(
        self,
        call_date: date,
        session: Session = None
    ) -> List[CallStatusDB]:
        """
        Получить все pending звонки за дату (для всех пользователей)
        
        Args:
            call_date: Дата звонков
            session: Сессия БД (опционально)
            
        Returns:
            Список pending звонков
        """
        if session is None:
            with get_db_session() as session:
                results = self._get_pending_calls(None, call_date, session)
                expunged_results = []
                for result in results:
                    session.refresh(result)
                    loaded_attrs = {}
                    for key, value in result.__dict__.items():
                        if not key.startswith('_sa_'):
                            loaded_attrs[key] = value
                    session.expunge(result)
                    for key, value in loaded_attrs.items():
                        object.__setattr__(result, key, value)
                    expunged_results.append(result)
                return expunged_results
        return self._get_pending_calls(None, call_date, session)
    
    def get_confirmed_calls(
        self, 
        user_id: int, 
        call_date: date, 
        session: Session = None
    ) -> List[CallStatusDB]:
        """
        Получить все подтвержденные звонки за дату
        
        Args:
            user_id: ID пользователя
            call_date: Дата звонков
            session: Сессия БД (опционально)
            
        Returns:
            Список подтвержденных звонков
        """
        if session is None:
            with get_db_session() as session:
                results = self._get_confirmed_calls(user_id, call_date, session)
                expunged_results = []
                for result in results:
                    session.refresh(result)
                    loaded_attrs = {}
                    for key, value in result.__dict__.items():
                        if not key.startswith('_sa_'):
                            loaded_attrs[key] = value
                    session.expunge(result)
                    for key, value in loaded_attrs.items():
                        object.__setattr__(result, key, value)
                    expunged_results.append(result)
                return expunged_results
        return self._get_confirmed_calls(user_id, call_date, session)
    
    def _get_confirmed_calls(
        self, 
        user_id: int, 
        call_date: date, 
        session: Session
    ) -> List[CallStatusDB]:
        """Внутренний метод получения подтвержденных звонков"""
        return session.query(CallStatusDB).filter(
            and_(
                CallStatusDB.user_id == user_id,
                CallStatusDB.call_date == call_date,
                CallStatusDB.status == "confirmed"
            )
        ).all()
    
    def create_or_update(
        self,
        user_id: int,
        order_number: str,
        call_time: datetime,
        phone: str,
        customer_name: Optional[str],
        call_date: date,
        is_manual_call: bool = False,
        is_manual_arrival: bool = False,
        arrival_time: Optional[datetime] = None,
        manual_arrival_time: Optional[datetime] = None,
        session: Session = None
    ) -> CallStatusDB:
        """
        Создать или обновить статус звонка
        
        Args:
            user_id: ID пользователя
            order_number: Номер заказа
            call_time: Время звонка
            phone: Телефон
            customer_name: Имя клиента
            call_date: Дата звонка
            is_manual_call: Ручное время звонка
            is_manual_arrival: Ручное время прибытия
            arrival_time: Расчетное время прибытия
            manual_arrival_time: Ручное время прибытия
            session: Сессия БД (опционально)
            
        Returns:
            Созданный или обновленный статус звонка
        """
        if session is None:
            with get_db_session() as session:
                result = self._create_or_update(
                    user_id, order_number, call_time, phone, customer_name,
                    call_date, is_manual_call, is_manual_arrival,
                    arrival_time, manual_arrival_time, session
                )
                if result:
                    session.refresh(result)
                    loaded_attrs = {}
                    for key, value in result.__dict__.items():
                        if not key.startswith('_sa_'):
                            loaded_attrs[key] = value
                    session.expunge(result)
                    for key, value in loaded_attrs.items():
                        object.__setattr__(result, key, value)
                return result
        return self._create_or_update(
            user_id, order_number, call_time, phone, customer_name,
            call_date, is_manual_call, is_manual_arrival,
            arrival_time, manual_arrival_time, session
        )
    
    def _create_or_update(
        self,
        user_id: int,
        order_number: str,
        call_time: datetime,
        phone: str,
        customer_name: Optional[str],
        call_date: date,
        is_manual_call: bool,
        is_manual_arrival: bool,
        arrival_time: Optional[datetime],
        manual_arrival_time: Optional[datetime],
        session: Session
    ) -> CallStatusDB:
        """Внутренний метод создания/обновления статуса"""
        existing = self._get_by_order(user_id, order_number, call_date, session)
        
        if existing:
            # Обновляем существующий статус
            existing.call_time = call_time
            existing.phone = phone
            existing.customer_name = customer_name
            existing.is_manual_call = is_manual_call
            existing.is_manual_arrival = is_manual_arrival
            existing.arrival_time = arrival_time
            existing.manual_arrival_time = manual_arrival_time
            # Если статус был "sent", сбрасываем на pending для повторной отправки
            if existing.status == "sent":
                existing.status = "pending"
                existing.attempts = 0
            session.commit()
            session.refresh(existing)
            logger.debug(f"🔄 Обновлен call_status для заказа {order_number}")
            return existing
        else:
            # Создаем новый статус
            new_status = CallStatusDB(
                user_id=user_id,
                order_number=order_number,
                call_date=call_date,
                call_time=call_time,
                phone=phone,
                customer_name=customer_name,
                is_manual_call=is_manual_call,
                is_manual_arrival=is_manual_arrival,
                arrival_time=arrival_time,
                manual_arrival_time=manual_arrival_time,
                status="pending"
            )
            session.add(new_status)
            session.commit()
            session.refresh(new_status)
            logger.debug(f"✅ Создан call_status для заказа {order_number}")
            return new_status
    
    def update_phone(
        self, 
        user_id: int, 
        order_number: str, 
        phone: str, 
        call_date: date,
        session: Session = None
    ) -> bool:
        """
        Обновить телефон в статусе звонка
        
        Args:
            user_id: ID пользователя
            order_number: Номер заказа
            phone: Новый телефон
            call_date: Дата звонка
            session: Сессия БД (опционально)
            
        Returns:
            True если обновление успешно
        """
        if session is None:
            with get_db_session() as session:
                return self._update_phone(user_id, order_number, phone, call_date, session)
        return self._update_phone(user_id, order_number, phone, call_date, session)
    
    def _update_phone(
        self, 
        user_id: int, 
        order_number: str, 
        phone: str, 
        call_date: date,
        session: Session
    ) -> bool:
        """Внутренний метод обновления телефона"""
        call_status = self._get_by_order(user_id, order_number, call_date, session)
        if call_status:
            call_status.phone = phone
            # Если статус был "sent", сбрасываем на pending
            if call_status.status == "sent":
                call_status.status = "pending"
                call_status.attempts = 0
            session.commit()
            logger.debug(f"✅ Обновлен телефон в call_status для заказа {order_number}")
            return True
        return False
    
    def get_by_user_and_date(
        self, 
        user_id: int, 
        call_date: date, 
        session: Session = None
    ) -> List[CallStatusDB]:
        """
        Получить все статусы звонков пользователя за дату
        
        Args:
            user_id: ID пользователя
            call_date: Дата звонков
            session: Сессия БД (опционально)
            
        Returns:
            Список статусов звонков
        """
        if session is None:
            with get_db_session() as session:
                results = self._get_by_user_and_date(user_id, call_date, session)
                expunged_results = []
                for result in results:
                    session.refresh(result)
                    loaded_attrs = {}
                    for key, value in result.__dict__.items():
                        if not key.startswith('_sa_'):
                            loaded_attrs[key] = value
                    session.expunge(result)
                    for key, value in loaded_attrs.items():
                        object.__setattr__(result, key, value)
                    expunged_results.append(result)
                return expunged_results
        return self._get_by_user_and_date(user_id, call_date, session)
    
    def _get_by_user_and_date(
        self, 
        user_id: int, 
        call_date: date, 
        session: Session
    ) -> List[CallStatusDB]:
        """Внутренний метод получения статусов по пользователю и дате"""
        return session.query(CallStatusDB).filter(
            and_(
                CallStatusDB.user_id == user_id,
                CallStatusDB.call_date == call_date
            )
        ).all()
    
    def get_retry_calls(
        self,
        user_id: int,
        call_date: date,
        max_time: datetime,
        max_attempts: int,
        session: Session = None
    ) -> List[CallStatusDB]:
        """
        Получить звонки для повторной попытки
        
        Args:
            user_id: ID пользователя (None для всех пользователей)
            call_date: Дата звонков
            max_time: Максимальное время (сейчас)
            max_attempts: Максимальное количество попыток
            session: Сессия БД (опционально)
            
        Returns:
            Список звонков для повторной попытки
        """
        if session is None:
            with get_db_session() as session:
                results = self._get_retry_calls(user_id, call_date, max_time, max_attempts, session)
                expunged_results = []
                for result in results:
                    session.refresh(result)
                    loaded_attrs = {}
                    for key, value in result.__dict__.items():
                        if not key.startswith('_sa_'):
                            loaded_attrs[key] = value
                    session.expunge(result)
                    for key, value in loaded_attrs.items():
                        object.__setattr__(result, key, value)
                    expunged_results.append(result)
                return expunged_results
        return self._get_retry_calls(user_id, call_date, max_time, max_attempts, session)
    
    def _get_retry_calls(
        self,
        user_id: int,
        call_date: date,
        max_time: datetime,
        max_attempts: int,
        session: Session
    ) -> List[CallStatusDB]:
        """Внутренний метод получения звонков для повторной попытки"""
        filters = [
            CallStatusDB.call_date == call_date,
            CallStatusDB.status == "rejected",
            CallStatusDB.next_attempt_time <= max_time,
            CallStatusDB.attempts < max_attempts
        ]
        if user_id is not None:
            filters.append(CallStatusDB.user_id == user_id)
        return session.query(CallStatusDB).filter(and_(*filters)).all()
    
    def get_all_retry_calls(
        self,
        call_date: date,
        max_time: datetime,
        max_attempts: int,
        session: Session = None
    ) -> List[CallStatusDB]:
        """
        Получить все звонки для повторной попытки (для всех пользователей)
        
        Args:
            call_date: Дата звонков
            max_time: Максимальное время (сейчас)
            max_attempts: Максимальное количество попыток
            session: Сессия БД (опционально)
            
        Returns:
            Список звонков для повторной попытки
        """
        if session is None:
            with get_db_session() as session:
                results = self._get_retry_calls(None, call_date, max_time, max_attempts, session)
                expunged_results = []
                for result in results:
                    session.refresh(result)
                    loaded_attrs = {}
                    for key, value in result.__dict__.items():
                        if not key.startswith('_sa_'):
                            loaded_attrs[key] = value
                    session.expunge(result)
                    for key, value in loaded_attrs.items():
                        object.__setattr__(result, key, value)
                    expunged_results.append(result)
                return expunged_results
        return self._get_retry_calls(None, call_date, max_time, max_attempts, session)
    
    def mark_as_sent(
        self,
        call_status_id: int,
        is_retry: bool = False,
        session: Session = None
    ) -> bool:
        """
        Пометить звонок как отправленный
        
        Args:
            call_status_id: ID статуса звонка
            is_retry: True если это повторная попытка
            session: Сессия БД (опционально)
            
        Returns:
            True если успешно
        """
        if session is None:
            with get_db_session() as session:
                return self._mark_as_sent(call_status_id, is_retry, session)
        return self._mark_as_sent(call_status_id, is_retry, session)
    
    def _mark_as_sent(
        self,
        call_status_id: int,
        is_retry: bool,
        session: Session
    ) -> bool:
        """Внутренний метод пометки как отправленного"""
        call_status = session.query(CallStatusDB).filter_by(id=call_status_id).first()
        if call_status:
            # НЕ инкрементируем attempts здесь - только при отклонении/подтверждении
            # Попытка = действие пользователя (отклонение), а не отправка уведомления
            call_status.status = "sent"
            if is_retry:
                call_status.next_attempt_time = None
            session.commit()
            logger.debug(f"✅ Помечен как отправленный: call_status_id={call_status_id}, попытка={call_status.attempts}")
            return True
        return False
    
    def confirm_call_status(
        self,
        call_status_id: int,
        user_id: int,
        comment: Optional[str] = None,
        session: Session = None
    ) -> bool:
        """
        Подтвердить звонок
        
        Args:
            call_status_id: ID статуса звонка
            user_id: ID пользователя (для проверки принадлежности)
            comment: Комментарий (опционально)
            session: Сессия БД (опционально)
            
        Returns:
            True если успешно
        """
        if session is None:
            with get_db_session() as session:
                return self._confirm_call_status(call_status_id, user_id, comment, session)
        return self._confirm_call_status(call_status_id, user_id, comment, session)
    
    def _confirm_call_status(
        self,
        call_status_id: int,
        user_id: int,
        comment: Optional[str],
        session: Session
    ) -> bool:
        """Внутренний метод подтверждения звонка"""
        call_status = session.query(CallStatusDB).filter_by(id=call_status_id).first()
        if call_status and call_status.user_id == user_id:
            call_status.status = "confirmed"
            call_status.confirmation_comment = comment
            session.commit()
            logger.info(f"✅ Звонок {call_status_id} подтвержден")
            return True
        return False
    
    def reject_call_status(
        self,
        call_status_id: int,
        user_id: int,
        next_attempt_time: datetime,
        max_attempts: int,
        session: Session = None
    ) -> bool:
        """
        Отклонить звонок (повторная попытка)
        
        Args:
            call_status_id: ID статуса звонка
            user_id: ID пользователя (для проверки принадлежности)
            next_attempt_time: Время следующей попытки
            max_attempts: Максимальное количество попыток
            session: Сессия БД (опционально)
            
        Returns:
            True если успешно
        """
        if session is None:
            with get_db_session() as session:
                return self._reject_call_status(call_status_id, user_id, next_attempt_time, max_attempts, session)
        return self._reject_call_status(call_status_id, user_id, next_attempt_time, max_attempts, session)
    
    def _reject_call_status(
        self,
        call_status_id: int,
        user_id: int,
        next_attempt_time: datetime,
        max_attempts: int,
        session: Session
    ) -> bool:
        """Внутренний метод отклонения звонка"""
        call_status = session.query(CallStatusDB).filter_by(id=call_status_id).first()
        if call_status and call_status.user_id == user_id:
            call_status.status = "rejected"
            call_status.attempts += 1  # Инкремент при отклонении (это реальная попытка)
            call_status.next_attempt_time = next_attempt_time
            
            # Если достигнут лимит попыток (например, 3 попытки = attempts достиг 3)
            if call_status.attempts >= max_attempts:
                call_status.status = "failed"
            
            session.commit()
            logger.info(f"❌ Звонок {call_status_id} отклонен (попытка {call_status.attempts}/{max_attempts})")
            return True
        return False
    
    def get_call_statuses_by_date(
        self,
        user_id: int,
        call_date: date,
        session: Session = None
    ) -> List[CallStatusDB]:
        """
        Получить все статусы звонков пользователя за дату (алиас для get_by_user_and_date)
        
        Args:
            user_id: ID пользователя
            call_date: Дата звонков
            session: Сессия БД (опционально)
            
        Returns:
            Список статусов звонков
        """
        return self.get_by_user_and_date(user_id, call_date, session)

