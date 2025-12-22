"""
Модуль обработчиков Telegram бота для курьеров
"""
import telebot
import logging
from src.services.maps_service import MapsService
from src.services.route_optimizer import RouteOptimizer
from src.services.traffic_monitor import TrafficMonitor
from src.services.db_service import DatabaseService
from src.services.call_notifier import CallNotifier
from src.services.user_settings_service import UserSettingsService
from src.services.credentials_service import CredentialsService
from src.application.container import get_container

logger = logging.getLogger(__name__)


class CourierBot:
    """Главный класс бота курьера"""
    
    def __init__(self, bot: telebot.TeleBot, llm_service=None):
        self.bot = bot
        self.llm_service = llm_service
        
        # Инициализация сервисов
        self.maps_service = MapsService()
        self.traffic_monitor = TrafficMonitor(self.maps_service)
        self.db_service = DatabaseService()
        self.settings_service = UserSettingsService()
        self.credentials_service = CredentialsService()
        
        # Application Services (из DI контейнера)
        container = get_container()
        self.order_service = container.order_service()
        self.route_service = container.route_service()
        self.call_service = container.call_service()
        
        # Bot services (требуют bot, создаются после инициализации)
        from src.bot.services.telegram_notifier import TelegramNotifier
        telegram_notifier = TelegramNotifier(bot)
        self.call_notifier = CallNotifier(self.call_service, telegram_notifier)
        
        # Состояния пользователей
        self.user_states = {}  # user_id -> state data
        
        # Инициализация хендлеров (импортируем только при инициализации чтобы избежать циклических импортов)
        from .base_handlers import BaseHandlers
        from .order_handlers import OrderHandlers
        from .route_handlers import RouteHandlers
        from .call_handlers import CallHandlers
        from .settings_handlers import SettingsHandlers
        from .import_handlers import ImportHandlers
        from .traffic_handlers import TrafficHandlers
        
        # Создаем экземпляры хендлеров
        self.base = BaseHandlers(self)
        self.orders = OrderHandlers(self)
        self.routes = RouteHandlers(self)
        self.calls = CallHandlers(self)
        self.settings = SettingsHandlers(self)
        self.imports = ImportHandlers(self)
        self.traffic = TrafficHandlers(self)
        
        # Настройка callback для мониторинга пробок
        self.traffic_monitor.add_callback(self._send_traffic_notification)
    
    def _send_traffic_notification(self, user_id: int, message: str):
        """Callback для отправки уведомлений о пробках"""
        try:
            self.bot.send_message(user_id, message, parse_mode='HTML')
        except Exception as e:
            logger.error(f"Ошибка отправки уведомления о пробках user_id={user_id}: {e}")
    
    def register_handlers(self):
        """Регистрация всех обработчиков сообщений"""
        # Регистрируем хендлеры из всех модулей
        self.base.register()
        self.orders.register()
        self.routes.register()
        self.calls.register()
        self.settings.register()
        self.imports.register()
        self.traffic.register()
        
        # Регистрируем главный обработчик сообщений (для обработки состояний)
        self.bot.register_message_handler(
            self._handle_message_with_state,
            func=lambda m: True,  # Обрабатывает все сообщения, которые не обработаны выше
            content_types=['text', 'location']
        )
        
        logger.info("✅ Все обработчики зарегистрированы")
    
    def _handle_message_with_state(self, message):
        """
        Главный обработчик сообщений для обработки состояний пользователя.
        Делегирует вызовы на соответствующие модули.
        """
        user_id = message.from_user.id
        state_data = self.get_user_state(user_id)
        current_state = state_data.get('state')
        
        if not current_state:
            # Нет состояния - проверяем, не ввел ли пользователь номер заказа
            text = message.text.strip() if message.text else ""
            if text.isdigit() and len(text) >= 4:
                # Похоже на номер заказа - делегируем на orders
                self.orders.process_order_number_quick(message)
            else:
                # Неизвестная команда
                self.bot.reply_to(
                    message,
                    "❓ Используйте кнопки меню для навигации",
                    reply_markup=self._main_menu_markup(message.from_user.id)
                )
            return
        
        # Делегируем обработку состояний на соответствующие модули
        try:
            # Состояния для импорта
            if current_state in ['waiting_for_chefmarket_login', 'waiting_for_chefmarket_password']:
                if current_state == 'waiting_for_chefmarket_login':
                    self.imports.process_chefmarket_login(message, state_data)
                else:
                    self.imports.process_chefmarket_password(message, state_data)
            
            # Состояния для звонков
            elif current_state == 'waiting_for_call_comment':
                self.calls.process_call_comment(message, state_data)
            
            # Состояния для настроек
            elif current_state == 'waiting_for_setting_value':
                self.settings.handle_setting_value(message, state_data)
            
            # Состояния для заказов (будут перенесены позже)
            elif current_state in [
                'waiting_for_orders',
                'waiting_for_order_phone',
                'waiting_for_order_name',
                'waiting_for_order_comment',
                'waiting_for_order_entrance',
                'waiting_for_order_apartment',
                'waiting_for_order_delivery_time',
                'waiting_for_manual_arrival_time',
                'waiting_for_manual_call_time',
                'searching_order_by_number'
            ]:
                self.orders.process_order_state(message, current_state, state_data)
            
            # Состояния для маршрутов (будут перенесены позже)
            elif current_state in [
                'waiting_for_start_location',
                'waiting_for_start_address',
                'confirming_start_location',
                'waiting_for_start_time'
            ]:
                self.routes.process_route_state(message, current_state, state_data)
            
            else:
                logger.warning(f"Неизвестное состояние: {current_state}")
                self.bot.reply_to(
                    message,
                    "❓ Неизвестное состояние. Возврат в главное меню.",
                    reply_markup=self._main_menu_markup(user_id)
                )
                self.clear_user_state(user_id)
        
        except Exception as e:
            logger.error(f"Ошибка обработки состояния {current_state}: {e}", exc_info=True)
            self.bot.reply_to(
                message,
                f"❌ Произошла ошибка: {str(e)}",
                reply_markup=self._main_menu_markup(user_id)
            )
            self.clear_user_state(user_id)
    
    # === Методы управления состоянием пользователей ===
    
    def get_user_state(self, user_id: int):
        """Получить состояние пользователя"""
        return self.user_states.get(user_id, {})
    
    def update_user_state(self, user_id: int, key: str, value):
        """Обновить состояние пользователя"""
        if user_id not in self.user_states:
            self.user_states[user_id] = {}
        self.user_states[user_id][key] = value
    
    def clear_user_state(self, user_id: int):
        """Очистить состояние пользователя"""
        if user_id in self.user_states:
            del self.user_states[user_id]
    
    # === Общие вспомогательные методы ===
    
    def _main_menu_markup(self, user_id: int = None):
        """Разметка главного меню
        
        Args:
            user_id: ID пользователя для проверки наличия оптимизированного маршрута.
                     Если передан и маршрут оптимизирован, добавляется кнопка "📋 Текущий заказ"
        """
        from telebot import types
        from datetime import date
        
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
        
        # Добавляем кнопку "Текущий заказ" только если маршрут оптимизирован (вверху)
        if user_id is not None:
            today = date.today()
            route_data = self.db_service.get_route_data(user_id, today)
            if route_data and route_data.get('route_points_data'):
                markup.row("📋 Текущий заказ")
        
        markup.row("📦 Заказы", "🗺️ Маршрут")
        markup.row("⚙️ Настройки")
        return markup
    
    def _orders_menu_markup(self, user_id: int = None):
        """Разметка меню заказов
        
        Args:
            user_id: ID пользователя для проверки наличия учетных данных ШефМаркет.
                     Если передан и учетные данные есть, добавляется кнопка "📲 Импорт из ШефМаркет"
        """
        from telebot import types
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
        markup.row("➕ Добавить заказы")
        markup.row("📸 Загрузить из скриншота")
        
        # Добавляем кнопку импорта из ШефМаркет, если есть учетные данные
        if user_id is not None and self.credentials_service.has_credentials(user_id, "chefmarket"):
            markup.row("📲 Импорт из ШефМаркет")
        
        markup.row("✏️ Редактирование заказов")
        markup.row("✅ Доставленные")
        markup.row("⬅️ Главное меню")
        return markup
    
    @staticmethod
    def _route_menu_markup():
        """Разметка меню маршрута"""
        from telebot import types
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
        markup.row("📋 Показать маршрут")
        markup.row("📍 Точка старта", "▶️ Оптимизировать")
        markup.row("📞 Звонки")
        markup.row("🚦 Мониторинг", "🛑 Стоп мониторинг")
        markup.row("⬅️ Главное меню")
        return markup
    
    @staticmethod
    def _add_orders_menu_markup():
        """Разметка меню добавления заказов"""
        from telebot import types
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
        markup.row("✅ Готово")
        markup.row("⬅️ Главное меню")
        return markup


# Экспортируем главный класс
__all__ = ['CourierBot']

