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
        elif callback_data == "confirm_start_address":
            self.handle_confirm_start_address(call)
    
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
        self.parent.update_user_state(user_id, 'waiting_for_start_location', {'type': 'geo'})
    
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
        self.parent.update_user_state(user_id, 'waiting_for_start_address', {})
    
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
        self.parent.update_user_state(user_id, 'waiting_for_start_time', {})
    
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
                    reply_markup=self.parent._main_menu_markup()
                )
                self.parent.clear_user_state(message.from_user.id)
        
        except Exception as e:
            logger.error(f"Ошибка обработки состояния маршрута: {e}", exc_info=True)
            self.bot.reply_to(
                message,
                f"❌ Ошибка обработки: {str(e)}",
                reply_markup=self.parent._main_menu_markup()
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
            
            self.parent.update_user_state(user_id, 'waiting_for_start_time', {})
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
        
        # Сохраняем в БД с координатами
        self.parent.db_service.save_start_location(
            user_id, 'address', address, lat, lon, gid, today
        )
        
        # Спрашиваем про время старта
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
        markup.row("⬅️ Главное меню")
        
        self.bot.send_message(
            message.chat.id,
            f"✅ Точка старта сохранена: {address}\n"
            f"📍 Координаты: ({lat:.6f}, {lon:.6f})\n\n"
            "⏰ Введите время старта (например, 09:00):",
            reply_markup=markup
        )
        
        self.parent.update_user_state(user_id, 'waiting_for_start_time', {})
    
    def handle_confirm_start_address(self, call):
        """Подтверждение адреса точки старта через callback"""
        user_id = call.from_user.id
        today = date.today()
        
        state_data = self.parent.get_user_state(user_id)
        pending_location = state_data.get('pending_location')
        
        if not pending_location:
            self.bot.answer_callback_query(call.id, "❌ Данные не найдены")
            return
        
        # Сохраняем в БД
        self.parent.db_service.save_start_location(
            user_id,
            'address',
            pending_location['address'],
            pending_location['lat'],
            pending_location['lon'],
            pending_location.get('gid'),
            today
        )
        
        self.bot.answer_callback_query(call.id, "✅ Адрес сохранен")
        self.bot.edit_message_text(
            f"✅ Точка старта сохранена: {pending_location['address']}\n\n"
            "⏰ Введите время старта (например, 09:00):",
            call.message.chat.id,
            call.message.message_id
        )
        
        self.parent.update_user_state(user_id, 'waiting_for_start_time', {})
    
    def process_start_time(self, message):
        """Обработка времени старта"""
        user_id = message.from_user.id
        today = date.today()
        
        if message.text == "⬅️ Главное меню":
            self.parent.clear_user_state(user_id)
            self.bot.send_message(
                message.chat.id,
                "Главное меню",
                reply_markup=self.parent._main_menu_markup()
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
            reply_markup=self.parent._main_menu_markup()
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
                self.bot.reply_to(message, "❌ Нет добавленных заказов. Добавьте их через кнопку ➕ Добавить заказы", reply_markup=self.parent._orders_menu_markup())
                return

            # Фильтруем доставленные заказы
            active_orders_data = [od for od in orders_data if od.get('status', 'pending') != 'delivered']
            
            if not active_orders_data:
                self.bot.reply_to(message, "❌ Нет активных заказов для оптимизации. Все заказы доставлены.", reply_markup=self.parent._orders_menu_markup())
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
                    lat, lon, gid = maps_service.geocode_address_sync(order.address)
                    if lat and lon:
                        order.latitude = lat
                        order.longitude = lon
                        order.gis_id = gid

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
            
            route_optimizer = RouteOptimizer(maps_service)
            optimized_route = route_optimizer.optimize_route_sync(
                orders, start_location_coords, start_datetime, user_id=user_id
            )
            
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

                # Проверяем, указано ли ручное время звонка
                if order.manual_call_time:
                    # Используем ручное время звонка
                    call_time = order.manual_call_time
                    logger.info(f"📞⏰ Используется ручное время звонка для заказа {order.order_number}: {call_time.strftime('%H:%M')}")
                else:
                    # Calculate call time (используем настройку пользователя вместо жестко заданных 40 минут)
                    call_time = point.estimated_arrival - timedelta(minutes=user_settings.call_advance_minutes)

                    # If order has time window, ensure call is not too early
                    if order.delivery_time_start:
                        today = point.estimated_arrival.date()
                        window_start = datetime.combine(today, order.delivery_time_start)
                        earliest_call = window_start - timedelta(minutes=user_settings.call_advance_minutes)

                        if call_time < earliest_call:
                            call_time = earliest_call

                # Используем ручное время прибытия если указано
                actual_arrival_time = order.manual_arrival_time if order.manual_arrival_time else point.estimated_arrival
                if order.manual_arrival_time:
                    logger.info(f"⏰ Используется ручное время прибытия для заказа {order.order_number}: {actual_arrival_time.strftime('%H:%M')}")
                
                # Сохраняем структурированные данные для каждой точки маршрута
                route_point_data = {
                    "order_number": order.order_number or str(order.id),
                    "estimated_arrival": actual_arrival_time.isoformat(),
                    "distance_from_previous": point.distance_from_previous,
                    "time_from_previous": point.time_from_previous,
                    "call_time": call_time.isoformat(),
                    "manual_arrival_time": order.manual_arrival_time.isoformat() if order.manual_arrival_time else None,
                    "manual_call_time": order.manual_call_time.isoformat() if order.manual_call_time else None
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
                
                # Создаем запись о звонке для уведомлений (если есть телефон)
                # НЕ перезаписываем подтвержденные звонки при повторной оптимизации
                if order.phone and order.order_number:
                    if order.order_number in confirmed_order_numbers:
                        logger.info(f"⏭️ Пропускаем создание call_status для заказа {order.order_number} - звонок уже подтвержден")
                    else:
                        logger.debug(f"Создание записи о звонке: заказ {order.order_number}, время звонка {call_time.strftime('%Y-%m-%d %H:%M:%S')}, прибытие {point.estimated_arrival.strftime('%Y-%m-%d %H:%M:%S')}")
                        self.parent.call_notifier.create_call_status(
                            user_id,
                            order.order_number,
                            call_time,
                            order.phone,
                            order.customer_name,
                            today
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
                f"<b>Маршрут:</b>\n" + "\n\n".join(formatted_route[:3])
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
                    reply_markup=self.parent._route_menu_markup(),
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
                    self.bot.edit_message_text(
                        f"❌ <b>Ошибка оптимизации</b>\n\n{str(e)}",
                        message.chat.id,
                        status_msg.message_id,
                        parse_mode='HTML',
                        reply_markup=self.parent._route_menu_markup()
                    )
                else:
                    # Если статусное сообщение не было создано, отправляем новое
                    self.bot.reply_to(message, f"❌ Ошибка оптимизации: {str(e)}", reply_markup=self.parent._route_menu_markup())
            except Exception as edit_error:
                logger.warning(f"Ошибка при редактировании сообщения: {edit_error}")
                # Если не удалось отредактировать, отправляем новое сообщение
                try:
                    if 'status_msg' in locals():
                        self.bot.delete_message(message.chat.id, status_msg.message_id)
                except Exception as e:
                    logger.warning(f"Не удалось удалить сообщение: {e}")
                self.bot.reply_to(message, f"❌ Ошибка оптимизации: {str(e)}", reply_markup=self.parent._route_menu_markup())
    
    # ==================== ВСПОМОГАТЕЛЬНЫЕ МЕТОДЫ ====================
    
    def _format_route_summary(self, user_id: int, route_points_data: List[Dict], orders_dict: Dict[str, Dict], 
                              start_location_data: Dict, maps_service) -> List[str]:
        """Форматирует маршрут из структурированных данных"""
        route_summary = []
        
        # Получаем координаты старта
        prev_latlon = None
        prev_gid = None
        if start_location_data:
            if start_location_data.get('location_type') == 'geo':
                prev_latlon = (start_location_data.get('latitude'), start_location_data.get('longitude'))
            elif start_location_data.get('latitude') and start_location_data.get('longitude'):
                prev_latlon = (start_location_data.get('latitude'), start_location_data.get('longitude'))
        
        for i, point_data in enumerate(route_points_data, 1):
            order_number = point_data.get('order_number')
            if not order_number:
                continue
                
            order_data = orders_dict.get(order_number)
            if not order_data:
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
            order_info.append(f"📍 {order.address}")
            
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
            
            route_summary.append("\n".join(order_info))
        
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
        orders_dict = {od.get('order_number'): od for od in orders_data if od.get('order_number')}
        
        # Загружаем точку старта
        start_location_data = self.parent.db_service.get_start_location(user_id, today) or {}
        
        # Форматируем маршрут
        maps_service = MapsService()
        route_summary = self._format_route_summary(user_id, route_points_data, orders_dict, start_location_data, maps_service)
        
        if not route_summary:
            self.bot.reply_to(message, "❌ Не удалось сформировать маршрут", reply_markup=self.parent._route_menu_markup())
            return
        
        # Отправляем маршрут по частям (по 3 заказа в сообщении)
        text_header = "<b>🗺️ Маршрут доставки</b>\n\n"
        
        # Первое сообщение с заголовком и первыми заказами
        first_chunk = text_header + "\n\n".join(route_summary[:3])
        self.bot.reply_to(message, first_chunk, parse_mode='HTML', reply_markup=self.parent._route_menu_markup(), disable_web_page_preview=True)
        
        # Остальные заказы по 5 в сообщении
        for i in range(3, len(route_summary), 5):
            chunk = "\n\n".join(route_summary[i:i+5])
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
            self.parent.db_service.delete_today_data(user_id, today)
            
            # Очищаем состояние пользователя
            self.parent.clear_user_state(user_id)
            
            # Останавливаем мониторинг пробок если был запущен
            self.parent.traffic_monitor.stop_monitoring(user_id)
            
            self.bot.answer_callback_query(call.id, "✅ Данные за сегодня удалены")
            self.bot.edit_message_text(
                "✅ <b>Данные за сегодня успешно удалены</b>\n\n"
                "Вы можете начать новый день:",
                call.message.chat.id,
                call.message.message_id,
                parse_mode='HTML',
                reply_markup=self.parent._main_menu_markup()
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
