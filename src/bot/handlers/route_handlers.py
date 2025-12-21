"""
Обработчики для работы с маршрутами и оптимизацией.

Содержит полный код для:
- Установки точки старта (геопозиция/адрес)
- Оптимизации маршрута
- Показа маршрута и графика звонков
- Сброса данных за день
"""
import logging
from typing import Dict, List
from datetime import datetime, time, timedelta, date
from telebot import types
from src.models.order import Order, CallStatusDB
from src.services.maps_service import MapsService
from src.services.route_optimizer import RouteOptimizer
from src.database.connection import get_db_session

logger = logging.getLogger(__name__)


class RouteHandlers:
    """Обработчики маршрутов - полная реализация"""
    
    def __init__(self, bot_instance):
        self.bot = bot_instance.bot
        self.parent = bot_instance
    
    def register(self):
        """Регистрация обработчиков маршрутов"""
        # Кнопки меню маршрутов
        self.bot.register_message_handler(
            self.handle_set_start,
            func=lambda m: m.text == "📍 Точка старта"
        )
        self.bot.register_message_handler(
            self.handle_optimize_route,
            func=lambda m: m.text == "▶️ Оптимизировать"
        )
        self.bot.register_message_handler(
            self.handle_show_route,
            func=lambda m: m.text == "📋 Показать маршрут"
        )
        self.bot.register_message_handler(
            self.handle_current_order,
            func=lambda m: m.text == "📋 Текущий заказ"
        )
        self.bot.register_message_handler(
            self.handle_show_calls,
            func=lambda m: m.text == "📞 Звонки"
        )
        self.bot.register_message_handler(
            self.handle_reset_day,
            func=lambda m: m.text == "🗑️ Сбросить день"
        )
        
        # Под-меню точки старта
        self.bot.register_message_handler(
            self.handle_set_start_location_geo,
            func=lambda m: m.text == "📍 Геопозиция"
        )
        self.bot.register_message_handler(
            self.handle_set_start_location_address,
            func=lambda m: m.text == "✍️ Адрес"
        )
        self.bot.register_message_handler(
            self.handle_set_start_time_change,
            func=lambda m: m.text == "⏰ Время старта"
        )
        
        logger.info("✅ Route handlers зарегистрированы")
    
    def handle_callback(self, call):
        """Обработка callback запросов для маршрутов"""
        callback_data = call.data
        
        if callback_data == "reset_day_confirm":
            self.handle_reset_day_confirm(call)
        elif callback_data == "reset_day_cancel":
            # Отмена сброса дня
            self.bot.answer_callback_query(call.id, "❌ Отменено")
            self.bot.edit_message_text(
                "❌ Сброс данных отменён",
                call.message.chat.id,
                call.message.message_id
            )
        elif callback_data == "confirm_start_address":
            self.handle_confirm_start_address(call)
        elif callback_data == "reject_start_address":
            self.handle_reject_start_address(call)
        elif callback_data == "recalculate_without_manual":
            self.handle_recalculate_without_manual_confirm(call)
        elif callback_data == "recalculate_without_manual_yes":
            self.handle_recalculate_without_manual(call)
        elif callback_data == "recalculate_without_manual_no":
            self.bot.answer_callback_query(call.id, "❌ Отменено")
            self.bot.edit_message_text(
                "❌ Пересчет отменен",
                call.message.chat.id,
                call.message.message_id
            )
        elif callback_data == "route_menu":
            # Показываем меню маршрута
            self.bot.answer_callback_query(call.id)
            self.bot.send_message(
                call.message.chat.id,
                "🗺️ <b>Меню маршрута</b>",
                parse_mode='HTML',
                reply_markup=self.parent._route_menu_markup()
            )
        elif callback_data.startswith("route_delivered_"):
            self.handle_mark_order_delivered(call)
        elif callback_data.startswith("route_edit_order_"):
            self.handle_edit_order_from_route(call)
        elif callback_data.startswith("current_order_"):
            # Формат: current_order_<index> или current_order_next_<index> или current_order_prev_<index>
            if callback_data.startswith("current_order_next_"):
                index = int(callback_data.replace("current_order_next_", ""))
                self.handle_show_order_by_index(call, index + 1)
            elif callback_data.startswith("current_order_prev_"):
                index = int(callback_data.replace("current_order_prev_", ""))
                self.handle_show_order_by_index(call, index - 1)
            else:
                index = int(callback_data.replace("current_order_", ""))
                self.handle_show_order_by_index(call, index)
    
    # ==================== ТОЧКА СТАРТА ====================
    
    def handle_set_start(self, message):
        """Handle /set_start command"""
        user_id = message.from_user.id
        today = date.today()
        
        # Загружаем из БД
        start_location_data = self.parent.db_service.get_start_location(user_id, today)
        
        start_address = None
        start_location = None
        start_time_str = None
        
        if start_location_data:
            if start_location_data.get('location_type') == 'geo':
                start_location = {
                    'lat': start_location_data.get('latitude'),
                    'lon': start_location_data.get('longitude')
                }
            elif start_location_data.get('location_type') == 'address':
                start_address = start_location_data.get('address')
            start_time_str = start_location_data.get('start_time')
        
        # Создаем клавиатуру с вариантами
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
        markup.row("📍 Геопозиция", "✍️ Адрес")
        if start_time_str:
            markup.row("⏰ Время старта")
        markup.row("⬅️ Главное меню")

        text = "📍 <b>Точка старта</b>\n\n"
        
        if start_location:
            lat, lon = start_location['lat'], start_location['lon']
            text += f"📍 <b>Текущая точка:</b> Геопозиция ({lat:.6f}, {lon:.6f})\n"
        elif start_address:
            text += f"📍 <b>Текущая точка:</b> {start_address}\n"
        else:
            text += "Точка старта не установлена\n"
        
        if start_time_str:
            start_time = datetime.fromisoformat(start_time_str)
            text += f"⏰ <b>Время старта:</b> {start_time.strftime('%H:%M')}\n"
        else:
            text += "⏰ Время старта не установлено\n"
        
        text += "\nВыберите действие:"
        
        self.bot.reply_to(message, text, parse_mode='HTML', reply_markup=markup)
    
    def handle_set_start_location_geo(self, message):
        """Запросить геопозицию для точки старта"""
        user_id = message.from_user.id
        
        # Создаем клавиатуру с кнопкой "Отправить геопозицию"
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
        geo_button = types.KeyboardButton("📍 Отправить геопозицию", request_location=True)
        markup.add(geo_button)
        markup.row("⬅️ Назад")
        
        self.bot.send_message(
            message.chat.id,
            "📍 Отправьте свою геопозицию с помощью кнопки ниже:",
            reply_markup=markup
        )
        
        # Устанавливаем состояние
        self.parent.update_user_state(user_id, 'state', 'waiting_for_start_location')
        self.parent.update_user_state(user_id, 'location_type', 'geo')
    
    def handle_set_start_location_address(self, message):
        """Запросить адрес для точки старта"""
        user_id = message.from_user.id
        
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
        markup.row("⬅️ Назад")
        
        self.bot.send_message(
            message.chat.id,
            "✍️ Введите адрес точки старта:",
            reply_markup=markup
        )
        
        # Устанавливаем состояние
        self.parent.update_user_state(user_id, 'state', 'waiting_for_start_address')
    
    def handle_set_start_time_change(self, message):
        """Изменить время старта"""
        user_id = message.from_user.id
        
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
        markup.row("⬅️ Назад")
        
        self.bot.send_message(
            message.chat.id,
            "⏰ Введите время старта (например, 09:00):",
            reply_markup=markup
        )
        
        # Устанавливаем состояние
        self.parent.update_user_state(user_id, 'state', 'waiting_for_start_time')
    
    # Методы обработки ввода (вызываются из основного message handler)
    
    def process_route_state(self, message, current_state, state_data):
        """Обработка сообщений в состояниях маршрутов"""
        try:
            if current_state == 'waiting_for_start_location':
                self.process_start_location_choice(message)
            elif current_state == 'waiting_for_start_address':
                self.process_start_location(message)
            elif current_state == 'confirming_start_location':
                self.process_start_location(message)
            elif current_state == 'waiting_for_start_time':
                self.process_start_time(message)
            else:
                logger.warning(f"Неизвестное состояние маршрута: {current_state}")
                self.bot.reply_to(
                    message,
                    "⚠️ Неизвестное состояние. Возврат в главное меню.",
                    reply_markup=self.parent._main_menu_markup(message.from_user.id)
                )
                self.parent.clear_user_state(message.from_user.id)
        
        except Exception as e:
            logger.error(f"Ошибка обработки состояния маршрута: {e}", exc_info=True)
            self.bot.reply_to(
                message,
                f"❌ Ошибка обработки: {str(e)}",
                reply_markup=self.parent._main_menu_markup(message.from_user.id)
            )
            self.parent.clear_user_state(message.from_user.id)
    
    def process_start_location_choice(self, message):
        """Обработка выбора способа ввода точки старта"""
        user_id = message.from_user.id
        today = date.today()
        
        if message.text == "⬅️ Назад":
            self.parent.clear_user_state(user_id)
            self.handle_set_start(message)
            return
        
        # Если это геопозиция
        if message.location:
            lat = message.location.latitude
            lon = message.location.longitude
            
            # Сохраняем в БД
            self.parent.db_service.save_start_location(
                user_id, 'geo', None, lat, lon, None, today
            )
            
            # Спрашиваем про время старта
            markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
            markup.row("⬅️ Главное меню")
            
            self.bot.send_message(
                message.chat.id,
                f"✅ Точка старта сохранена: ({lat:.6f}, {lon:.6f})\n\n"
                "⏰ Введите время старта (например, 09:00):",
                reply_markup=markup
            )
            
            self.parent.update_user_state(user_id, 'state', 'waiting_for_start_time')
        else:
            self.bot.reply_to(
                message,
                "❌ Пожалуйста, отправьте геопозицию с помощью кнопки."
            )
    
    def process_start_location(self, message):
        """Обработка адреса точки старта"""
        user_id = message.from_user.id
        today = date.today()
        
        if message.text == "⬅️ Назад":
            self.parent.clear_user_state(user_id)
            self.handle_set_start(message)
            return
        
        address = message.text.strip()
        
        # Геокодируем адрес для получения координат
        self.bot.send_chat_action(message.chat.id, 'typing')
        maps_service = MapsService()
        lat, lon, gid = maps_service.geocode_address_sync(address)
        
        if not lat or not lon:
            self.bot.reply_to(
                message,
                f"❌ Не удалось определить координаты адреса: {address}\n\n"
                "Попробуйте ввести адрес в другом формате или используйте геопозицию."
            )
            return
        
        # Сохраняем в состояние для подтверждения (НЕ в БД!)
        self.parent.update_user_state(user_id, 'pending_location', {
            'address': address,
            'lat': lat,
            'lon': lon,
            'gid': gid  # Сохраняем для ссылки на 2ГИС
        })
        self.parent.update_user_state(user_id, 'state', 'confirming_start_location')
        
        # Формируем ссылки на карты
        dgis_link = f"https://2gis.ru/geo/{gid}?m={lon}%2C{lat}%2F17.87" if gid else f"https://2gis.ru/search/{address}"
        yandex_link = f"https://yandex.ru/maps/?whatshere[point]={lon},{lat}&whatshere[zoom]=17"
        
        # Показываем inline кнопки для подтверждения
        from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
        markup = InlineKeyboardMarkup()
        markup.row(
            InlineKeyboardButton("✅ Да, верно", callback_data="confirm_start_address"),
            InlineKeyboardButton("❌ Нет, ввести заново", callback_data="reject_start_address")
        )
        
        # Отправляем сообщение с превью карт
        self.bot.send_message(
            message.chat.id,
            f"📍 <b>Проверьте адрес точки старта</b>\n\n"
            f"<b>Адрес:</b> {address}\n"
            f"<b>Координаты:</b> {lat:.6f}, {lon:.6f}\n\n"
            f"🔗 <a href='{dgis_link}'>Открыть в 2ГИС</a> | "
            f"<a href='{yandex_link}'>Открыть в Яндекс Картах</a>\n\n"
            f"Правильно ли определен адрес?",
            parse_mode='HTML',
            reply_markup=markup,
            disable_web_page_preview=False  # Включаем превью ссылок
        )
    
    def handle_confirm_start_address(self, call):
        """Подтверждение адреса точки старта через callback"""
        user_id = call.from_user.id
        today = date.today()
        
        state_data = self.parent.get_user_state(user_id)
        pending_location = state_data.get('pending_location')
        
        if not pending_location:
            self.bot.answer_callback_query(call.id, "❌ Данные не найдены")
            return
        
        # Сохраняем в БД (start_time=None, будет введен на следующем шаге)
        self.parent.db_service.save_start_location(
            user_id,
            'address',
            pending_location['address'],
            pending_location['lat'],
            pending_location['lon'],
            None,  # start_time (не gid!)
            today
        )
        
        self.bot.answer_callback_query(call.id, "✅ Адрес сохранен")
        self.bot.edit_message_text(
            f"✅ Точка старта сохранена: {pending_location['address']}\n\n"
            "⏰ Введите время старта (например, 09:00):",
            call.message.chat.id,
            call.message.message_id
        )
        
        self.parent.update_user_state(user_id, 'state', 'waiting_for_start_time')
    
    def handle_reject_start_address(self, call):
        """Отклонение адреса точки старта - запрос повторного ввода"""
        user_id = call.from_user.id
        
        self.bot.answer_callback_query(call.id, "Введите адрес заново")
        self.bot.edit_message_text(
            "❌ Адрес не подтвержден.\n\n"
            "✍️ Введите адрес точки старта заново:",
            call.message.chat.id,
            call.message.message_id
        )
        
        # Возвращаем в состояние ожидания адреса
        self.parent.update_user_state(user_id, 'state', 'waiting_for_start_address')
        self.parent.update_user_state(user_id, 'pending_location', None)
    
    def process_start_time(self, message):
        """Обработка времени старта"""
        user_id = message.from_user.id
        today = date.today()
        
        if message.text == "⬅️ Главное меню":
            self.parent.clear_user_state(user_id)
            self.bot.send_message(
                message.chat.id,
                "Главное меню",
                reply_markup=self.parent._main_menu_markup(user_id)
            )
            return
        
        time_str = message.text.strip()
        
        # Парсим время
        try:
            time_parts = time_str.split(':')
            if len(time_parts) != 2:
                raise ValueError("Неверный формат")
            
            hour = int(time_parts[0])
            minute = int(time_parts[1])
            
            if not (0 <= hour <= 23 and 0 <= minute <= 59):
                raise ValueError("Неверное время")
            
            # Создаем datetime на сегодня
            start_datetime = datetime.combine(today, time(hour, minute))
            
        except Exception as e:
            self.bot.reply_to(
                message,
                f"❌ Неверный формат времени. Используйте формат ЧЧ:ММ (например, 09:00)"
            )
            return
        
        # Обновляем время старта в БД
        self.parent.db_service.update_start_time(user_id, start_datetime, today)
        
        self.bot.send_message(
            message.chat.id,
            f"✅ Время старта установлено: {start_datetime.strftime('%H:%M')}",
            reply_markup=self.parent._main_menu_markup(user_id)
        )
        
        self.parent.clear_user_state(user_id)
    
    # ==================== ОПТИМИЗАЦИЯ МАРШРУТА ====================
    
    def handle_optimize_route(self, message):
        """Handle /optimize_route command"""
        try:
            user_id = message.from_user.id
            today = date.today()
            
            logger.debug(f"Начало оптимизации для user_id={user_id}")
            
            # Загружаем заказы из БД
            try:
                orders_data = self.parent.db_service.get_today_orders(user_id)
                logger.debug(f"Загружено заказов: {len(orders_data) if orders_data else 0}")
            except Exception as e:
                logger.error(f"Ошибка загрузки заказов: {e}", exc_info=True)
                self.bot.reply_to(message, f"❌ Ошибка загрузки заказов: {str(e)}", reply_markup=self.parent._route_menu_markup())
                return
            
            if not orders_data:
                user_id = message.from_user.id
                self.bot.reply_to(message, "❌ Нет добавленных заказов. Добавьте их через кнопку ➕ Добавить заказы", reply_markup=self.parent._orders_menu_markup(user_id))
                return

            # Фильтруем доставленные заказы
            active_orders_data = [od for od in orders_data if od.get('status', 'pending') != 'delivered']
            
            if not active_orders_data:
                user_id = message.from_user.id
                self.bot.reply_to(message, "❌ Нет активных заказов для оптимизации. Все заказы доставлены.", reply_markup=self.parent._orders_menu_markup(user_id))
                return
            
            # Загружаем подтвержденные звонки для сохранения их при повторной оптимизации
            try:
                confirmed_calls = self.parent.db_service.get_confirmed_calls(user_id, today)
                confirmed_order_numbers = set(call['order_number'] for call in confirmed_calls)
                logger.info(f"Найдено {len(confirmed_calls)} подтвержденных звонков: {confirmed_order_numbers}")
            except Exception as e:
                logger.error(f"Ошибка загрузки подтвержденных звонков: {e}", exc_info=True)
                confirmed_calls = []
                confirmed_order_numbers = set()

            # Загружаем точку старта из БД
            try:
                start_location_data = self.parent.db_service.get_start_location(user_id, today)
                logger.debug(f"Данные точки старта: {start_location_data}")
            except Exception as e:
                logger.error(f"Ошибка загрузки точки старта: {e}", exc_info=True)
                self.bot.reply_to(message, f"❌ Ошибка загрузки точки старта: {str(e)}", reply_markup=self.parent._route_menu_markup())
                return
            
            if not start_location_data:
                self.bot.reply_to(message, "❌ Не установлена точка старта. Используйте кнопку 📍 Точка старта", reply_markup=self.parent._route_menu_markup())
                return
            
            start_address = start_location_data.get('address')
            start_lat = start_location_data.get('latitude')
            start_lon = start_location_data.get('longitude')
            start_time_str = start_location_data.get('start_time')
            location_type = start_location_data.get('location_type')
            
            if not start_time_str:
                self.bot.reply_to(message, "❌ Не установлено время старта. Используйте кнопку 📍 Точка старта", reply_markup=self.parent._route_menu_markup())
                return

            # Convert data back to Order objects
            # Разделяем на подтвержденные (confirmed calls) и неподтвержденные заказы
            confirmed_orders = []  # Заказы с подтвержденными звонками (сохраняем порядок из предыдущего маршрута)
            unconfirmed_orders = []  # Заказы для новой оптимизации
            
            for order_data in active_orders_data:
                try:
                    # Преобразуем строки времени обратно в time объекты
                    order_dict = order_data.copy()
                    if order_dict.get('delivery_time_start'):
                        if isinstance(order_dict['delivery_time_start'], str):
                            parts = order_dict['delivery_time_start'].split(':')
                            if len(parts) >= 2:
                                order_dict['delivery_time_start'] = time(int(parts[0]), int(parts[1]))
                            else:
                                order_dict['delivery_time_start'] = None
                    if order_dict.get('delivery_time_end'):
                        if isinstance(order_dict['delivery_time_end'], str):
                            parts = order_dict['delivery_time_end'].split(':')
                            if len(parts) >= 2:
                                order_dict['delivery_time_end'] = time(int(parts[0]), int(parts[1]))
                            else:
                                order_dict['delivery_time_end'] = None
                    
                    order = Order(**order_dict)
                    
                    # DEBUG: Логируем manual_arrival_time СРАЗУ после создания Order
                    logger.info(f"📦 DEBUG: Заказ #{order.order_number} создан из БД, manual_arrival_time = {order.manual_arrival_time} (тип: {type(order.manual_arrival_time)})")
                    
                    # Разделяем по признаку подтвержденного звонка
                    if order.order_number and order.order_number in confirmed_order_numbers:
                        confirmed_orders.append(order)
                    else:
                        unconfirmed_orders.append(order)
                except Exception as e:
                    logger.error(f"Ошибка создания Order из данных: {e}, данные: {order_data}", exc_info=True)
                    continue
            
            # Для оптимизации используем только неподтвержденные заказы
            orders = unconfirmed_orders
            
            if not orders and not confirmed_orders:
                self.bot.reply_to(message, "❌ Не удалось обработать заказы. Проверьте данные.", reply_markup=self.parent._route_menu_markup())
                return
            
            if not orders and confirmed_orders:
                # Все заказы уже подтверждены - повторная оптимизация не нужна
                self.bot.reply_to(message, "✅ Все заказы уже подтверждены. Маршрут не требует оптимизации.", reply_markup=self.parent._route_menu_markup())
                return
            
            try:
                start_datetime = datetime.fromisoformat(start_time_str) if isinstance(start_time_str, str) else start_time_str
            except Exception as e:
                logger.error(f"Ошибка парсинга времени старта: {e}, start_time_str: {start_time_str}", exc_info=True)
                self.bot.reply_to(message, f"❌ Ошибка обработки времени старта: {str(e)}", reply_markup=self.parent._route_menu_markup())
                return
            
            # Если есть подтвержденные заказы - начинаем маршрут с последнего подтвержденного
            # Загружаем предыдущий маршрут из БД
            actual_start_from_confirmed = None
            if confirmed_orders:
                try:
                    route_data = self.parent.db_service.get_route_data(user_id, today)
                    if route_data:
                        route_points_data = route_data.get('route_points_data', [])
                        route_order = route_data.get('route_order', [])
                        
                        # Находим последний подтвержденный заказ в маршруте
                        last_confirmed_index = -1
                        last_confirmed_order_number = None
                        for i, order_num in enumerate(route_order):
                            if order_num in confirmed_order_numbers:
                                last_confirmed_index = i
                                last_confirmed_order_number = order_num
                        
                        if last_confirmed_index >= 0 and last_confirmed_index < len(route_points_data):
                            last_point_data = route_points_data[last_confirmed_index]
                            # Находим соответствующий Order объект для получения координат
                            last_confirmed_order = next(
                                (o for o in confirmed_orders if o.order_number == last_confirmed_order_number),
                                None
                            )
                            
                            if last_confirmed_order and last_confirmed_order.latitude and last_confirmed_order.longitude:
                                # Получаем настройки пользователя для времени на точке
                                user_settings = self.parent.settings_service.get_settings(user_id)
                                
                                # Время прибытия + время на точке = новая точка старта
                                arrival_time = datetime.fromisoformat(last_point_data['estimated_arrival'])
                                new_start_time = arrival_time + timedelta(minutes=user_settings.service_time_minutes)
                                
                                actual_start_from_confirmed = {
                                    'lat': last_confirmed_order.latitude,
                                    'lon': last_confirmed_order.longitude,
                                    'time': new_start_time,
                                    'order_number': last_confirmed_order_number
                                }
                                
                                logger.info(f"🎯 Начинаем оптимизацию от последнего подтвержденного заказа {last_confirmed_order_number}: координаты ({last_confirmed_order.latitude}, {last_confirmed_order.longitude}), время {new_start_time.strftime('%H:%M')}")
                except Exception as e:
                    logger.error(f"Ошибка определения точки старта от подтвержденного заказа: {e}", exc_info=True)
                    # Продолжаем с обычной точкой старта
            
            # Определяем координаты старта - используем сохраненные координаты из БД
            # Или координаты последнего подтвержденного заказа
            if actual_start_from_confirmed:
                # Начинаем от последнего подтвержденного заказа
                start_location = {'lat': actual_start_from_confirmed['lat'], 'lon': actual_start_from_confirmed['lon']}
                start_location_coords = (actual_start_from_confirmed['lat'], actual_start_from_confirmed['lon'])
                start_datetime = actual_start_from_confirmed['time']
                location_description = f"последнего подтвержденного заказа {actual_start_from_confirmed['order_number']}"
            elif start_lat and start_lon:
                # Координаты уже есть в БД (были сохранены при подтверждении адреса или при отправке геопозиции)
                start_location = {'lat': start_lat, 'lon': start_lon}
                start_location_coords = (start_lat, start_lon)
                location_description = f"{'геопозиции' if location_type == 'geo' else 'адреса'} ({start_lat:.6f}, {start_lon:.6f})"
            elif start_address:
                # Координат нет, но есть адрес (старые данные) - нужно загеокодировать
                start_location = None
                start_location_coords = None
            else:
                start_location = None
                start_location_coords = None
            
            logger.debug(f"Начало оптимизации: {len(orders)} заказов, точка старта: {start_location or start_address}")

            # Отправляем начальное сообщение и включаем typing indicator
            status_msg = self.bot.reply_to(message, "🔄 <b>Начинаю оптимизацию маршрута...</b>\n\n⏳ Загружаю данные...", parse_mode='HTML')
            self.bot.send_chat_action(message.chat.id, 'typing')

            # Initialize services
            maps_service = MapsService()

            # Get start location coordinates - используем сохраненные координаты из БД
            if start_location_coords:
                # Координаты уже есть в БД (были сохранены при подтверждении адреса или при отправке геопозиции)
                self.bot.edit_message_text(
                    "🔄 <b>Оптимизация маршрута</b>\n\n✅ Точка старта определена (координаты из БД)\n⏳ Геокодирую адреса заказов...",
                    message.chat.id,
                    status_msg.message_id,
                    parse_mode='HTML'
                )
            elif start_address:
                # Координат нет в БД, но есть адрес (старые данные или не подтвержденный адрес) - нужно загеокодировать
                self.bot.edit_message_text(
                    "🔄 <b>Оптимизация маршрута</b>\n\n⏳ Определяю координаты точки старта...",
                    message.chat.id,
                    status_msg.message_id,
                    parse_mode='HTML'
                )
                self.bot.send_chat_action(message.chat.id, 'typing')
                
                start_lat, start_lon, gid = maps_service.geocode_address_sync(start_address)
                if not start_lat or not start_lon:
                    self.bot.edit_message_text(
                        f"❌ Не удалось определить координаты точки старта: {start_address}",
                        message.chat.id,
                        status_msg.message_id,
                        parse_mode='HTML'
                    )
                    return
                start_location_coords = (start_lat, start_lon)
                location_description = f"адреса: {start_address}"
                
                # Сохраняем координаты в БД для будущего использования
                self.parent.db_service.save_start_location(
                    user_id, 'address', start_address, start_lat, start_lon, None, today
                )
                
                self.bot.edit_message_text(
                    "🔄 <b>Оптимизация маршрута</b>\n\n✅ Точка старта определена\n⏳ Геокодирую адреса заказов...",
                    message.chat.id,
                    status_msg.message_id,
                    parse_mode='HTML'
                )
            else:
                self.bot.edit_message_text(
                    "❌ Не удалось получить координаты точки старта",
                    message.chat.id,
                    status_msg.message_id,
                    parse_mode='HTML'
                )
                return

            # Геокодирование адресов заказов (только для тех, у кого нет координат)
            self.bot.send_chat_action(message.chat.id, 'typing')
            orders_to_geocode = [o for o in orders if not o.latitude or not o.longitude]
            if orders_to_geocode:
                total_to_geocode = len(orders_to_geocode)
                self.bot.edit_message_text(
                    f"🔄 <b>Оптимизация маршрута</b>\n\n✅ Точка старта определена\n⏳ Геокодирую адреса: 0/{total_to_geocode}...",
                    message.chat.id,
                    status_msg.message_id,
                    parse_mode='HTML'
                )
                for idx, order in enumerate(orders_to_geocode, 1):
                    # Обновляем сообщение перед обработкой каждого заказа
                    if idx == 1 or idx % 3 == 0 or idx == total_to_geocode:
                        self.bot.edit_message_text(
                            f"🔄 <b>Оптимизация маршрута</b>\n\n✅ Точка старта определена\n⏳ Геокодирую адреса: {idx}/{total_to_geocode}...",
                            message.chat.id,
                            status_msg.message_id,
                            parse_mode='HTML'
                        )
                    self.bot.send_chat_action(message.chat.id, 'typing')
                    # Проверяем, что адрес не пустой перед геокодированием
                    if order.address and order.address.strip():
                        lat, lon, gid = maps_service.geocode_address_sync(order.address)
                        if lat and lon:
                            order.latitude = lat
                            order.longitude = lon
                            order.gis_id = gid
                    else:
                        logger.warning(f"⚠️ Заказ {order.order_number} не может быть загеокодирован: адрес отсутствует")

            # Initialize route optimizer
            total_orders = len(orders)
            if orders_to_geocode:
                geocoded_count = len(orders_to_geocode)
                already_geocoded = total_orders - geocoded_count
                if already_geocoded > 0:
                    self.bot.edit_message_text(
                        f"🔄 <b>Оптимизация маршрута</b>\n\n✅ Адреса обработаны: {geocoded_count} загеокодировано, {already_geocoded} уже были в БД\n⏳ Всего заказов: {total_orders}\n⏳ Рассчитываю оптимальный маршрут...",
                        message.chat.id,
                        status_msg.message_id,
                        parse_mode='HTML'
                    )
                else:
                    self.bot.edit_message_text(
                        f"🔄 <b>Оптимизация маршрута</b>\n\n✅ Все адреса загеокодированы ({total_orders} заказов)\n⏳ Рассчитываю оптимальный маршрут...",
                        message.chat.id,
                        status_msg.message_id,
                        parse_mode='HTML'
                    )
            else:
                self.bot.edit_message_text(
                    f"🔄 <b>Оптимизация маршрута</b>\n\n✅ Все адреса уже загеокодированы ({total_orders} заказов)\n⏳ Рассчитываю оптимальный маршрут...",
                    message.chat.id,
                    status_msg.message_id,
                    parse_mode='HTML'
                )
            self.bot.send_chat_action(message.chat.id, 'typing')
            
            # DEBUG: Логируем заказы перед оптимизацией
            logger.info(f"🚀 DEBUG: Отправляем {len(orders)} заказов на оптимизацию")
            for order in orders:
                logger.info(f"   → Заказ #{order.order_number}: manual_arrival_time = {order.manual_arrival_time}")
            
            route_optimizer = RouteOptimizer(maps_service)
            # Проверяем, есть ли ручные времена - если нет, используем fallback при ошибке
            has_manual_times_check = False
            with get_db_session() as session:
                from sqlalchemy import and_
                manual_calls_check = session.query(CallStatusDB).filter(
                    and_(
                        CallStatusDB.user_id == user_id,
                        CallStatusDB.call_date == today,
                        CallStatusDB.is_manual_arrival == True,
                        CallStatusDB.manual_arrival_time.isnot(None)
                    )
                ).all()
                has_manual_times_check = len(manual_calls_check) > 0
            
            optimized_route = route_optimizer.optimize_route_sync(
                orders, start_location_coords, start_datetime, 
                user_id=user_id,
                use_fallback=not has_manual_times_check  # Используем fallback только если нет ручных времен
            )
            
            # Проверяем результат оптимизации
            if not optimized_route or not optimized_route.points:
                # Проверяем наличие ручных времен
                has_manual_times = False
                with get_db_session() as session:
                    from sqlalchemy import and_
                    manual_calls = session.query(CallStatusDB).filter(
                        and_(
                            CallStatusDB.user_id == user_id,
                            CallStatusDB.call_date == today,
                            CallStatusDB.is_manual_arrival == True,
                            CallStatusDB.manual_arrival_time.isnot(None)
                        )
                    ).all()
                    has_manual_times = len(manual_calls) > 0
                
                # Загружаем предыдущий маршрут, если он есть
                previous_route_data = self.parent.db_service.get_route_data(user_id, today)
                if previous_route_data:
                    error_text = (
                        "❌ <b>Не удалось оптимизировать маршрут</b>\n\n"
                        "⚠️ Возможен конфликт между временными окнами доставки и ручными временами прибытия.\n\n"
                        "💡 <b>Рекомендации:</b>\n"
                        "• Проверьте временные окна доставки заказов\n"
                        "• Убедитесь, что ручные времена прибытия не конфликтуют с окнами доставки\n"
                        "• Попробуйте изменить ручные времена или временные окна\n\n"
                        "📋 <b>Предыдущий маршрут сохранен</b>"
                    )
                else:
                    error_text = (
                        "❌ <b>Не удалось оптимизировать маршрут</b>\n\n"
                        "⚠️ Возможен конфликт между временными окнами доставки и ручными временами прибытия.\n\n"
                        "💡 <b>Рекомендации:</b>\n"
                        "• Проверьте временные окна доставки заказов\n"
                        "• Убедитесь, что ручные времена прибытия не конфликтуют с окнами доставки\n"
                        "• Попробуйте изменить ручные времена или временные окна"
                    )
                
                # Удаляем статусное сообщение и отправляем новое с клавиатурой
                try:
                    self.bot.delete_message(message.chat.id, status_msg.message_id)
                except Exception as e:
                    logger.warning(f"Не удалось удалить статусное сообщение: {e}")
                
                # Создаем клавиатуру
                if has_manual_times:
                    from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
                    markup = InlineKeyboardMarkup()
                    markup.add(InlineKeyboardButton(
                        "🔄 Пересчитать без ручных времен",
                        callback_data="recalculate_without_manual"
                    ))
                    markup.add(InlineKeyboardButton(
                        "📋 Меню маршрута",
                        callback_data="route_menu"
                    ))
                    reply_markup = markup
                else:
                    reply_markup = self.parent._route_menu_markup()
                
                self.bot.reply_to(
                    message,
                    error_text,
                    parse_mode='HTML',
                    reply_markup=reply_markup
                )
                return
            
            self.bot.edit_message_text(
                f"🔄 <b>Оптимизация маршрута</b>\n\n✅ Маршрут рассчитан\n⏳ Формирую детальный план...",
                message.chat.id,
                status_msg.message_id,
                parse_mode='HTML'
            )
            self.bot.send_chat_action(message.chat.id, 'typing')

            # Build route summary
            # Сохраняем структурированные данные маршрута вместо готового текста
            route_points_data = []
            call_schedule = []
            
            # Получаем настройки пользователя для времени звонка
            user_settings = self.parent.settings_service.get_settings(user_id)

            # Загружаем существующие call_status для текущего дня,
            # чтобы учитывать РУЧНЫЕ времена звонка/прибытия при формировании плана.
            # ВАЖНО: сохраняем только примитивные значения, а не ORM-объекты,
            # чтобы не обращаться к ним после закрытия сессии.
            call_status_map = {}
            with get_db_session() as session:
                statuses = session.query(CallStatusDB).filter(
                    CallStatusDB.user_id == user_id,
                    CallStatusDB.call_date == today
                ).all()
                for cs in statuses:
                    call_status_map[cs.order_number] = {
                        "is_manual_call": bool(getattr(cs, "is_manual_call", False)),
                        "call_time": cs.call_time,
                        "is_manual_arrival": bool(getattr(cs, "is_manual_arrival", False)),
                        "manual_arrival_time": cs.manual_arrival_time,
                    }
            
            # Если есть подтвержденные заказы - добавляем их в начало маршрута
            if actual_start_from_confirmed and confirmed_orders:
                try:
                    # Загружаем данные предыдущего маршрута
                    previous_route_data = self.parent.db_service.get_route_data(user_id, today)
                    if previous_route_data:
                        previous_route_points = previous_route_data.get('route_points_data', [])
                        previous_route_order = previous_route_data.get('route_order', [])
                        previous_call_schedule = previous_route_data.get('call_schedule', [])
                        
                        # Добавляем подтвержденные точки из предыдущего маршрута
                        for order_num in previous_route_order:
                            if order_num in confirmed_order_numbers:
                                # Находим данные точки в предыдущем маршруте
                                point_index = previous_route_order.index(order_num)
                                if point_index < len(previous_route_points):
                                    route_points_data.append(previous_route_points[point_index])
                                
                                # Находим данные звонка в предыдущем расписании
                                call_data = next(
                                    (c for c in previous_call_schedule if c.get('order_number') == order_num),
                                    None
                                )
                                if call_data:
                                    call_schedule.append(call_data)
                        
                        logger.info(f"✅ Добавлено {len([o for o in previous_route_order if o in confirmed_order_numbers])} подтвержденных точек в начало маршрута")
                except Exception as e:
                    logger.error(f"Ошибка добавления подтвержденных заказов в маршрут: {e}", exc_info=True)

            for i, point in enumerate(optimized_route.points, 1):
                order = point.order

                # Подтягиваем существующий call_status (если есть)
                cs = call_status_map.get(order.order_number) if order.order_number else None
                manual_call_time = None
                manual_arrival_time = None
                if cs:
                    if cs.get("is_manual_call") and cs.get("call_time"):
                        manual_call_time = cs["call_time"]
                    if cs.get("is_manual_arrival") and cs.get("manual_arrival_time"):
                        manual_arrival_time = cs["manual_arrival_time"]

                # Синхронизируем manual_arrival_time в Order с БД, если его не было
                if manual_arrival_time and not order.manual_arrival_time:
                    order.manual_arrival_time = manual_arrival_time

                # Фактическое время прибытия: ручное (если есть) или рассчитанное оптимизатором
                actual_arrival_time = order.manual_arrival_time if order.manual_arrival_time else point.estimated_arrival
                if order.manual_arrival_time:
                    logger.info(f"⏰ Используется ручное время прибытия для заказа {order.order_number}: {actual_arrival_time.strftime('%H:%M')}")

                # Время звонка:
                #  - если есть РУЧНОЕ время звонка -> используем его
                #  - иначе рассчитываем от фактического времени прибытия
                if manual_call_time:
                    call_time = manual_call_time
                    logger.info(
                        f"📞 Используется РУЧНОЕ время звонка для заказа {order.order_number}: "
                        f"{call_time.strftime('%H:%M')}"
                    )
                else:
                    call_time = actual_arrival_time - timedelta(minutes=user_settings.call_advance_minutes)

                    # Если есть окно доставки, не звоним слишком рано
                    if order.delivery_time_start:
                        today_call = actual_arrival_time.date()
                        window_start = datetime.combine(today_call, order.delivery_time_start)
                        earliest_call = window_start - timedelta(minutes=user_settings.call_advance_minutes)
                        if call_time < earliest_call:
                            call_time = earliest_call
                
                # Сохраняем структурированные данные для каждой точки маршрута
                route_point_data = {
                    "order_number": order.order_number or str(order.id),
                    "estimated_arrival": actual_arrival_time.isoformat(),
                    "distance_from_previous": point.distance_from_previous,
                    "time_from_previous": point.time_from_previous,
                    "call_time": call_time.isoformat(),
                    "manual_arrival_time": order.manual_arrival_time.isoformat() if order.manual_arrival_time else None
                }
                route_points_data.append(route_point_data)

                # Сохраняем структурированные данные для графика звонков
                call_data = {
                    "order_number": order.order_number or str(order.id),
                    "call_time": call_time.isoformat(),
                    "arrival_time": actual_arrival_time.isoformat(),
                    "phone": order.phone or None,
                    "customer_name": order.customer_name or None
                }
                call_schedule.append(call_data)
                
                # Создаем/обновляем запись о звонке для уведомлений
                # ВАЖНО: обновляем call_time для ВСЕХ заказов, даже без телефона,
                # чтобы уведомления использовали актуальное время
                if order.order_number:
                    if order.order_number in confirmed_order_numbers:
                        logger.info(f"⏭️ Пропускаем создание call_status для заказа {order.order_number} - звонок уже подтвержден")
                    else:
                        logger.debug(
                            f"Создание/обновление записи о звонке: заказ {order.order_number}, "
                            f"время звонка {call_time.strftime('%Y-%m-%d %H:%M:%S')}, "
                            f"прибытие {actual_arrival_time.strftime('%Y-%m-%d %H:%M:%S')}"
                        )
                        # Используем телефон из заказа или "Не указан" если его нет
                        phone = order.phone or "Не указан"
                        self.parent.call_notifier.create_call_status(
                            user_id,
                            order.order_number,
                            call_time,
                            phone,
                            order.customer_name,
                            today,
                            is_manual_call=bool(manual_call_time),
                            is_manual_arrival=bool(order.manual_arrival_time),
                            arrival_time=actual_arrival_time,
                            manual_arrival_time=order.manual_arrival_time
                        )

            # Сохраняем порядок заказов в маршруте
            # Сначала подтвержденные (в порядке из предыдущего маршрута), затем новые
            confirmed_route_order = [
                point_data['order_number'] 
                for point_data in route_points_data 
                if 'order_number' in point_data
            ]  # Уже добавленные подтвержденные заказы
            new_route_order = [point.order.order_number or str(point.order.id) for point in optimized_route.points]
            route_order = confirmed_route_order + new_route_order
            
            # Сохраняем обновленные координаты заказов в БД (если они были загеокодированы)
            for point in optimized_route.points:
                order = point.order
                if order.latitude and order.longitude and order.order_number:
                    # Обновляем координаты заказа в БД
                    updates = {
                        'latitude': order.latitude,
                        'longitude': order.longitude,
                    }
                    if order.gis_id:
                        updates['gis_id'] = order.gis_id
                    try:
                        self.parent.db_service.update_order(user_id, order.order_number, updates, today)
                    except Exception as e:
                        logger.warning(f"Не удалось обновить координаты заказа {order.order_number}: {e}")
            
            # Сохраняем структурированные данные маршрута в БД
            self.parent.db_service.save_route_data(
                user_id,
                route_points_data,  # Структурированные данные вместо готового текста
                call_schedule,
                route_order,
                optimized_route.total_distance,
                optimized_route.total_time,
                optimized_route.estimated_completion,
                today
            )
            
            # Также сохраняем в state для обратной совместимости
            self.parent.update_user_state(user_id, 'route_points_data', route_points_data)
            self.parent.update_user_state(user_id, 'call_schedule', call_schedule)
            self.parent.update_user_state(user_id, 'route_order', route_order)
            # Сохраняем optimized_route для мониторинга пробок
            self.parent.update_user_state(user_id, 'optimized_route', optimized_route)
            self.parent.update_user_state(user_id, 'optimized_orders', orders)
            start_location_tuple = None
            if start_location_data:
                if start_location_data.get('latitude') and start_location_data.get('longitude'):
                    start_location_tuple = (start_location_data['latitude'], start_location_data['longitude'])
            self.parent.update_user_state(user_id, 'start_location', start_location_tuple)
            if start_location_data and start_location_data.get('start_time'):
                start_time_str = start_location_data['start_time']
                if isinstance(start_time_str, str):
                    start_time = datetime.fromisoformat(start_time_str)
                else:
                    start_time = start_time_str
                self.parent.update_user_state(user_id, 'start_time', start_time.isoformat() if isinstance(start_time, datetime) else start_time)

            # Формируем итоговое сообщение (форматируем маршрут для отображения)
            orders_data = self.parent.db_service.get_today_orders(user_id)
            orders_dict = {od.get('order_number'): od for od in orders_data if od.get('order_number')}
            start_location_data = self.parent.db_service.get_start_location(user_id, today) or {}
            formatted_route = self._format_route_summary(user_id, route_points_data, orders_dict, start_location_data, maps_service)
            
            summary_text = (
                f"✅ <b>Маршрут оптимизирован!</b>\n\n"
                f"📊 Всего заказов: {len(optimized_route.points)}\n"
                f"📏 Общее расстояние: {optimized_route.total_distance:.1f} км\n"
                f"⏱️ Общее время: {optimized_route.total_time:.0f} мин\n"
                f"🏁 Завершение: {optimized_route.estimated_completion.strftime('%H:%M')}\n\n"
                f"<b>Маршрут:</b>\n" + "\n\n".join(item["text"] for item in formatted_route[:3])
            )

            if len(formatted_route) > 3:
                summary_text += f"\n... и ещё {len(formatted_route) - 3} заказов"

            # Редактируем статусное сообщение на итоговое
            try:
                self.bot.edit_message_text(
                    summary_text,
                    message.chat.id,
                    status_msg.message_id,
                    parse_mode='HTML',
                    disable_web_page_preview=True
                )
            except Exception:
                # Если не удалось отредактировать (например, сообщение слишком длинное), отправляем новое
                self.bot.delete_message(message.chat.id, status_msg.message_id)
                self.bot.reply_to(message, summary_text, parse_mode='HTML', reply_markup=self.parent._route_menu_markup(), disable_web_page_preview=True)

        except Exception as e:
            logger.error(f"Ошибка оптимизации маршрута: {e}", exc_info=True)
            
            # Обновляем статусное сообщение с ошибкой (если оно было создано)
            try:
                if 'status_msg' in locals():
                    # Удаляем статусное сообщение и отправляем новое с клавиатурой
                    try:
                        self.bot.delete_message(message.chat.id, status_msg.message_id)
                    except Exception as del_error:
                        logger.warning(f"Не удалось удалить статусное сообщение: {del_error}")
                    
                    self.bot.reply_to(
                        message,
                        f"❌ <b>Ошибка оптимизации</b>\n\n{str(e)}",
                        parse_mode='HTML',
                        reply_markup=self.parent._route_menu_markup()
                    )
                else:
                    # Если статусное сообщение не было создано, отправляем новое
                    self.bot.reply_to(message, f"❌ Ошибка оптимизации: {str(e)}", reply_markup=self.parent._route_menu_markup())
            except Exception as edit_error:
                logger.warning(f"Ошибка при отправке сообщения об ошибке: {edit_error}")
                # Если не удалось отправить, пробуем еще раз без форматирования
                try:
                    self.bot.reply_to(message, f"❌ Ошибка оптимизации: {str(e)}", reply_markup=self.parent._route_menu_markup())
                except Exception as final_error:
                    logger.error(f"Критическая ошибка при отправке сообщения: {final_error}")
    
    # ==================== ВСПОМОГАТЕЛЬНЫЕ МЕТОДЫ ====================
    
    def _build_order_delivered_keyboard(self, order_number: str):
        """Строит inline‑клавиатуру для одного заказа: кнопка "✅ Доставлен"."""
        from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton

        markup = InlineKeyboardMarkup()
        callback_data = f"route_delivered_{order_number}"
        # callback_data ограничено 64 символами, наш формат безопасен
        markup.add(InlineKeyboardButton("✅ Доставлен", callback_data=callback_data))
        return markup

    def _format_route_summary(self, user_id: int, route_points_data: List[Dict], orders_dict: Dict[str, Dict], 
                              start_location_data: Dict, maps_service, start_index: int = 1, 
                              prev_latlon: tuple = None, prev_gid: str = None) -> List[Dict]:
        """
        Форматирует маршрут из структурированных данных.
        
        Args:
            start_index: Начальный номер для нумерации заказов (по умолчанию 1)
        
        Returns:
            Список словарей:
            {
                "text": "<строка с описанием точки маршрута>",
                "order_number": "<номер заказа или None>"
            }
        """
        route_summary: List[Dict] = []
        
        # Получаем координаты старта (если не переданы явно)
        if prev_latlon is None:
            if start_location_data:
                if start_location_data.get('location_type') == 'geo':
                    prev_latlon = (start_location_data.get('latitude'), start_location_data.get('longitude'))
                elif start_location_data.get('latitude') and start_location_data.get('longitude'):
                    prev_latlon = (start_location_data.get('latitude'), start_location_data.get('longitude'))
        
        # ВАЖНО: выводим маршрут в хронологическом порядке по фактическому времени прибытия,
        # а не в "сыром" порядке вершин из оптимизатора. Это делает план понятным для человека.
        try:
            sorted_points = sorted(
                route_points_data,
                key=lambda pd: datetime.fromisoformat(pd.get("estimated_arrival"))
            )
        except Exception as e:
            logger.error(f"Ошибка сортировки точек маршрута по времени прибытия: {e}", exc_info=True)
            sorted_points = route_points_data

        for i, point_data in enumerate(sorted_points, start_index):
            order_number = point_data.get('order_number')
            if not order_number:
                continue
                
            order_data = orders_dict.get(order_number)
            if not order_data:
                continue
            
            # ВАЖНО: Пропускаем доставленные заказы
            if order_data.get('status', 'pending') == 'delivered':
                logger.debug(f"Пропускаем доставленный заказ {order_number} в маршруте")
                continue
            
            # Преобразуем данные заказа
            try:
                order = Order(**order_data)
            except Exception as e:
                logger.error(f"Ошибка создания Order из данных: {e}", exc_info=True)
                continue
            
            # Парсим время
            try:
                estimated_arrival = datetime.fromisoformat(point_data['estimated_arrival'])
                call_time = datetime.fromisoformat(point_data['call_time'])
            except Exception as e:
                logger.error(f"Ошибка парсинга времени: {e}", exc_info=True)
                continue
            
            # Определяем заголовок заказа
            if order.order_number:
                order_title = f"Заказ №{order.order_number}"
                if order.customer_name:
                    order_title += f" ({order.customer_name})"
            else:
                order_title = order.customer_name or 'Клиент'

            # Формируем информацию о заказе
            order_info = [f"<b>{i}. {order_title}</b>"]
            
            # Адрес
            if order.address:
                order_info.append(f"📍 {order.address}")
            else:
                order_info.append("📍 Адрес не указан")
            
            # Контакты (компактно)
            contact_parts = []
            if order.customer_name:
                contact_parts.append(f"👤 {order.customer_name}")
            if order.phone:
                contact_parts.append(f"📞 {order.phone}")
            if contact_parts:
                order_info.append(" | ".join(contact_parts))
            elif not order.phone:
                order_info.append("📞 Телефон не указан")

            # Время доставки и статус
            if order.delivery_time_window:
                arrival_status = ""
                if order.delivery_time_start and order.delivery_time_end:
                    today_date = estimated_arrival.date()
                    window_start = datetime.combine(today_date, order.delivery_time_start)
                    window_end = datetime.combine(today_date, order.delivery_time_end)

                    if estimated_arrival < window_start:
                        arrival_status = f" ⚠️ Раньше окна"
                    elif estimated_arrival > window_end:
                        arrival_status = f" 🚨 Позже окна"
                    else:
                        arrival_status = f" ✅"
                
                order_info.append(f"🕐 {order.delivery_time_window} | Прибытие: {estimated_arrival.strftime('%H:%M')}{arrival_status}")

            # Детали доставки (компактно)
            delivery_details = []
            if order.entrance_number:
                delivery_details.append(f"🏢 Подъезд {order.entrance_number}")
            if order.apartment_number:
                delivery_details.append(f"🚪 Кв. {order.apartment_number}")
            if delivery_details:
                order_info.append(" | ".join(delivery_details))
            
            # Проверяем статус звонка
            call_status_text = f"📞 Звонок: {call_time.strftime('%H:%M')}"
            try:
                with get_db_session() as session:
                    call_status = session.query(CallStatusDB).filter(
                        CallStatusDB.order_number == order.order_number,
                        CallStatusDB.call_date == estimated_arrival.date()
                    ).first()
                    if call_status:
                        if call_status.status == "failed":
                            call_status_text = "🔴 НЕДОЗВОН"
                        elif call_status.status == "confirmed":
                            call_status_text = f"✅ Звонок: {call_time.strftime('%H:%M')}"
            except Exception as e:
                logger.debug(f"Ошибка получения статуса звонка: {e}")
            
            # Время звонка и маршрут (компактно)
            route_info = [call_status_text]
            route_info.append(f"📏 {point_data.get('distance_from_previous', 0):.1f} км")
            route_info.append(f"⏱️ {point_data.get('time_from_previous', 0):.0f} мин")
            order_info.append(" | ".join(route_info))

            # Ссылки на карты (компактно)
            if order.latitude and order.longitude and prev_latlon:
                links = maps_service.build_route_links(
                    prev_latlon[0],
                    prev_latlon[1],
                    order.latitude,
                    order.longitude,
                    prev_gid,
                    order.gis_id
                )
                point_links = maps_service.build_point_links(order.latitude, order.longitude, order.gis_id)

                order_info.append(
                    "🔗 <a href=\"{dg}\">Маршрут 2ГИС</a> | <a href=\"{ya}\">Яндекс</a> | "
                    "<a href=\"{pdg}\">Точка 2ГИС</a> | <a href=\"{pya}\">Яндекс</a>".format(
                        dg=links["2gis"],
                        ya=links["yandex"],
                        pdg=point_links["2gis"],
                        pya=point_links["yandex"]
                    )
                )

                # Обновляем prev_latlon для следующей точки
                prev_latlon = (order.latitude, order.longitude)
                prev_gid = order.gis_id

            # Комментарий (если есть)
            if order.comment:
                order_info.append(f"💬 {order.comment}")
            
            route_summary.append({
                "text": "\n".join(order_info),
                "order_number": order.order_number
            })
        
        return route_summary
    
    # ==================== ПОКАЗ МАРШРУТА И ЗВОНКОВ ====================
    
    def handle_show_route(self, message):
        """Показать оптимизированный маршрут"""
        user_id = message.from_user.id
        today = date.today()
        
        # Загружаем из БД
        route_data = self.parent.db_service.get_route_data(user_id, today)
        if not route_data:
            self.bot.reply_to(message, "❌ Маршрут не оптимизирован. Используйте кнопку ▶️ Оптимизировать", reply_markup=self.parent._route_menu_markup())
            return
        
        route_points_data = route_data.get('route_points_data', [])
        route_order = route_data.get('route_order', [])
        
        if not route_points_data or not route_order:
            self.bot.reply_to(message, "❌ Маршрут не оптимизирован. Используйте кнопку ▶️ Оптимизировать", reply_markup=self.parent._route_menu_markup())
            return
        
        # Загружаем заказы из БД
        orders_data = self.parent.db_service.get_today_orders(user_id)
        
        # Фильтруем только активные (не доставленные) заказы
        active_orders_data = [od for od in orders_data if od.get('status', 'pending') != 'delivered']
        orders_dict = {od.get('order_number'): od for od in active_orders_data if od.get('order_number')}
        
        # Фильтруем route_points_data, оставляя только активные заказы
        active_order_numbers = set(orders_dict.keys())
        active_route_points_data = [p for p in route_points_data if p.get('order_number') in active_order_numbers]
        
        if not active_route_points_data:
            self.bot.reply_to(message, "✅ Все заказы доставлены", reply_markup=self.parent._route_menu_markup())
            return
        
        # Загружаем точку старта
        start_location_data = self.parent.db_service.get_start_location(user_id, today) or {}
        
        # Форматируем маршрут только для активных заказов
        maps_service = MapsService()
        route_summary = self._format_route_summary(user_id, active_route_points_data, orders_dict, start_location_data, maps_service)
        
        if not route_summary:
            self.bot.reply_to(message, "❌ Не удалось сформировать маршрут", reply_markup=self.parent._route_menu_markup())
            return
        
        # Отправляем маршрут по частям (по 3 заказа в сообщении) - БЕЗ кнопок
        text_header = "<b>🗺️ Маршрут доставки</b>\n\n"
        
        # Первое сообщение с заголовком и первыми заказами
        first_chunk = text_header + "\n\n".join(item["text"] for item in route_summary[:3])
        self.bot.reply_to(message, first_chunk, parse_mode='HTML', reply_markup=self.parent._route_menu_markup(), disable_web_page_preview=True)
        
        # Остальные заказы по 5 в сообщении
        for i in range(3, len(route_summary), 5):
            chunk = "\n\n".join(item["text"] for item in route_summary[i:i+5])
            self.bot.send_message(message.chat.id, chunk, parse_mode='HTML', disable_web_page_preview=True)
    
    def handle_show_calls(self, message):
        """Показать график звонков"""
        user_id = message.from_user.id
        today = date.today()
        
        # Загружаем из БД
        route_data = self.parent.db_service.get_route_data(user_id, today)
        if not route_data:
            self.bot.reply_to(message, "❌ Маршрут не оптимизирован. Используйте кнопку ▶️ Оптимизировать", reply_markup=self.parent._route_menu_markup())
            return
        
        call_schedule = route_data.get('call_schedule', [])
        
        if not call_schedule:
            self.bot.reply_to(message, "❌ График звонков не найден", reply_markup=self.parent._route_menu_markup())
            return
        
        # Формируем текст с графиком звонков
        text = "<b>📞 График звонков</b>\n\n"
        
        for i, call_data in enumerate(call_schedule, 1):
            order_number = call_data.get('order_number', 'N/A')
            call_time = datetime.fromisoformat(call_data['call_time'])
            arrival_time = datetime.fromisoformat(call_data['arrival_time'])
            phone = call_data.get('phone', 'Не указан')
            customer_name = call_data.get('customer_name', '')
            
            # Проверяем статус звонка
            call_status = "⏰"
            try:
                with get_db_session() as session:
                    status_obj = session.query(CallStatusDB).filter(
                        CallStatusDB.order_number == order_number,
                        CallStatusDB.call_date == today
                    ).first()
                    if status_obj:
                        if status_obj.status == "confirmed":
                            call_status = "✅"
                        elif status_obj.status == "failed":
                            call_status = "🔴"
            except Exception as e:
                logger.debug(f"Ошибка получения статуса звонка: {e}")
            
            text += f"{i}. {call_status} <b>№{order_number}</b>"
            if customer_name:
                text += f" ({customer_name})"
            text += f"\n   📞 {phone}\n"
            text += f"   🕐 Звонок: {call_time.strftime('%H:%M')}\n"
            text += f"   🚗 Прибытие: {arrival_time.strftime('%H:%M')}\n\n"
        
        # Отправляем по частям если слишком длинное
        if len(text) > 4096:
            for i in range(0, len(text), 4000):
                chunk = text[i:i + 4000]
                if i == 0:
                    self.bot.reply_to(message, chunk, parse_mode='HTML', reply_markup=self.parent._route_menu_markup())
                else:
                    self.bot.send_message(message.chat.id, chunk, parse_mode='HTML')
        else:
            self.bot.reply_to(message, text, parse_mode='HTML', reply_markup=self.parent._route_menu_markup())
    
    # ==================== ПЕРЕСЧЕТ БЕЗ РУЧНЫХ ВРЕМЕН ====================
    
    def handle_recalculate_without_manual_confirm(self, call):
        """Запрос подтверждения пересчета без ручных времен"""
        user_id = call.from_user.id
        today = date.today()
        
        try:
            # Проверяем количество ручных времен
            manual_times_list = []
            manual_count = 0
            with get_db_session() as session:
                from sqlalchemy import and_
                manual_calls = session.query(CallStatusDB).filter(
                    and_(
                        CallStatusDB.user_id == user_id,
                        CallStatusDB.call_date == today,
                        CallStatusDB.is_manual_arrival == True,
                        CallStatusDB.manual_arrival_time.isnot(None)
                    )
                ).all()
                
                # Извлекаем значения ДО закрытия сессии
                manual_count = len(manual_calls)
                for cs in manual_calls[:5]:
                    if cs.manual_arrival_time:
                        manual_times_list.append(cs.manual_arrival_time.strftime("%H:%M"))
            
            if not manual_times_list:
                self.bot.answer_callback_query(call.id, "ℹ️ Ручные времена не найдены")
                return
            
            manual_times_text = ", ".join(manual_times_list)
            if manual_count > 5:
                manual_times_text += f" и еще {manual_count - 5}"
            
            # Создаем клавиатуру с подтверждением
            from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
            markup = InlineKeyboardMarkup()
            markup.add(InlineKeyboardButton(
                "✅ Да, пересчитать",
                callback_data="recalculate_without_manual_yes"
            ))
            markup.add(InlineKeyboardButton(
                "❌ Нет, отменить",
                callback_data="recalculate_without_manual_no"
            ))
            
            confirm_text = (
                "⚠️ <b>Подтверждение пересчета</b>\n\n"
                f"Найдено <b>{manual_count}</b> заказ(ов) с ручными временами прибытия.\n"
                f"Времена: {manual_times_text}\n\n"
                "При пересчете:\n"
                "• Ручные времена будут перенесены в комментарии заказов\n"
                "• Маршрут будет пересчитан автоматически\n"
                "• Ручные времена больше не будут учитываться при оптимизации\n\n"
                "<b>Вы уверены, что хотите пересчитать маршрут?</b>"
            )
            
            self.bot.edit_message_text(
                confirm_text,
                call.message.chat.id,
                call.message.message_id,
                parse_mode='HTML',
                reply_markup=markup
            )
            
        except Exception as e:
            logger.error(f"Ошибка при запросе подтверждения: {e}", exc_info=True)
            self.bot.answer_callback_query(call.id, f"❌ Ошибка: {str(e)}")
    
    def handle_recalculate_without_manual(self, call):
        """Пересчет маршрута без учета ручных времен (перенос в комментарии)"""
        # Явно импортируем для избежания проблем с областью видимости
        from src.database.connection import get_db_session
        
        user_id = call.from_user.id
        today = date.today()
        
        try:
            self.bot.answer_callback_query(call.id, "🔄 Пересчитываю маршрут...")
            
            # Получаем все заказы с ручными временами
            with get_db_session() as session:
                from sqlalchemy import and_
                from src.models.order import OrderDB
                
                # Находим все call_status с ручными временами (прибытия или звонка)
                from sqlalchemy import or_
                manual_statuses = session.query(CallStatusDB).filter(
                    and_(
                        CallStatusDB.user_id == user_id,
                        CallStatusDB.call_date == today,
                        or_(
                            and_(
                                CallStatusDB.is_manual_arrival == True,
                                CallStatusDB.manual_arrival_time.isnot(None)
                            ),
                            and_(
                                CallStatusDB.is_manual_call == True,
                                CallStatusDB.call_time.isnot(None)
                            )
                        )
                    )
                ).all()
                
                if not manual_statuses:
                    self.bot.edit_message_text(
                        "ℹ️ Ручные времена не найдены",
                        call.message.chat.id,
                        call.message.message_id
                    )
                    return
                
                # Переносим ручные времена в комментарии и удаляем ручные времена
                moved_count = 0
                for call_status in manual_statuses:
                    order = session.query(OrderDB).filter(
                        and_(
                            OrderDB.user_id == user_id,
                            OrderDB.order_date == today,
                            OrderDB.order_number == call_status.order_number
                        )
                    ).first()
                    
                    if order:
                        # Формируем комментарий с ручными временами
                        comment_parts_to_add = []
                        
                        # Добавляем ручное время прибытия, если есть и еще не в комментарии
                        if call_status.manual_arrival_time:
                            manual_arrival_str = call_status.manual_arrival_time.strftime("%H:%M")
                            arrival_part = f"[Ручное время: {manual_arrival_str}]"
                            if not order.comment or arrival_part not in order.comment:
                                comment_parts_to_add.append(arrival_part)
                        
                        # Добавляем ручное время звонка, если есть и еще не в комментарии
                        if call_status.is_manual_call and call_status.call_time:
                            manual_call_str = call_status.call_time.strftime("%H:%M")
                            call_part = f"[Ручный звонок: {manual_call_str}]"
                            if not order.comment or call_part not in order.comment:
                                comment_parts_to_add.append(call_part)
                        
                        # Добавляем новые части в комментарий
                        if comment_parts_to_add:
                            comment_prefix = " ".join(comment_parts_to_add) + " "
                            if order.comment:
                                order.comment = comment_prefix + order.comment
                            else:
                                order.comment = comment_prefix
                        
                        # Удаляем ручное время прибытия из call_status
                        if call_status.is_manual_arrival:
                            call_status.is_manual_arrival = False
                            call_status.manual_arrival_time = None
                        # Оставляем arrival_time как есть (это расчетное время)
                        
                        # Сбрасываем флаг ручного времени звонка для этого же заказа
                        # чтобы оно пересчиталось автоматически от нового времени прибытия
                        # ВАЖНО: call_time будет обновлен при оптимизации через create_call_status,
                        # но нужно явно сбросить флаг, чтобы create_call_status знал, что можно обновлять
                        if call_status.is_manual_call:
                            call_status.is_manual_call = False
                            # Временно устанавливаем call_time в None невозможно (NOT NULL constraint),
                            # поэтому оставляем старое значение - оно будет перезаписано при оптимизации
                        
                        moved_count += 1
                
                session.commit()
                logger.info(f"✅ Перенесено {moved_count} ручных времен в комментарии и удалены ручные времена звонков")
            
            # Удаляем сообщение и запускаем оптимизацию заново
            # (теперь без ручных времен, так как мы их удалили из call_status)
            try:
                self.bot.delete_message(call.message.chat.id, call.message.message_id)
            except Exception as e:
                logger.warning(f"Не удалось удалить сообщение: {e}")
            
            # Создаем фиктивное сообщение для вызова handle_optimize_route
            # Нужно отправить новое сообщение, чтобы получить message_id для reply_to
            status_msg = self.bot.send_message(
                call.message.chat.id,
                "🔄 <b>Начинаю оптимизацию маршрута...</b>\n\n⏳ Загружаю данные...",
                parse_mode='HTML'
            )
            
            # Создаем фиктивное сообщение с message_id для совместимости
            class FakeMessage:
                def __init__(self, chat_id, user, message_id):
                    self.chat = type('obj', (object,), {'id': chat_id})()
                    self.from_user = user
                    self.message_id = message_id
            
            fake_message = FakeMessage(call.message.chat.id, call.from_user, status_msg.message_id)
            
            # Запускаем оптимизацию (теперь без ручных времен)
            # OR-Tools должен найти решение, или будет использован fallback
            self.handle_optimize_route(fake_message)
            
        except Exception as e:
            logger.error(f"Ошибка при пересчете без ручных времен: {e}", exc_info=True)
            self.bot.edit_message_text(
                f"❌ <b>Ошибка пересчета</b>\n\n{str(e)}",
                call.message.chat.id,
                call.message.message_id,
                parse_mode='HTML'
            )
    
    # ==================== СБРОС ДНЯ ====================
    
    def handle_reset_day(self, message):
        """Обработчик кнопки 'Сбросить текущий день'"""
        user_id = message.from_user.id
        
        # Создаем inline клавиатуру с подтверждением
        from telebot import types
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("✅ Да, сбросить", callback_data="reset_day_confirm"))
        markup.add(types.InlineKeyboardButton("❌ Отмена", callback_data="reset_day_cancel"))
        
        self.bot.send_message(
            message.chat.id,
            "⚠️ <b>Внимание!</b>\n\n"
            "Вы уверены, что хотите сбросить все данные за сегодня?\n\n"
            "Это действие удалит:\n"
            "• Все заказы\n"
            "• Маршрут\n"
            "• График звонков\n"
            "• Точку старта\n\n"
            "<b>Это действие нельзя отменить!</b>",
            parse_mode='HTML',
            reply_markup=markup
        )
    
    def handle_reset_day_confirm(self, call):
        """Подтверждение сброса дня"""
        user_id = call.from_user.id
        today = date.today()
        
        try:
            # Удаляем все данные за сегодня
            self.parent.db_service.delete_all_data_by_date(user_id, today)
            
            # Очищаем состояние пользователя
            self.parent.clear_user_state(user_id)
            
            # Останавливаем мониторинг пробок если был запущен
            self.parent.traffic_monitor.stop_monitoring(user_id)
            
            self.bot.answer_callback_query(call.id, "✅ Данные за сегодня удалены")
            self.bot.edit_message_text(
                "✅ <b>Данные за сегодня успешно удалены</b>\n\n"
                "Вы можете начать новый день!",
                call.message.chat.id,
                call.message.message_id,
                parse_mode='HTML'
            )
            
            logger.info(f"Пользователь {user_id} сбросил данные за {today}")
        
        except Exception as e:
            logger.error(f"Ошибка сброса данных: {e}", exc_info=True)
            self.bot.answer_callback_query(call.id, f"❌ Ошибка: {str(e)}")
            self.bot.edit_message_text(
                f"❌ Ошибка при сбросе данных: {str(e)}",
                call.message.chat.id,
                call.message.message_id
            )

    # ==================== ТЕКУЩИЙ ЗАКАЗ ====================
    
    def handle_current_order(self, message):
        """Показать текущий (ближайший) заказ с навигацией"""
        user_id = message.from_user.id
        today = date.today()
        
        # Загружаем маршрут из БД
        route_data = self.parent.db_service.get_route_data(user_id, today)
        if not route_data:
            self.bot.reply_to(message, "❌ Маршрут не оптимизирован. Используйте кнопку ▶️ Оптимизировать", reply_markup=self.parent._route_menu_markup())
            return
        
        route_points_data = route_data.get('route_points_data', [])
        if not route_points_data:
            self.bot.reply_to(message, "❌ Маршрут не оптимизирован. Используйте кнопку ▶️ Оптимизировать", reply_markup=self.parent._route_menu_markup())
            return
        
        # Сортируем по времени прибытия и берем первый (ближайший) заказ
        try:
            sorted_points = sorted(
                route_points_data,
                key=lambda pd: datetime.fromisoformat(pd.get("estimated_arrival"))
            )
        except Exception as e:
            logger.error(f"Ошибка сортировки точек маршрута: {e}", exc_info=True)
            sorted_points = route_points_data
        
        # Фильтруем только активные (не доставленные) заказы
        orders_data = self.parent.db_service.get_today_orders(user_id)
        active_order_numbers = {od.get('order_number') for od in orders_data if od.get('status', 'pending') != 'delivered'}
        
        active_points = [p for p in sorted_points if p.get('order_number') in active_order_numbers]
        
        if not active_points:
            self.bot.reply_to(message, "✅ Все заказы доставлены", reply_markup=self.parent._main_menu_markup(user_id))
            return
        
        # Показываем первый заказ (индекс 0) - отправляем новое сообщение
        self._show_order_at_index(message.chat.id, user_id, active_points, 0, None)
    
    def handle_show_order_by_index(self, call, index: int):
        """Показать заказ по индексу (для навигации)"""
        user_id = call.from_user.id
        today = date.today()
        
        # Загружаем маршрут из БД
        route_data = self.parent.db_service.get_route_data(user_id, today)
        if not route_data:
            self.bot.answer_callback_query(call.id, "❌ Маршрут не найден")
            return
        
        route_points_data = route_data.get('route_points_data', [])
        if not route_points_data:
            self.bot.answer_callback_query(call.id, "❌ Маршрут пуст")
            return
        
        # Сортируем и фильтруем активные заказы
        try:
            sorted_points = sorted(
                route_points_data,
                key=lambda pd: datetime.fromisoformat(pd.get("estimated_arrival"))
            )
        except Exception as e:
            logger.error(f"Ошибка сортировки точек маршрута: {e}", exc_info=True)
            sorted_points = route_points_data
        
        orders_data = self.parent.db_service.get_today_orders(user_id)
        active_order_numbers = {od.get('order_number') for od in orders_data if od.get('status', 'pending') != 'delivered'}
        active_points = [p for p in sorted_points if p.get('order_number') in active_order_numbers]
        
        if not active_points:
            self.bot.answer_callback_query(call.id, "✅ Все заказы доставлены")
            return
        
        # Проверяем границы
        if index < 0:
            index = 0
        elif index >= len(active_points):
            index = len(active_points) - 1
        
        self.bot.answer_callback_query(call.id)
        self._show_order_at_index(call.message.chat.id, user_id, active_points, index, call.message.message_id)
    
    def _show_order_at_index(self, chat_id: int, user_id: int, active_points: List[Dict], index: int, message_id: int = None):
        """Показать заказ по индексу с навигацией"""
        today = date.today()
        
        if index < 0 or index >= len(active_points):
            return
        
        point_data = active_points[index]
        order_number = point_data.get('order_number')
        if not order_number:
            return
        
        # Загружаем данные заказа
        orders_data = self.parent.db_service.get_today_orders(user_id)
        orders_dict = {od.get('order_number'): od for od in orders_data if od.get('order_number')}
        order_data = orders_dict.get(order_number)
        
        if not order_data:
            return
        
        # Определяем координаты предыдущей точки для построения маршрута
        # Если это не первый заказ, используем координаты предыдущего заказа
        prev_latlon = None
        prev_gid = None
        
        if index > 0:
            # Берем предыдущий заказ из списка
            prev_point_data = active_points[index - 1]
            prev_order_number = prev_point_data.get('order_number')
            if prev_order_number:
                prev_order_data = orders_dict.get(prev_order_number)
                if prev_order_data and prev_order_data.get('latitude') and prev_order_data.get('longitude'):
                    prev_latlon = (prev_order_data['latitude'], prev_order_data['longitude'])
                    prev_gid = prev_order_data.get('gis_id')
        
        # Если предыдущего заказа нет, используем стартовую точку
        if prev_latlon is None:
            start_location_data = self.parent.db_service.get_start_location(user_id, today) or {}
            if start_location_data:
                if start_location_data.get('location_type') == 'geo':
                    prev_latlon = (start_location_data.get('latitude'), start_location_data.get('longitude'))
                elif start_location_data.get('latitude') and start_location_data.get('longitude'):
                    prev_latlon = (start_location_data.get('latitude'), start_location_data.get('longitude'))
        else:
            start_location_data = {}  # Не нужна стартовая точка, если есть предыдущий заказ
        
        # Получаем номер заказа из point_data
        order_number = point_data.get('order_number')
        if not order_number:
            logger.warning(f"Не найден номер заказа в point_data для индекса {index}")
            return
        
        # Форматируем один заказ с правильным порядковым номером (index + 1, так как нумерация с 1)
        maps_service = MapsService()
        route_summary = self._format_route_summary(user_id, [point_data], orders_dict, start_location_data, maps_service, start_index=index + 1, prev_latlon=prev_latlon, prev_gid=prev_gid)
        
        if not route_summary:
            return
        
        order_text = route_summary[0]["text"]
        
        # Создаем клавиатуру навигации
        from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
        markup = InlineKeyboardMarkup()
        
        # Кнопки навигации
        nav_buttons = []
        if index > 0:
            nav_buttons.append(InlineKeyboardButton("⬅️ Предыдущий", callback_data=f"current_order_prev_{index}"))
        if index < len(active_points) - 1:
            nav_buttons.append(InlineKeyboardButton("➡️ Следующий", callback_data=f"current_order_next_{index}"))
        
        if nav_buttons:
            markup.row(*nav_buttons)
        
        # Кнопки действий
        action_buttons = []
        action_buttons.append(InlineKeyboardButton("✏️ Отредактировать", callback_data=f"route_edit_order_{order_number}"))
        action_buttons.append(InlineKeyboardButton("✅ Доставлен", callback_data=f"route_delivered_{order_number}"))
        markup.row(*action_buttons)
        
        # Отправляем или редактируем сообщение
        if message_id:
            try:
                self.bot.edit_message_text(
                    order_text,
                    chat_id,
                    message_id,
                    parse_mode='HTML',
                    reply_markup=markup,
                    disable_web_page_preview=True
                )
            except Exception as e:
                logger.warning(f"Не удалось отредактировать сообщение: {e}")
                # Если не удалось отредактировать, отправляем новое
                self.bot.send_message(
                    chat_id,
                    order_text,
                    parse_mode='HTML',
                    reply_markup=markup,
                    disable_web_page_preview=True
                )
        else:
            self.bot.send_message(
                chat_id,
                order_text,
                parse_mode='HTML',
                reply_markup=markup,
                disable_web_page_preview=True
            )
    
    # ==================== ОТМЕТКА ДОСТАВКИ ЗАКАЗА ====================

    def handle_mark_order_delivered(self, call):
        """Обработчик нажатия на кнопку 'Доставлен' в списке маршрута."""
        user_id = call.from_user.id
        today = date.today()

        try:
            data = call.data or ""
            # Формат callback_data: route_delivered_<order_number>
            prefix = "route_delivered_"
            if not data.startswith(prefix):
                self.bot.answer_callback_query(call.id, "❌ Некорректные данные", show_alert=True)
                return

            order_number = data[len(prefix):]
            if not order_number:
                self.bot.answer_callback_query(call.id, "❌ Не указан номер заказа", show_alert=True)
                return

            # Загружаем маршрут ДО обновления статуса, чтобы найти индекс текущего заказа
            route_data = self.parent.db_service.get_route_data(user_id, today)
            if not route_data:
                # Если маршрута нет, просто обновляем статус
                updated = self.parent.db_service.update_order(
                    user_id,
                    order_number,
                    {"status": "delivered"},
                    today,
                )
                if updated:
                    self.bot.answer_callback_query(call.id, f"✅ Заказ №{order_number} отмечен доставленным")
                else:
                    self.bot.answer_callback_query(call.id, f"❌ Заказ №{order_number} не найден", show_alert=True)
                return
            
            route_points_data = route_data.get('route_points_data', [])
            try:
                sorted_points = sorted(
                    route_points_data,
                    key=lambda pd: datetime.fromisoformat(pd.get("estimated_arrival"))
                )
            except Exception:
                sorted_points = route_points_data
            
            # Находим индекс текущего заказа ДО обновления статуса
            orders_data_before = self.parent.db_service.get_today_orders(user_id)
            active_order_numbers_before = {od.get('order_number') for od in orders_data_before if od.get('status', 'pending') != 'delivered'}
            active_points_before = [p for p in sorted_points if p.get('order_number') in active_order_numbers_before]
            current_index = next((i for i, p in enumerate(active_points_before) if p.get('order_number') == order_number), None)
            
            # Обновляем статус заказа в БД
            updated = self.parent.db_service.update_order(
                user_id,
                order_number,
                {"status": "delivered"},
                today,
            )

            if not updated:
                self.bot.answer_callback_query(
                    call.id,
                    f"❌ Заказ №{order_number} не найден за сегодня",
                    show_alert=True
                )
                return

            # Отвечаем на callback
            self.bot.answer_callback_query(call.id, f"✅ Заказ №{order_number} отмечен доставленным")
            
            # Загружаем активные заказы ПОСЛЕ обновления статуса
            orders_data_after = self.parent.db_service.get_today_orders(user_id)
            active_order_numbers_after = {od.get('order_number') for od in orders_data_after if od.get('status', 'pending') != 'delivered'}
            active_points_after = [p for p in sorted_points if p.get('order_number') in active_order_numbers_after]
            
            if active_points_after:
                # Определяем, какой заказ показать
                if current_index is not None:
                    # Если был не последний - показываем следующий (который теперь на том же индексе)
                    if current_index < len(active_points_after):
                        next_index = current_index
                    else:
                        # Если был последний - показываем предыдущий
                        next_index = len(active_points_after) - 1
                else:
                    # Если не нашли индекс (не должно случиться), показываем первый
                    next_index = 0
                
                self._show_order_at_index(call.message.chat.id, user_id, active_points_after, next_index, call.message.message_id)
            else:
                # Больше нет активных заказов
                try:
                    # Удаляем старое сообщение и отправляем новое с клавиатурой
                    # (на случай, если исходное сообщение не имело reply_markup)
                    try:
                        self.bot.delete_message(call.message.chat.id, call.message.message_id)
                    except:
                        pass  # Игнорируем ошибку, если сообщение уже удалено
                    
                    self.bot.send_message(
                        call.message.chat.id,
                        "✅ Все заказы доставлены",
                        parse_mode='HTML',
                        reply_markup=self.parent._main_menu_markup(user_id)
                    )
                except Exception as edit_error:
                    logger.error(f"Ошибка при обновлении сообщения после доставки всех заказов: {edit_error}")
                    # Пытаемся хотя бы ответить на callback
                    try:
                        self.bot.answer_callback_query(call.id, "✅ Все заказы доставлены")
                    except:
                        pass

        except Exception as e:
            logger.error(f"Ошибка при отметке заказа доставленным: {e}", exc_info=True)
            try:
                self.bot.answer_callback_query(call.id, f"❌ Ошибка: {str(e)}", show_alert=True)
            except Exception:
                # Игнорируем вторичную ошибку ответа
                pass
    
    def handle_edit_order_from_route(self, call):
        """Обработчик нажатия на кнопку 'Отредактировать' в текущем заказе"""
        user_id = call.from_user.id
        
        try:
            data = call.data or ""
            # Формат callback_data: route_edit_order_<order_number>
            prefix = "route_edit_order_"
            if not data.startswith(prefix):
                self.bot.answer_callback_query(call.id, "❌ Некорректные данные", show_alert=True)
                return
            
            order_number = data[len(prefix):]
            if not order_number:
                self.bot.answer_callback_query(call.id, "❌ Не указан номер заказа", show_alert=True)
                return
            
            # Отвечаем на callback
            self.bot.answer_callback_query(call.id, "✏️ Открываю редактирование...")
            
            # Вызываем метод из order_handlers для показа деталей заказа и начала редактирования
            self.parent.orders.show_order_details(user_id, order_number, call.message.chat.id)
            
        except Exception as e:
            logger.error(f"Ошибка при открытии редактирования заказа: {e}", exc_info=True)
            try:
                self.bot.answer_callback_query(call.id, f"❌ Ошибка: {str(e)}", show_alert=True)
            except Exception:
                pass
