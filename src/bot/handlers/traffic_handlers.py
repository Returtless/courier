"""
Обработчики для мониторинга пробок
"""
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


class TrafficHandlers:
    """Обработчики мониторинга пробок"""
    
    def __init__(self, bot_instance):
        self.bot = bot_instance.bot
        self.parent = bot_instance
    
    def register(self):
        """Регистрация обработчиков"""
        # Регистрация обработчиков кнопок меню
        self.bot.register_message_handler(
            self.handle_monitor,
            func=lambda m: m.text == "🚦 Мониторинг"
        )
        self.bot.register_message_handler(
            self.handle_stop_monitor,
            func=lambda m: m.text == "🛑 Стоп мониторинг"
        )
        
        logger.info("✅ Traffic handlers зарегистрированы")
    
    def handle_callback(self, call):
        """Обработка callback запросов для мониторинга"""
        # Пока нет callback для мониторинга
        pass
    
    def handle_monitor(self, message):
        """Запуск мониторинга пробок"""
        user_id = message.from_user.id
        state_data = self.parent.get_user_state(user_id)

        # Получаем сохраненный маршрут из state (сохранен после оптимизации)
        optimized_route = state_data.get('optimized_route')
        orders = state_data.get('optimized_orders', [])
        start_location = state_data.get('start_location')
        start_time_str = state_data.get('start_time')

        if not optimized_route or not orders or not start_location or not start_time_str:
            self.bot.reply_to(
                message,
                "❌ Сначала оптимизируйте маршрут",
                reply_markup=self.parent._main_menu_markup()
            )
            return

        # Преобразуем start_time в datetime
        if isinstance(start_time_str, str):
            start_datetime = datetime.fromisoformat(start_time_str)
        else:
            start_datetime = start_time_str

        # Запустить мониторинг для этого пользователя
        self.parent.traffic_monitor.start_monitoring(
            user_id,
            optimized_route,
            orders,
            start_location,
            start_datetime
        )
        
        self.bot.reply_to(
            message,
            "🚦 <b>Мониторинг пробок запущен!</b>\n\n"
            "Буду проверять пробки и уведомлять об изменениях.",
            parse_mode='HTML',
            reply_markup=self.parent._main_menu_markup()
        )
    
    def handle_stop_monitor(self, message):
        """Остановка мониторинга пробок"""
        user_id = message.from_user.id
        self.parent.traffic_monitor.stop_monitoring(user_id)
        self.bot.reply_to(
            message,
            "🛑 Мониторинг пробок остановлен",
            reply_markup=self.parent._main_menu_markup()
        )
    
    def handle_traffic_status(self, message):
        """Статус мониторинга пробок"""
        user_id = message.from_user.id
        status = self.parent.traffic_monitor.get_current_traffic_status(user_id)

        if status['is_monitoring']:
            last_check = status['last_check']
            if last_check:
                last_check_dt = datetime.fromisoformat(last_check)
                time_diff = datetime.now() - last_check_dt
                last_check_str = f"{time_diff.seconds // 60} мин назад"
            else:
                last_check_str = "еще не проверялось"

            text = (
                f"🚦 <b>Статус мониторинга:</b>\n\n"
                f"📍 Точек маршрута: {status['route_points']}\n"
                f"⏰ Интервал проверки: {status['check_interval_minutes']} мин\n"
                f"🔍 Последняя проверка: {last_check_str}\n"
                f"✅ Статус: Активен"
            )
        else:
            text = (
                "🚦 <b>Мониторинг не активен</b>\n\n"
                "Используйте кнопку 🚦 Мониторинг для запуска"
            )

        self.bot.reply_to(
            message,
            text,
            parse_mode='HTML',
            reply_markup=self.parent._main_menu_markup()
        )

