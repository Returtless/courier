"""
Централизованная обработка ошибок
"""
import logging
from functools import wraps
from typing import Callable, Any

logger = logging.getLogger(__name__)


def handle_errors(func: Callable) -> Callable:
    """
    Декоратор для централизованной обработки ошибок
    
    Использование:
        @handle_errors
        def some_function():
            # код, который может выбросить исключение
            pass
    """
    @wraps(func)
    def wrapper(*args, **kwargs) -> Any:
        try:
            return func(*args, **kwargs)
        except ValueError as e:
            # Бизнес-ошибки (валидация, неверные данные)
            logger.warning(f"Validation error in {func.__name__}: {e}")
            raise
        except Exception as e:
            # Технические ошибки
            logger.error(f"Error in {func.__name__}: {e}", exc_info=True)
            raise
    return wrapper

