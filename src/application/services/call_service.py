"""
Сервис для работы со звонками
Содержит бизнес-логику управления звонками и уведомлениями
"""
import logging
from datetime import date, datetime, timedelta
from typing import List, Optional
from sqlalchemy.orm import Session

from src.application.dto.call_dto import (
    CallStatusDTO, CallNotificationDTO, CreateCallStatusDTO
)
from src.repositories.call_status_repository import CallStatusRepository
from src.repositories.order_repository import OrderRepository
from src.services.user_settings_service import UserSettingsService
from src.models.order import CallStatusDB, OrderDB

logger = logging.getLogger(__name__)


def get_local_now():
    """Получить текущее время в часовом поясе Europe/Moscow"""
    try:
        from zoneinfo import ZoneInfo
        return datetime.now(ZoneInfo("Europe/Moscow"))
    except ImportError:
        try:
            from backports.zoneinfo import ZoneInfo
            return datetime.now(ZoneInfo("Europe/Moscow"))
        except ImportError:
            import pytz
            moscow_tz = pytz.timezone("Europe/Moscow")
            return datetime.now(moscow_tz)


class CallService:
    """Сервис для работы со звонками"""
    
    def __init__(
        self,
        call_status_repository: CallStatusRepository,
        order_repository: OrderRepository
    ):
        """
        Args:
            call_status_repository: Репозиторий для работы со статусами звонков
            order_repository: Репозиторий для работы с заказами
        """
        self.call_status_repository = call_status_repository
        self.order_repository = order_repository
        self.settings_service = UserSettingsService()
    
    def check_pending_calls(
        self,
        user_id: Optional[int] = None,
        call_date: date = None,
        session: Session = None
    ) -> List[CallNotificationDTO]:
        """
        Проверить pending звонки, которые нужно сделать сейчас
        
        Args:
            user_id: ID пользователя
            call_date: Дата звонков (по умолчанию сегодня)
            session: Сессия БД (опционально)
            
        Returns:
            Список уведомлений о звонках
        """
        if call_date is None:
            call_date = date.today()
        
        now = get_local_now()
        # Если now timezone-aware, конвертируем в naive для сравнения с БД
        if now.tzinfo is not None:
            now = now.replace(tzinfo=None)
        
        # Получаем pending звонки
        if user_id is None:
            # Для всех пользователей
            pending_calls = self.call_status_repository.get_all_pending_calls(call_date, session)
        else:
            pending_calls = self.call_status_repository.get_pending_calls(
                user_id, call_date, session
            )
        
        # Фильтруем звонки, время которых наступило (в пределах последних 10 минут)
        time_threshold = now - timedelta(minutes=10)
        notifications = []
        
        for call in pending_calls:
            # Проверяем, что время звонка наступило
            if call.call_time <= now and call.call_time >= time_threshold:
                # Проверяем, что заказ не доставлен
                order = self.order_repository.get_by_number(
                    call.user_id, call.order_number, call_date, session
                )
                
                if order and order.status == "delivered":
                    # Помечаем звонок как неактивный
                    if session:
                        call.status = "failed"
                        call.attempts = 999
                        session.commit()
                    else:
                        # Обновляем через BaseRepository
                        from src.repositories.base_repository import BaseRepository
                        base_repo = BaseRepository(CallStatusDB)
                        call.status = "failed"
                        call.attempts = 999
                        base_repo.update(call, session)
                    continue
                
                # Создаем уведомление
                message = self._build_notification_message(call, order)
                notifications.append(CallNotificationDTO(
                    call_status_id=call.id,
                    user_id=call.user_id,
                    order_number=call.order_number,
                    call_time=call.call_time,
                    phone=call.phone,
                    customer_name=call.customer_name,
                    arrival_time=call.arrival_time,
                    message=message,
                    attempts=call.attempts
                ))
        
        return notifications
    
    def check_retry_calls(
        self,
        user_id: Optional[int] = None,
        call_date: date = None,
        session: Session = None
    ) -> List[CallNotificationDTO]:
        """
        Проверить звонки для повторной попытки
        
        Args:
            user_id: ID пользователя
            call_date: Дата звонков (по умолчанию сегодня)
            session: Сессия БД (опционально)
            
        Returns:
            Список уведомлений о звонках для повторной попытки
        """
        if call_date is None:
            call_date = date.today()
        
        now = get_local_now()
        if now.tzinfo is not None:
            now = now.replace(tzinfo=None)
        
        # Получаем rejected звонки через репозиторий
        if user_id is None:
            # Для всех пользователей - используем максимальное значение попыток по умолчанию
            max_attempts = 3  # Значение по умолчанию
            retry_calls = self.call_status_repository.get_all_retry_calls(
                call_date, now, max_attempts, session
            )
        else:
            # Получаем настройки пользователя
            user_settings = self.settings_service.get_settings(user_id)
            retry_calls = self.call_status_repository.get_retry_calls(
                user_id, call_date, now, user_settings.call_max_attempts, session
            )
        
        notifications = []
        for call in retry_calls:
            # Получаем настройки пользователя для проверки максимального количества попыток
            call_user_settings = self.settings_service.get_settings(call.user_id)
            if call.attempts >= call_user_settings.call_max_attempts:
                continue
            
            order = self.order_repository.get_by_number(
                call.user_id, call.order_number, call_date, session
            )
            
            if order and order.status == "delivered":
                continue
            
            message = self._build_notification_message(call, order, is_retry=True)
            notifications.append(CallNotificationDTO(
                call_status_id=call.id,
                user_id=call.user_id,
                order_number=call.order_number,
                call_time=call.call_time,
                phone=call.phone,
                customer_name=call.customer_name,
                arrival_time=call.arrival_time,
                message=message,
                attempts=call.attempts
            ))
        
        return notifications
    
    def mark_notification_sent(
        self,
        call_status_id: int,
        is_retry: bool = False,
        session: Session = None
    ) -> bool:
        """
        Пометить уведомление как отправленное
        
        Args:
            call_status_id: ID статуса звонка
            is_retry: True если это повторная попытка
            session: Сессия БД (опционально)
            
        Returns:
            True если успешно
        """
        return self.call_status_repository.mark_as_sent(call_status_id, is_retry, session)
    
    def confirm_call(
        self,
        user_id: int,
        call_status_id: int,
        comment: Optional[str] = None,
        session: Session = None
    ) -> bool:
        """
        Подтвердить звонок
        
        Args:
            user_id: ID пользователя
            call_status_id: ID статуса звонка
            comment: Комментарий (опционально)
            session: Сессия БД (опционально)
            
        Returns:
            True если успешно
        """
        from src.database.connection import get_db_session
        from src.models.order import CallStatusDB
        
        if session:
            call_status = session.query(CallStatusDB).filter_by(id=call_status_id).first()
            if call_status and call_status.user_id == user_id:
                call_status.status = "confirmed"
                call_status.confirmation_comment = comment
                session.commit()
                logger.info(f"✅ Звонок {call_status_id} подтвержден")
                return True
        else:
            with get_db_session() as session:
                call_status = session.query(CallStatusDB).filter_by(id=call_status_id).first()
                if call_status and call_status.user_id == user_id:
                    call_status.status = "confirmed"
                    call_status.confirmation_comment = comment
                    session.commit()
                    logger.info(f"✅ Звонок {call_status_id} подтвержден")
                    return True
        
        return False
    
    def reject_call(
        self,
        user_id: int,
        call_status_id: int,
        session: Session = None
    ) -> bool:
        """
        Отклонить звонок (повторная попытка)
        
        Args:
            user_id: ID пользователя
            call_status_id: ID статуса звонка
            session: Сессия БД (опционально)
            
        Returns:
            True если успешно
        """
        from src.database.connection import get_db_session
        from src.models.order import CallStatusDB
        
        if session:
            call_status = session.query(CallStatusDB).filter_by(id=call_status_id).first()
            if call_status and call_status.user_id == user_id:
                call_status.status = "rejected"
                call_status.attempts += 1
                
                # Устанавливаем время следующей попытки
                user_settings = self.settings_service.get_settings(user_id)
                call_status.next_attempt_time = datetime.now() + timedelta(
                    minutes=user_settings.call_retry_interval_minutes
                )
                
                # Если превышен лимит попыток
                if call_status.attempts >= user_settings.call_max_attempts:
                    call_status.status = "failed"
                
                session.commit()
                logger.info(f"❌ Звонок {call_status_id} отклонен (попытка {call_status.attempts})")
                return True
        else:
            with get_db_session() as session:
                call_status = session.query(CallStatusDB).filter_by(id=call_status_id).first()
                if call_status and call_status.user_id == user_id:
                    call_status.status = "rejected"
                    call_status.attempts += 1
                    
                    user_settings = self.settings_service.get_settings(user_id)
                    call_status.next_attempt_time = datetime.now() + timedelta(
                        minutes=user_settings.call_retry_interval_minutes
                    )
                    
                    if call_status.attempts >= user_settings.call_max_attempts:
                        call_status.status = "failed"
                    
                    session.commit()
                    logger.info(f"❌ Звонок {call_status_id} отклонен (попытка {call_status.attempts})")
                    return True
        
        return False
    
    def create_call_status(
        self,
        user_id: int,
        call_data: CreateCallStatusDTO,
        call_date: date = None,
        session: Session = None
    ) -> CallStatusDTO:
        """
        Создать статус звонка
        
        Args:
            user_id: ID пользователя
            call_data: Данные звонка
            call_date: Дата звонка (по умолчанию сегодня)
            session: Сессия БД (опционально)
            
        Returns:
            Созданный статус звонка в формате DTO
        """
        if call_date is None:
            call_date = date.today()
        
        call_status_db = self.call_status_repository.create_or_update(
            user_id=user_id,
            order_number=call_data.order_number,
            call_time=call_data.call_time,
            phone=call_data.phone,
            customer_name=call_data.customer_name,
            call_date=call_date,
            is_manual_call=call_data.is_manual_call,
            is_manual_arrival=call_data.is_manual_arrival,
            arrival_time=call_data.arrival_time,
            manual_arrival_time=call_data.manual_arrival_time,
            session=session
        )
        
        return self._call_status_db_to_dto(call_status_db)
    
    def get_call_status(
        self,
        user_id: int,
        order_number: str,
        call_date: date = None,
        session: Session = None
    ) -> Optional[CallStatusDTO]:
        """
        Получить статус звонка по номеру заказа
        
        Args:
            user_id: ID пользователя
            order_number: Номер заказа
            call_date: Дата звонка (по умолчанию сегодня)
            session: Сессия БД (опционально)
            
        Returns:
            Статус звонка в формате DTO или None
        """
        if call_date is None:
            call_date = date.today()
        
        call_status_db = self.call_status_repository.get_by_order(
            user_id, order_number, call_date, session
        )
        
        if not call_status_db:
            return None
        
        return self._call_status_db_to_dto(call_status_db)
    
    def _build_notification_message(
        self,
        call: CallStatusDB,
        order: Optional[OrderDB],
        is_retry: bool = False
    ) -> str:
        """Построить текст уведомления о звонке"""
        retry_text = " (повторная попытка)" if is_retry else ""
        arrival_text = ""
        if call.arrival_time:
            arrival_text = f"\n⏰ Прибытие: {call.arrival_time.strftime('%H:%M')}"
        
        message = (
            f"📞 <b>Время звонить{retry_text}</b>\n\n"
            f"📦 Заказ: {call.order_number}\n"
            f"👤 {call.customer_name or 'Клиент'}\n"
            f"📞 {call.phone}{arrival_text}"
        )
        
        if order and order.comment:
            message += f"\n💬 {order.comment}"
        
        return message
    
    def _call_status_db_to_dto(self, call_status_db: CallStatusDB) -> CallStatusDTO:
        """Преобразовать CallStatusDB в CallStatusDTO"""
        return CallStatusDTO(
            id=call_status_db.id,
            order_number=call_status_db.order_number,
            call_time=call_status_db.call_time,
            arrival_time=call_status_db.arrival_time,
            phone=call_status_db.phone,
            customer_name=call_status_db.customer_name,
            status=call_status_db.status,
            attempts=call_status_db.attempts,
            is_manual_call=call_status_db.is_manual_call,
            is_manual_arrival=call_status_db.is_manual_arrival,
            manual_arrival_time=call_status_db.manual_arrival_time,
            confirmation_comment=call_status_db.confirmation_comment
        )

