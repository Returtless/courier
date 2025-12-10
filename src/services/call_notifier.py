import threading
import logging
import time as time_module
from datetime import datetime, timedelta, date
from typing import Optional
from src.services.db_service import DatabaseService
from src.database.connection import get_db_session
from src.models.order import CallStatusDB
from sqlalchemy import and_

logger = logging.getLogger(__name__)

try:
    from zoneinfo import ZoneInfo
    TZ_AVAILABLE = True
except ImportError:
    try:
        from backports.zoneinfo import ZoneInfo
        TZ_AVAILABLE = True
    except ImportError:
        TZ_AVAILABLE = False
        import pytz


def get_local_now():
    """Получить текущее время в часовом поясе Europe/Moscow"""
    if TZ_AVAILABLE:
        return datetime.now(ZoneInfo("Europe/Moscow"))
    else:
        moscow_tz = pytz.timezone("Europe/Moscow")
        return datetime.now(moscow_tz)


class CallNotifier:
    """Сервис для проверки времени звонков и отправки уведомлений"""
    
    def __init__(self, bot, courier_bot):
        self.bot = bot
        self.courier_bot = courier_bot
        self.db_service = DatabaseService()
        self.running = False
        self.thread = None
        self.check_interval = 30  # Проверка каждые 30 секунд
    
    def start(self):
        """Запустить фоновую проверку звонков"""
        if self.running:
            return
        
        self.running = True
        self.thread = threading.Thread(target=self._check_loop, daemon=True)
        self.thread.start()
        logger.info("📞 CallNotifier запущен")
    
    def stop(self):
        """Остановить проверку звонков"""
        self.running = False
        if self.thread:
            self.thread.join(timeout=5)
        logger.info("📞 CallNotifier остановлен")
    
    def _check_loop(self):
        """Основной цикл проверки звонков"""
        while self.running:
            try:
                self._check_pending_calls()
                self._check_retry_calls()
            except Exception as e:
                logger.error(f"Ошибка в CallNotifier: {e}", exc_info=True)
            
            time_module.sleep(self.check_interval)
    
    def _check_pending_calls(self):
        """Проверить звонки, которые нужно сделать сейчас"""
        now = get_local_now()
        # Если now timezone-aware, конвертируем в naive для сравнения с БД
        if now.tzinfo is not None:
            now = now.replace(tzinfo=None)
        today = date.today()
        
        with get_db_session() as session:
            # Ищем звонки со статусом pending, время которых наступило
            # Проверяем звонки, которые должны быть сделаны в течение последних 10 минут (на случай если бот был перезапущен)
            time_threshold = now - timedelta(minutes=10)
            
            # Получаем все pending звонки на сегодня для отладки
            all_pending = session.query(CallStatusDB).filter(
                and_(
                    CallStatusDB.status == "pending",
                    CallStatusDB.call_date == today
                )
            ).all()
            
            logger.debug(f"Проверка звонков: сейчас {now.strftime('%Y-%m-%d %H:%M:%S')}, найдено {len(all_pending)} pending звонков на сегодня")
            for call in all_pending:
                time_diff = (call.call_time - now).total_seconds() / 60
                logger.debug(f"Заказ {call.order_number}: время звонка {call.call_time.strftime('%Y-%m-%d %H:%M:%S')}, разница {time_diff:.1f} мин")
            
            # Ищем звонки со статусом pending или sent (sent - это отправленные, но еще не подтвержденные/отклоненные)
            pending_calls = session.query(CallStatusDB).filter(
                and_(
                    CallStatusDB.status.in_(["pending", "sent"]),  # Также проверяем "sent" на случай если уведомление уже отправлено
                    CallStatusDB.call_time <= now,
                    CallStatusDB.call_time >= time_threshold,  # Не старше 10 минут
                    CallStatusDB.call_date == today
                )
            ).all()
            
            logger.debug(f"Звонков для отправки: {len(pending_calls)} (время <= {now.strftime('%H:%M:%S')} и >= {time_threshold.strftime('%H:%M:%S')})")
            
            for call in pending_calls:
                logger.info(f"✅ Найден звонок для отправки: заказ {call.order_number}, время {call.call_time.strftime('%H:%M:%S')}, сейчас {now.strftime('%H:%M:%S')}")
                self._send_call_notification(call)
    
    def _check_retry_calls(self):
        """Проверить звонки для повторной попытки"""
        now = get_local_now()
        # Если now timezone-aware, конвертируем в naive для сравнения с БД
        if now.tzinfo is not None:
            now = now.replace(tzinfo=None)
        today = date.today()
        
        with get_db_session() as session:
            # Ищем звонки со статусом rejected, у которых наступило время повторной попытки
            retry_calls = session.query(CallStatusDB).filter(
                and_(
                    CallStatusDB.status == "rejected",
                    CallStatusDB.next_attempt_time <= now,
                    CallStatusDB.call_date == today,
                    CallStatusDB.attempts < 3
                )
            ).all()
            
            for call in retry_calls:
                # Обновляем статус на pending для повторной попытки
                call.status = "pending"
                call.next_attempt_time = None
                session.commit()
                self._send_call_notification(call)
    
    def _send_call_notification(self, call: CallStatusDB):
        """Отправить уведомление о необходимости звонка"""
        try:
            customer_info = call.customer_name or "Клиент"
            order_info = f"Заказ №{call.order_number}" if call.order_number else "Заказ"
            
            text = (
                f"📞 <b>Время звонка!</b>\n\n"
                f"👤 {customer_info}\n"
                f"📦 {order_info}\n"
                f"📱 {call.phone}\n"
                f"🕐 Время: {call.call_time.strftime('%H:%M')}"
            )
            
            # Создаем inline клавиатуру с кнопками
            from telebot import types
            markup = types.InlineKeyboardMarkup()
            
            # Кнопки подтверждения/отклонения
            confirm_button = types.InlineKeyboardButton(
                "✅ Подтверждено",
                callback_data=f"call_confirm_{call.id}"
            )
            reject_button = types.InlineKeyboardButton(
                "❌ Отклонено",
                callback_data=f"call_reject_{call.id}"
            )
            markup.add(confirm_button, reject_button)
            
            # Отправляем уведомление
            try:
                self.bot.send_message(
                    call.user_id,
                    text,
                    parse_mode='HTML',
                    reply_markup=markup
                )
                
                logger.info(f"✅ Отправлено уведомление о звонке для заказа {call.order_number} пользователю {call.user_id}")
                
                # Обновляем статус в БД, чтобы не отправлять повторно
                # Используем временный статус "sent" (можно использовать любое значение, которое не pending/rejected/confirmed/failed)
                with get_db_session() as session:
                    call_status = session.query(CallStatusDB).filter(CallStatusDB.id == call.id).first()
                    if call_status and call_status.status == "pending":
                        # Временно помечаем как отправленное (после подтверждения/отклонения статус изменится)
                        call_status.status = "sent"
                        session.commit()
            except Exception as send_error:
                logger.error(f"❌ Ошибка отправки уведомления: {send_error}", exc_info=True)
            
        except Exception as e:
            logger.error(f"Ошибка отправки уведомления о звонке: {e}", exc_info=True)
    
    def create_call_status(self, user_id: int, order_number: str, call_time: datetime, 
                          phone: str, customer_name: Optional[str] = None, call_date: date = None):
        """Создать запись о звонке"""
        if call_date is None:
            call_date = date.today()
        
        with get_db_session() as session:
            # Проверяем, нет ли уже записи для этого заказа
            existing = session.query(CallStatusDB).filter(
                and_(
                    CallStatusDB.user_id == user_id,
                    CallStatusDB.order_number == order_number,
                    CallStatusDB.call_date == call_date
                )
            ).first()
            
            if existing:
                # Обновляем существующую запись
                existing.call_time = call_time
                existing.phone = phone
                existing.customer_name = customer_name
                existing.status = "pending"
                existing.attempts = 0
                existing.next_attempt_time = None
                session.commit()
                now = get_local_now()
                if now.tzinfo is not None:
                    now = now.replace(tzinfo=None)
                time_diff = (call_time - now).total_seconds() / 60
                logger.debug(f"✅ Обновлена запись о звонке: заказ {order_number}, время звонка {call_time.strftime('%Y-%m-%d %H:%M:%S')}, до звонка {time_diff:.1f} мин (сейчас {now.strftime('%Y-%m-%d %H:%M:%S')})")
                return existing
            
            # Создаем новую запись
            call_status = CallStatusDB(
                user_id=user_id,
                order_number=order_number,
                call_date=call_date,
                call_time=call_time,
                phone=phone,
                customer_name=customer_name,
                status="pending",
                attempts=0
            )
            session.add(call_status)
            session.commit()
            session.refresh(call_status)
            now = get_local_now()
            if now.tzinfo is not None:
                now = now.replace(tzinfo=None)
            time_diff = (call_time - now).total_seconds() / 60
            logger.info(f"✅ Создана запись о звонке: заказ {order_number}, время звонка {call_time.strftime('%Y-%m-%d %H:%M:%S')}, телефон {phone}, до звонка {time_diff:.1f} мин (сейчас {now.strftime('%Y-%m-%d %H:%M:%S')})")
            return call_status

