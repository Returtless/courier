"""
Обработчики для работы с заказами
"""
import logging

logger = logging.getLogger(__name__)


class OrderHandlers:
    """Обработчики заказов"""
    
    def __init__(self, bot_instance):
        self.bot = bot_instance.bot
        self.parent = bot_instance
    
    def register(self):
        """Регистрация обработчиков"""
        # Кнопки меню заказов
        self.bot.register_message_handler(
            self.handle_add_orders,
            func=lambda m: m.text == "➕ Добавить заказы"
        )
        self.bot.register_message_handler(
            self.handle_order_details_start,
            func=lambda m: m.text == "✏️ Редактирование заказов"
        )
        self.bot.register_message_handler(
            self.handle_delivered_orders,
            func=lambda m: m.text == "✅ Доставленные"
        )
        
        logger.info("✅ Order handlers зарегистрированы")
    
    def handle_callback(self, call):
        """Обработка callback запросов для заказов"""
        callback_data = call.data
        
        if callback_data.startswith("order_details_"):
            # Показать детали заказа
            order_number = callback_data.replace("order_details_", "")
            self.show_order_details(call.from_user.id, order_number, call.message.chat.id)
            self.bot.answer_callback_query(call.id)
        elif callback_data == "view_delivered_orders":
            self.handle_view_delivered(call)
    
    def handle_view_delivered(self, call):
        """Просмотр доставленных заказов через callback"""
        self.show_delivered_orders(call.from_user.id, call.message.chat.id)
        self.bot.answer_callback_query(call.id)
    
    # === Методы будут перенесены из старого handlers.py ===
    # TODO: Перенести следующие методы (см. REFACTORING_STATUS.md):
    # - handle_add_orders()
    # - handle_order_details_start()
    # - handle_delivered_orders()
    # - show_order_details()
    # - show_delivered_orders()
    # - mark_order_delivered()
    # - process_order()
    # - process_order_*() (phone, name, comment, etc.)
    # - _update_order_field()
    
    def handle_add_orders(self, message):
        """Добавление заказов - временная заглушка"""
        self.bot.reply_to(
            message,
            "⚠️ Функция временно недоступна. Завершается перенос кода.\n"
            "См. REFACTORING_STATUS.md для деталей.",
            reply_markup=self.parent._orders_menu_markup()
        )
        logger.warning("handle_add_orders вызван, но еще не перенесен")
    
    def handle_order_details_start(self, message):
        """Редактирование заказов - временная заглушка"""
        self.bot.reply_to(
            message,
            "⚠️ Функция временно недоступна. Завершается перенос кода.\n"
            "См. REFACTORING_STATUS.md для деталей.",
            reply_markup=self.parent._orders_menu_markup()
        )
        logger.warning("handle_order_details_start вызван, но еще не перенесен")
    
    def handle_delivered_orders(self, message):
        """Доставленные заказы - временная заглушка"""
        self.bot.reply_to(
            message,
            "⚠️ Функция временно недоступна. Завершается перенос кода.\n"
            "См. REFACTORING_STATUS.md для деталей.",
            reply_markup=self.parent._orders_menu_markup()
        )
        logger.warning("handle_delivered_orders вызван, но еще не перенесен")
    
    def show_order_details(self, user_id: int, order_number: str, chat_id: int):
        """Показ деталей заказа - заглушка"""
        logger.warning(f"show_order_details вызван для заказа {order_number}, но еще не перенесен")
        self.bot.send_message(
            chat_id,
            "⚠️ Функция в процессе переноса. См. REFACTORING_STATUS.md",
            reply_markup=self.parent._orders_menu_markup()
        )
    
    def show_delivered_orders(self, user_id: int, chat_id: int):
        """Показ доставленных заказов - заглушка"""
        logger.warning("show_delivered_orders вызван, но еще не перенесен")
        self.bot.send_message(
            chat_id,
            "⚠️ Функция в процессе переноса. См. REFACTORING_STATUS.md",
            reply_markup=self.parent._orders_menu_markup()
        )
    
    # Методы обработки ввода (вызываются из основного message handler)
    
    def process_order_state(self, message, current_state, state_data):
        """
        Обработка сообщений в состояниях заказов.
        Делегирует вызовы на старый handlers.py до полного переноса кода.
        """
        try:
            # Импортируем старый обработчик
            from ..handlers import CourierBot as OldCourierBot
            
            # Создаем временный экземпляр старого бота
            old_bot = OldCourierBot(self.bot, None)
            old_bot.db_service = self.parent.db_service
            old_bot.maps_service = self.parent.maps_service
            old_bot.traffic_monitor = self.parent.traffic_monitor
            old_bot.settings_service = self.parent.settings_service
            old_bot.call_notifier = self.parent.call_notifier
            old_bot.user_states = self.parent.user_states
            
            # Делегируем на старый обработчик
            if current_state == 'waiting_for_orders':
                old_bot.process_order_number(message)
            elif current_state == 'waiting_for_order_phone':
                old_bot.process_order_phone(message)
            elif current_state == 'waiting_for_order_name':
                old_bot.process_order_name(message)
            elif current_state == 'waiting_for_order_comment':
                old_bot.process_order_comment(message)
            elif current_state == 'waiting_for_order_entrance':
                old_bot.process_order_entrance(message)
            elif current_state == 'waiting_for_order_apartment':
                old_bot.process_order_apartment(message)
            elif current_state == 'waiting_for_order_delivery_time':
                old_bot.process_order_delivery_time(message)
            elif current_state == 'waiting_for_manual_arrival_time':
                old_bot.process_manual_arrival_time(message)
            elif current_state == 'waiting_for_manual_call_time':
                old_bot.process_manual_call_time(message)
            elif current_state == 'searching_order_by_number':
                old_bot.process_search_order_by_number(message)
            else:
                logger.warning(f"Неизвестное состояние заказа: {current_state}")
                self.bot.reply_to(
                    message,
                    "⚠️ Неизвестное состояние. Возврат в главное меню.",
                    reply_markup=self.parent._main_menu_markup()
                )
                self.parent.clear_user_state(message.from_user.id)
        
        except Exception as e:
            logger.error(f"Ошибка делегирования на старый обработчик заказов: {e}", exc_info=True)
            self.bot.reply_to(
                message,
                f"❌ Ошибка обработки: {str(e)}",
                reply_markup=self.parent._main_menu_markup()
            )
            self.parent.clear_user_state(message.from_user.id)
    
    def process_order_number_quick(self, message):
        """
        Быстрый поиск заказа по номеру (когда пользователь просто вводит номер).
        """
        try:
            from ..handlers import CourierBot as OldCourierBot
            
            old_bot = OldCourierBot(self.bot, None)
            old_bot.db_service = self.parent.db_service
            old_bot.maps_service = self.parent.maps_service
            old_bot.user_states = self.parent.user_states
            
            # Проверяем, есть ли такой заказ
            order_number = message.text.strip()
            user_id = message.from_user.id
            
            order = self.parent.db_service.get_order_by_number(user_id, order_number)
            if order:
                # Устанавливаем состояние поиска
                self.parent.update_user_state(user_id, 'searching_order_by_number', {})
                # Делегируем на старый обработчик
                old_bot.process_search_order_by_number(message)
            else:
                self.bot.reply_to(
                    message,
                    "❓ Используйте кнопки меню для навигации",
                    reply_markup=self.parent._main_menu_markup()
                )
        
        except Exception as e:
            logger.error(f"Ошибка быстрого поиска заказа: {e}", exc_info=True)
    
    def process_order(self, message, state_data):
        """Обработка ввода заказа - заглушка"""
        logger.warning("process_order вызван, но еще не перенесен")
        self.bot.reply_to(
            message,
            "⚠️ Функция в процессе переноса. См. REFACTORING_STATUS.md",
            reply_markup=self.parent._orders_menu_markup()
        )
    
    def process_order_phone(self, message, state_data):
        """Обработка ввода телефона - заглушка"""
        logger.warning("process_order_phone вызван, но еще не перенесен")
        self.bot.reply_to(
            message,
            "⚠️ Функция в процессе переноса. См. REFACTORING_STATUS.md",
            reply_markup=self.parent._orders_menu_markup()
        )
    
    def process_order_name(self, message, state_data):
        """Обработка ввода имени - заглушка"""
        logger.warning("process_order_name вызван, но еще не перенесен")
        self.bot.reply_to(
            message,
            "⚠️ Функция в процессе переноса. См. REFACTORING_STATUS.md",
            reply_markup=self.parent._orders_menu_markup()
        )
    
    def process_order_comment(self, message, state_data):
        """Обработка ввода комментария - заглушка"""
        logger.warning("process_order_comment вызван, но еще не перенесен")
        self.bot.reply_to(
            message,
            "⚠️ Функция в процессе переноса. См. REFACTORING_STATUS.md",
            reply_markup=self.parent._orders_menu_markup()
        )
    
    def process_order_entrance(self, message, state_data):
        """Обработка ввода подъезда - заглушка"""
        logger.warning("process_order_entrance вызван, но еще не перенесен")
        self.bot.reply_to(
            message,
            "⚠️ Функция в процессе переноса. См. REFACTORING_STATUS.md",
            reply_markup=self.parent._orders_menu_markup()
        )
    
    def process_order_apartment(self, message, state_data):
        """Обработка ввода квартиры - заглушка"""
        logger.warning("process_order_apartment вызван, но еще не перенесен")
        self.bot.reply_to(
            message,
            "⚠️ Функция в процессе переноса. См. REFACTORING_STATUS.md",
            reply_markup=self.parent._orders_menu_markup()
        )
    
    def process_order_delivery_time(self, message, state_data):
        """Обработка ввода времени доставки - заглушка"""
        logger.warning("process_order_delivery_time вызван, но еще не перенесен")
        self.bot.reply_to(
            message,
            "⚠️ Функция в процессе переноса. См. REFACTORING_STATUS.md",
            reply_markup=self.parent._orders_menu_markup()
        )
    
    def process_manual_arrival_time(self, message, state_data):
        """Обработка ручного ввода времени прибытия - заглушка"""
        logger.warning("process_manual_arrival_time вызван, но еще не перенесен")
        self.bot.reply_to(
            message,
            "⚠️ Функция в процессе переноса. См. REFACTORING_STATUS.md",
            reply_markup=self.parent._orders_menu_markup()
        )
    
    def process_manual_call_time(self, message, state_data):
        """Обработка ручного ввода времени звонка - заглушка"""
        logger.warning("process_manual_call_time вызван, но еще не перенесен")
        self.bot.reply_to(
            message,
            "⚠️ Функция в процессе переноса. См. REFACTORING_STATUS.md",
            reply_markup=self.parent._orders_menu_markup()
        )
    
    def process_search_order_by_number(self, message, state_data):
        """Обработка поиска заказа по номеру - заглушка"""
        logger.warning("process_search_order_by_number вызван, но еще не перенесен")
        self.bot.reply_to(
            message,
            "⚠️ Функция в процессе переноса. См. REFACTORING_STATUS.md",
            reply_markup=self.parent._orders_menu_markup()
        )
