"""
Централизованная обработка ошибок
"""
import logging
from functools import wraps
from typing import Callable, Any, Optional
from telebot import TeleBot
from telebot.apihelper import ApiTelegramException

logger = logging.getLogger(__name__)


def handle_errors(
    func: Optional[Callable] = None,
    bot: Optional[TeleBot] = None,
    user_id: Optional[int] = None,
    error_message: Optional[str] = None
) -> Callable:
    """
    Декоратор для централизованной обработки ошибок
    
    Использование:
        @handle_errors
        def some_function():
            # код, который может выбросить исключение
            pass
        
        # С отправкой сообщения пользователю
        @handle_errors(bot=bot, user_id=user_id)
        def handler_function(message):
            # код обработчика
            pass
    """
    def decorator(f: Callable) -> Callable:
        @wraps(f)
        def wrapper(*args, **kwargs) -> Any:
            try:
                return f(*args, **kwargs)
            except ValueError as e:
                # Бизнес-ошибки (валидация, неверные данные)
                logger.warning(f"Validation error in {f.__name__}: {e}")
                if bot and user_id:
                    msg = error_message or f"❌ Ошибка валидации: {str(e)}"
                    try:
                        bot.send_message(user_id, msg, parse_mode='HTML')
                    except Exception:
                        pass
                raise
            except ApiTelegramException as e:
                # Ошибки Telegram API
                logger.error(f"Telegram API error in {f.__name__}: {e}", exc_info=True)
                if bot and user_id:
                    msg = error_message or "❌ Ошибка отправки сообщения в Telegram"
                    try:
                        bot.send_message(user_id, msg, parse_mode='HTML')
                    except Exception:
                        pass
                raise
            except Exception as e:
                # Технические ошибки
                logger.error(f"Error in {f.__name__}: {e}", exc_info=True)
                if bot and user_id:
                    msg = error_message or "❌ Произошла ошибка. Попробуйте позже."
                    try:
                        bot.send_message(user_id, msg, parse_mode='HTML')
                    except Exception:
                        pass
                raise
        return wrapper
    
    if func is None:
        # Декоратор вызван с аргументами
        return decorator
    else:
        # Декоратор вызван без аргументов
        return decorator(func)

