"""
Базовые обработчики: главное меню, команды, callback routing
"""
import logging
from telebot import types

logger = logging.getLogger(__name__)


class BaseHandlers:
    """Базовые обработчики бота"""
    
    def __init__(self, bot_instance):
        self.bot = bot_instance.bot
        self.parent = bot_instance  # Ссылка на CourierBot
    
    def register(self):
        """Регистрация обработчиков"""
        # Команды
        self.bot.register_message_handler(self.handle_start, commands=['start'])
        self.bot.register_message_handler(self.handle_help, commands=['help'])
        
        # Главное меню
        self.bot.register_message_handler(
            self.handle_orders_menu,
            func=lambda m: m.text == "📦 Заказы"
        )
        self.bot.register_message_handler(
            self.handle_route_menu,
            func=lambda m: m.text == "🗺️ Маршрут"
        )
        self.bot.register_message_handler(
            self.handle_settings_menu,
            func=lambda m: m.text == "⚙️ Настройки"
        )
        self.bot.register_message_handler(
            self.handle_back_to_main,
            func=lambda m: m.text == "⬅️ Главное меню"
        )
        
        # Callback queries (роутинг)
        self.bot.register_callback_query_handler(
            self.handle_callback_query,
            func=lambda call: True
        )
        
        logger.info("✅ Базовые обработчики зарегистрированы")
    
    def handle_start(self, message):
        """Обработчик команды /start"""
        welcome_text = (
            "👋 <b>Добро пожаловать в Courier Bot!</b>\n\n"
            "Этот бот поможет вам оптимизировать маршруты доставки с учетом:\n"
            "• 🗺️ Реальных пробок (2GIS API)\n"
            "• ⏰ Временных окон доставки\n"
            "• 📞 Автоматических напоминаний о звонках\n"
            "• 🚦 Мониторинга изменений в пробках\n\n"
            "Используйте кнопки меню для управления заказами и маршрутами."
        )
        self.bot.reply_to(
            message,
            welcome_text,
            parse_mode='HTML',
            reply_markup=self.parent._main_menu_markup(message.from_user.id)
        )
    
    def handle_help(self, message):
        """Обработчик команды /help"""
        help_text = (
            "📖 <b>Справка по использованию бота</b>\n\n"
            "<b>📦 Заказы:</b>\n"
            "• ➕ Добавить заказы - ввести заказы вручную\n"
            "• ✏️ Редактирование - изменить данные заказа\n"
            "• ✅ Доставленные - список выполненных заказов\n\n"
            "<b>🗺️ Маршрут:</b>\n"
            "• 📍 Точка старта - установить начальную точку\n"
            "• ▶️ Оптимизировать - построить маршрут\n"
            "• 📞 Звонки - график звонков клиентам\n"
            "• 🚦 Мониторинг - отслеживать изменения в пробках\n\n"
            "<b>⚙️ Настройки:</b>\n"
            "• Время звонка до приезда\n"
            "• Интервал повторных звонков\n"
            "• Время на точке и парковку\n"
            "• Учетные данные ШефМаркет\n\n"
            "<b>📲 Импорт заказов:</b>\n"
            "• /import_orders - автоматический импорт из ШефМаркет\n\n"
            "По всем вопросам обращайтесь к администратору."
        )
        self.bot.reply_to(
            message,
            help_text,
            parse_mode='HTML',
            reply_markup=self.parent._main_menu_markup(message.from_user.id)
        )
    
    def handle_orders_menu(self, message):
        """Открыть меню заказов"""
        # Очищаем состояние при переходе в меню
        user_id = message.from_user.id
        self.parent.clear_user_state(user_id)
        
        self.bot.reply_to(
            message,
            "📦 <b>Меню заказов</b>\n\nВыберите действие:",
            parse_mode='HTML',
            reply_markup=self.parent._orders_menu_markup(user_id)
        )
    
    def handle_route_menu(self, message):
        """Открыть меню маршрута"""
        # Очищаем состояние при переходе в меню
        self.parent.clear_user_state(message.from_user.id)
        
        self.bot.reply_to(
            message,
            "🗺️ <b>Меню маршрута</b>\n\nВыберите действие:",
            parse_mode='HTML',
            reply_markup=self.parent._route_menu_markup()
        )
    
    def handle_settings_menu(self, message):
        """Открыть меню настроек"""
        # Очищаем состояние при переходе в меню
        self.parent.clear_user_state(message.from_user.id)
        
        self.parent.settings.show_settings_menu(message)
    
    def handle_back_to_main(self, message):
        """Вернуться в главное меню"""
        # Очищаем состояние при переходе в главное меню
        self.parent.clear_user_state(message.from_user.id)
        
        self.bot.reply_to(
            message,
            "🏠 <b>Главное меню</b>\n\nВыберите раздел:",
            parse_mode='HTML',
            reply_markup=self.parent._main_menu_markup(message.from_user.id)
        )
    
    def handle_callback_query(self, call):
        """Роутинг callback запросов по модулям"""
        callback_data = call.data
        
        try:
            # Роутинг по префиксам callback_data
            if (callback_data.startswith("order_") or 
                callback_data.startswith("save_order_from_image_") or
                callback_data.startswith("overwrite_order_from_image_") or
                callback_data == "cancel_save_order"):
                self.parent.orders.handle_callback(call)
            elif callback_data.startswith("call_"):
                self.parent.calls.handle_callback(call)
            elif callback_data.startswith("settings_"):
                self.parent.settings.handle_callback(call)
            elif callback_data.startswith("chefmarket_"):
                self.parent.imports.handle_callback(call)
            elif callback_data.startswith("traffic_"):
                self.parent.traffic.handle_callback(call)
            elif (callback_data.startswith("reset_") or 
                  callback_data.startswith("confirm_start_") or 
                  callback_data.startswith("recalculate_without_manual") or
                  callback_data.startswith("route_delivered_") or
                  callback_data.startswith("route_edit_order_") or
                  callback_data.startswith("current_order_") or
                  callback_data == "reject_start_address" or
                  callback_data == "route_menu"):
                # Обработка callback'ов маршрутов (сброс дня, подтверждение точки старта, пересчет без ручных времен, навигация по заказам, отметка доставки)
                self.parent.routes.handle_callback(call)
            elif callback_data == "view_delivered_orders":
                self.parent.orders.handle_view_delivered(call)
            elif callback_data.startswith("mark_delivered_"):
                # Обработка отметки доставки из списка заказов
                self.parent.orders.handle_callback(call)
            else:
                logger.warning(f"Неизвестный callback: {callback_data}")
                self.bot.answer_callback_query(call.id, "❌ Неизвестное действие")
        
        except Exception as e:
            logger.error(f"Ошибка обработки callback {callback_data}: {e}", exc_info=True)
            self.bot.answer_callback_query(call.id, f"❌ Ошибка: {str(e)}", show_alert=True)

