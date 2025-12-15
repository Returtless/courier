"""
Мост к старому handlers.py для методов, которые еще не перенесены.
Это временное решение до полного переноса кода.
"""
import logging

logger = logging.getLogger(__name__)


class LegacyBridge:
    """
    Мост к старому handlers.py.
    
    Этот класс импортирует и вызывает методы из старого handlers.py
    для функций, которые еще не перенесены (маршруты и заказы).
    """
    
    def __init__(self, bot_instance):
        self.bot = bot_instance.bot
        self.parent = bot_instance
        
        # Импортируем старый CourierBot
        try:
            # Старый handlers.py должен быть доступен
            import sys
            import os
            
            # Добавляем путь к старому handlers
            old_handlers_path = os.path.join(
                os.path.dirname(__file__),
                '..',
                'handlers.py'
            )
            
            if os.path.exists(old_handlers_path):
                # Импортируем старый модуль
                import importlib.util
                spec = importlib.util.spec_from_file_location("old_handlers", old_handlers_path)
                old_module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(old_module)
                
                # Создаем экземпляр старого CourierBot
                self.old_bot = old_module.CourierBot(self.bot, None)
                
                # Копируем необходимые атрибуты
                self.old_bot.db_service = self.parent.db_service
                self.old_bot.maps_service = self.parent.maps_service
                self.old_bot.traffic_monitor = self.parent.traffic_monitor
                self.old_bot.settings_service = self.parent.settings_service
                self.old_bot.call_notifier = self.parent.call_notifier
                self.old_bot.user_states = self.parent.user_states
                
                logger.info("✅ Legacy bridge инициализирован")
                self.available = True
            else:
                logger.warning("⚠️ Старый handlers.py не найден")
                self.available = False
        except Exception as e:
            logger.error(f"❌ Ошибка инициализации legacy bridge: {e}")
            self.available = False
    
    def delegate_method(self, method_name, *args, **kwargs):
        """Делегировать вызов метода на старый handlers"""
        if not self.available:
            raise RuntimeError(f"Legacy bridge недоступен для метода {method_name}")
        
        method = getattr(self.old_bot, method_name, None)
        if method:
            return method(*args, **kwargs)
        else:
            raise AttributeError(f"Метод {method_name} не найден в старом handlers")

