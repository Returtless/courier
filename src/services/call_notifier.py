"""
Рефакторенный CallNotifier - использует CallService и TelegramNotifier
"""
import threading
import logging
import time as time_module
from datetime import date
from typing import Optional

from src.application.services.call_service import CallService
from src.bot.services.telegram_notifier import TelegramNotifier
from src.application.interfaces.notifier import Notifier

logger = logging.getLogger(__name__)


class CallNotifier:
    """Сервис для проверки времени звонков и отправки уведомлений"""
    
    def __init__(
        self,
        call_service: CallService,
        notifier: Notifier
    ):
        """
        Args:
            call_service: Сервис для работы со звонками
            notifier: Сервис для отправки уведомлений
        """
        self.call_service = call_service
        self.notifier = notifier
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
        today = date.today()
        
        # Получаем уведомления через CallService (для всех пользователей)
        notifications = self.call_service.check_pending_calls(
            user_id=None,
            call_date=today
        )
        
        # Отправляем уведомления через Notifier
        for notification in notifications:
            try:
                success = self.notifier.send_call_notification(notification, is_retry=False)
                if success:
                    # Помечаем как отправленное
                    self.call_service.mark_notification_sent(
                        notification.call_status_id,
                        is_retry=False
                    )
                    logger.info(
                        f"✅ Отправлено уведомление о звонке для заказа {notification.order_number} "
                        f"пользователю {notification.user_id}"
                    )
            except Exception as e:
                logger.error(f"❌ Ошибка отправки уведомления: {e}", exc_info=True)
    
    def _check_retry_calls(self):
        """Проверить звонки для повторной попытки"""
        today = date.today()
        
        # Получаем уведомления для повторной попытки через CallService (для всех пользователей)
        notifications = self.call_service.check_retry_calls(
            user_id=None,
            call_date=today
        )
        
        # Отправляем уведомления через Notifier
        for notification in notifications:
            try:
                success = self.notifier.send_call_notification(notification, is_retry=True)
                if success:
                    # Помечаем как отправленное
                    self.call_service.mark_notification_sent(
                        notification.call_status_id,
                        is_retry=True
                    )
                    logger.info(
                        f"🔄 Отправлено повторное уведомление о звонке для заказа {notification.order_number} "
                        f"пользователю {notification.user_id} (попытка #{notification.attempts + 1})"
                    )
            except Exception as e:
                logger.error(f"❌ Ошибка отправки повторного уведомления: {e}", exc_info=True)
    
    def create_call_status(
        self,
        user_id: int,
        order_number: str,
        call_time,
        phone: str,
        customer_name: Optional[str] = None,
        call_date: date = None,
        is_manual_call: bool = False,
        is_manual_arrival: bool = False,
        arrival_time=None,
        manual_arrival_time=None,
    ):
        """
        Создать запись о звонке (обертка для обратной совместимости)
        
        Этот метод оставлен для обратной совместимости со старым кодом.
        В будущем должен быть удален, и код должен использовать CallService напрямую.
        """
        from src.application.dto.call_dto import CreateCallStatusDTO
        from datetime import datetime
        
        if call_date is None:
            call_date = date.today()
        
        create_dto = CreateCallStatusDTO(
            order_number=order_number,
            call_time=call_time if isinstance(call_time, datetime) else call_time,
            phone=phone,
            customer_name=customer_name,
            arrival_time=arrival_time,
            is_manual_call=is_manual_call,
            is_manual_arrival=is_manual_arrival,
            manual_arrival_time=manual_arrival_time
        )
        
        call_status_dto = self.call_service.create_call_status(
            user_id, create_dto, call_date
        )
        
        # Возвращаем объект для обратной совместимости
        # В будущем этот метод должен возвращать DTO
        return call_status_dto

