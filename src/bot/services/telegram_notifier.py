"""
Telegram Notifier - реализация Notifier для отправки уведомлений через Telegram
"""
import logging
from typing import Optional
from telebot import TeleBot
from telebot import types

from src.application.interfaces.notifier import AbstractNotifier
from src.application.dto.call_dto import CallNotificationDTO

logger = logging.getLogger(__name__)


class TelegramNotifier(AbstractNotifier):
    """Реализация Notifier для отправки уведомлений через Telegram"""
    
    def __init__(self, bot: TeleBot):
        """
        Args:
            bot: Экземпляр Telegram бота
        """
        self.bot = bot
    
    def send_call_notification(
        self,
        notification: CallNotificationDTO,
        is_retry: bool = False
    ) -> bool:
        """
        Отправить уведомление о звонке через Telegram
        
        Args:
            notification: Данные уведомления
            is_retry: True если это повторная попытка
            
        Returns:
            True если успешно отправлено, False в случае ошибки
        """
        try:
            # Формируем текст уведомления
            if is_retry:
                text = (
                    f"📞 <b>Повторное уведомление!</b>\n\n"
                    f"👤 {notification.customer_name or 'Клиент'}\n"
                    f"📦 Заказ №{notification.order_number}\n"
                    f"📱 {notification.phone}\n"
                    f"🕐 Время: {notification.call_time.strftime('%H:%M')}\n"
                    f"🔄 Попытка: {notification.attempts + 1 if hasattr(notification, 'attempts') else 1}"
                )
            else:
                text = notification.message
            
            # Создаем inline клавиатуру с кнопками
            markup = types.InlineKeyboardMarkup()
            
            # Кнопки подтверждения/отклонения
            confirm_button = types.InlineKeyboardButton(
                "✅ Подтверждено",
                callback_data=f"call_confirm_{notification.call_status_id}"
            )
            reject_button = types.InlineKeyboardButton(
                "❌ Отклонено",
                callback_data=f"call_reject_{notification.call_status_id}"
            )
            markup.add(confirm_button, reject_button)
            
            # Отправляем уведомление
            self.bot.send_message(
                notification.user_id,
                text,
                parse_mode='HTML',
                reply_markup=markup
            )
            
            logger.info(
                f"✅ Отправлено уведомление о звонке для заказа {notification.order_number} "
                f"пользователю {notification.user_id}"
            )
            return True
            
        except Exception as e:
            logger.error(f"❌ Ошибка отправки уведомления через Telegram: {e}", exc_info=True)
            return False

