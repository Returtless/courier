import telebot
import logging
from typing import Dict, List
from datetime import datetime, time, timedelta, date
from src.models.order import Order
# Импортируем модели БД, чтобы они зарегистрировались
from src.models.order import OrderDB, StartLocationDB, RouteDataDB  # noqa: F401
from src.services.maps_service import MapsService
from src.services.route_optimizer import RouteOptimizer
from src.services.traffic_monitor import TrafficMonitor
from src.services.db_service import DatabaseService
from src.services.call_notifier import CallNotifier, get_local_now
from src.database.connection import Base, engine
# from src.services.llm_service import LLMService  # Пока отключено

logger = logging.getLogger(__name__)


class CourierBot:
    def __init__(self, bot: telebot.TeleBot, llm_service=None):
        self.bot = bot
        self.llm_service = llm_service
        self.traffic_monitor = TrafficMonitor(MapsService())
        self.db_service = DatabaseService()
        self.call_notifier = CallNotifier(bot, self)
        self.setup_traffic_callbacks()
        self.user_states = {}  # user_id -> state data (для временных состояний)
        # Инициализация БД (создание таблиц) - теперь только в main.py

    @staticmethod
    def _main_menu_markup():
        from telebot import types
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
        markup.row("📦 Заказы", "🗺️ Маршрут")
        markup.row("🗑️ Сбросить день")
        return markup

    @staticmethod
    def _orders_menu_markup():
        from telebot import types
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
        markup.row("➕ Добавить заказы")
        markup.row("ℹ️ Детали заказа")
        markup.row("✅ Доставленные")
        markup.row("⬅️ Главное меню")
        return markup

    @staticmethod
    def _route_menu_markup():
        from telebot import types
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
        markup.row("📋 Показать маршрут")
        markup.row("📍 Точка старта")
        markup.row("▶️ Оптимизировать")
        markup.row("📞 Звонки")
        markup.row("🚦 Мониторинг", "🛑 Стоп мониторинг")
        markup.row("⬅️ Главное меню")
        return markup

    @staticmethod
    def _add_orders_menu_markup():
        from telebot import types
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=False)
        markup.row("✅ Готово")
        markup.row("⬅️ Главное меню")
        return markup

    @staticmethod
    def _update_order_back_markup():
        from telebot import types
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
        markup.row("⬅️ Главное меню")
        return markup

    def register_handlers(self):
        """Register all message handlers"""

        @self.bot.message_handler(commands=['start'])
        def cmd_start(message):
            self.handle_start(message)

        @self.bot.message_handler(commands=['add_orders'])
        def cmd_add_orders(message):
            self.handle_add_orders(message)

        @self.bot.message_handler(commands=['set_start'])
        def cmd_set_start(message):
            self.handle_set_start(message)

        @self.bot.message_handler(commands=['optimize_route'])
        def cmd_optimize_route(message):
            self.handle_optimize_route(message)

        @self.bot.message_handler(commands=['view_route'])
        def cmd_view_route(message):
            self.handle_view_route(message)

        @self.bot.message_handler(commands=['calls'])
        def cmd_calls(message):
            self.handle_calls(message)

        @self.bot.message_handler(commands=['monitor'])
        def cmd_monitor(message):
            self.handle_monitor(message)

        @self.bot.message_handler(commands=['stop_monitor'])
        def cmd_stop_monitor(message):
            self.handle_stop_monitor(message)

        @self.bot.message_handler(commands=['traffic_status'])
        def cmd_traffic_status(message):
            self.handle_traffic_status(message)

        @self.bot.message_handler(commands=['update_order'])
        def cmd_update_order(message):
            self.handle_update_order(message)

        @self.bot.message_handler(content_types=['location'])
        def handle_location(message):
            self.handle_location_message(message)

        @self.bot.callback_query_handler(func=lambda call: True)
        def handle_callback(call):
            self.handle_callback_query(call)

        @self.bot.message_handler(func=lambda message: True)
        def handle_text(message):
            self.handle_text_message(message)

    def get_user_state(self, user_id: int) -> Dict:
        """Get user state data"""
        return self.user_states.get(user_id, {})

    def set_user_state(self, user_id: int, data: Dict):
        """Set user state data"""
        self.user_states[user_id] = data

    def update_user_state(self, user_id: int, key: str, value):
        """Update specific user state key"""
        state = self.get_user_state(user_id)
        state[key] = value
        self.set_user_state(user_id, state)

    def setup_traffic_callbacks(self):
        """Настроить callbacks для мониторинга пробок"""
        def traffic_change_callback(user_id, changes, total_time):
            # Отправить уведомление конкретному пользователю
            try:
                self.send_traffic_alert(user_id, changes, total_time)
            except Exception as e:
                logger.warning(f"Ошибка отправки уведомления пользователю {user_id}: {e}", exc_info=True)

        self.traffic_monitor.add_callback(traffic_change_callback)

    def handle_start(self, message):
        """Handle /start command"""
        text = (
            "🚚 <b>Бот для оптимизации маршрутов доставки</b>\n\n"
            "Команды:\n"
            "/add_orders - Добавить заказы для оптимизации\n"
            "/set_start - Установить точку старта\n"
            "/optimize_route - Оптимизировать маршрут\n"
            "/view_route - Просмотреть маршрут\n"
            "/calls - График звонков\n\n"
            "🚦 <b>Мониторинг пробок:</b>\n"
            "/monitor - Запустить мониторинг\n"
            "/stop_monitor - Остановить мониторинг\n"
            "/traffic_status - Статус мониторинга\n\n"
            "Выберите действие:"
        )
        self.bot.reply_to(message, text, parse_mode='HTML', reply_markup=self._main_menu_markup())

    def handle_add_orders(self, message):
        """Handle /add_orders command"""
        user_id = message.from_user.id
        self.update_user_state(user_id, 'state', 'waiting_for_orders')
        self.update_user_state(user_id, 'orders', [])

        text = (
            "📝 <b>Добавление заказов</b>\n\n"
            "Отправьте заказы в одном из форматов:\n\n"
            "📋 <b>Формат 1 (с вашими данными):</b>\n"
            "<code>Время НомерЗаказа Адрес</code>\n"
            "Пример:\n"
            "<code>10:00 - 13:00 3258104 г Санкт-Петербург, ул Манчестерская, д 3 стр 1</code>\n\n"
            "📋 <b>Формат 2 (расширенный):</b>\n"
            "<code>Имя|Телефон|Адрес|Комментарий</code>\n"
            "Пример:\n"
            "<code>Иван|+7-999-123-45-67|ул. Ленина, 10|Звонок в домофон</code>\n\n"
            "Можно вставить сразу несколько строк одним сообщением — все корректные добавятся.\n"
            "Когда закончите, нажмите кнопку <b>✅ Готово</b>"
        )
        self.bot.reply_to(message, text, parse_mode='HTML', reply_markup=self._add_orders_menu_markup())

    def handle_set_start(self, message):
        """Handle /set_start command"""
        user_id = message.from_user.id
        today = date.today()
        
        # Загружаем из БД
        start_location_data = self.db_service.get_start_location(user_id, today)
        
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
        from telebot import types
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

    def handle_optimize_route(self, message):
        """Handle /optimize_route command"""
        try:
            user_id = message.from_user.id
            today = date.today()
            
            logger.debug(f"Начало оптимизации для user_id={user_id}")
            
            # Загружаем заказы из БД
            try:
                orders_data = self.db_service.get_today_orders(user_id)
                logger.debug(f"Загружено заказов: {len(orders_data) if orders_data else 0}")
            except Exception as e:
                logger.error(f"Ошибка загрузки заказов: {e}", exc_info=True)
                self.bot.reply_to(message, f"❌ Ошибка загрузки заказов: {str(e)}", reply_markup=self._route_menu_markup())
                return
            
            if not orders_data:
                self.bot.reply_to(message, "❌ Нет добавленных заказов. Добавьте их через кнопку ➕ Добавить заказы", reply_markup=self._orders_menu_markup())
                return

            # Фильтруем доставленные заказы
            active_orders_data = [od for od in orders_data if od.get('status', 'pending') != 'delivered']
            
            if not active_orders_data:
                self.bot.reply_to(message, "❌ Нет активных заказов для оптимизации. Все заказы доставлены.", reply_markup=self._orders_menu_markup())
                return

            # Загружаем точку старта из БД
            try:
                start_location_data = self.db_service.get_start_location(user_id, today)
                logger.debug(f"Данные точки старта: {start_location_data}")
            except Exception as e:
                logger.error(f"Ошибка загрузки точки старта: {e}", exc_info=True)
                self.bot.reply_to(message, f"❌ Ошибка загрузки точки старта: {str(e)}", reply_markup=self._route_menu_markup())
                return
            
            if not start_location_data:
                self.bot.reply_to(message, "❌ Не установлена точка старта. Используйте кнопку 📍 Точка старта", reply_markup=self._route_menu_markup())
                return
            
            start_address = start_location_data.get('address')
            start_lat = start_location_data.get('latitude')
            start_lon = start_location_data.get('longitude')
            start_time_str = start_location_data.get('start_time')
            location_type = start_location_data.get('location_type')
            
            if not start_time_str:
                self.bot.reply_to(message, "❌ Не установлено время старта. Используйте кнопку 📍 Точка старта", reply_markup=self._route_menu_markup())
                return

            # Convert data back to Order objects (только активные заказы)
            orders = []
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
                    orders.append(Order(**order_dict))
                except Exception as e:
                    logger.error(f"Ошибка создания Order из данных: {e}, данные: {order_data}", exc_info=True)
                    continue
            
            if not orders:
                self.bot.reply_to(message, "❌ Не удалось обработать заказы. Проверьте данные.", reply_markup=self._route_menu_markup())
                return
            
            try:
                start_datetime = datetime.fromisoformat(start_time_str) if isinstance(start_time_str, str) else start_time_str
            except Exception as e:
                logger.error(f"Ошибка парсинга времени старта: {e}, start_time_str: {start_time_str}", exc_info=True)
                self.bot.reply_to(message, f"❌ Ошибка обработки времени старта: {str(e)}", reply_markup=self._route_menu_markup())
                return
            
            # Определяем координаты старта - используем сохраненные координаты из БД
            if start_lat and start_lon:
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
                self.db_service.save_start_location(
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
                orders, start_location_coords, start_datetime
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

            for i, point in enumerate(optimized_route.points, 1):
                order = point.order

                # Calculate call time (40 min before delivery, but not before start of delivery window)
                call_time = point.estimated_arrival - timedelta(minutes=40)

                # If order has time window, ensure call is not too early
                if order.delivery_time_start:
                    today = point.estimated_arrival.date()
                    window_start = datetime.combine(today, order.delivery_time_start)
                    earliest_call = window_start - timedelta(minutes=40)

                    if call_time < earliest_call:
                        call_time = earliest_call

                # Сохраняем структурированные данные для каждой точки маршрута
                route_point_data = {
                    "order_number": order.order_number or str(order.id),
                    "estimated_arrival": point.estimated_arrival.isoformat(),
                    "distance_from_previous": point.distance_from_previous,
                    "time_from_previous": point.time_from_previous,
                    "call_time": call_time.isoformat()
                }
                route_points_data.append(route_point_data)

                # Сохраняем структурированные данные для графика звонков
                call_data = {
                    "order_number": order.order_number or str(order.id),
                    "call_time": call_time.isoformat(),
                    "arrival_time": point.estimated_arrival.isoformat(),
                    "phone": order.phone or None,
                    "customer_name": order.customer_name or None
                }
                call_schedule.append(call_data)
                
                # Создаем запись о звонке для уведомлений (если есть телефон)
                if order.phone and order.order_number:
                    logger.debug(f"Создание записи о звонке: заказ {order.order_number}, время звонка {call_time.strftime('%Y-%m-%d %H:%M:%S')}, прибытие {point.estimated_arrival.strftime('%Y-%m-%d %H:%M:%S')}")
                    self.call_notifier.create_call_status(
                        user_id,
                        order.order_number,
                        call_time,
                        order.phone,
                        order.customer_name,
                        today
                    )

            # Сохраняем порядок заказов в маршруте
            route_order = [point.order.order_number or str(point.order.id) for point in optimized_route.points]
            
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
                        self.db_service.update_order(user_id, order.order_number, updates, today)
                    except Exception as e:
                        logger.warning(f"Не удалось обновить координаты заказа {order.order_number}: {e}")
            
            # Сохраняем структурированные данные маршрута в БД
            self.db_service.save_route_data(
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
            self.update_user_state(user_id, 'route_points_data', route_points_data)
            self.update_user_state(user_id, 'call_schedule', call_schedule)
            self.update_user_state(user_id, 'route_order', route_order)
            # Сохраняем optimized_route для мониторинга пробок
            self.update_user_state(user_id, 'optimized_route', optimized_route)
            self.update_user_state(user_id, 'optimized_orders', orders)
            start_location_tuple = None
            if start_location_data:
                if start_location_data.get('latitude') and start_location_data.get('longitude'):
                    start_location_tuple = (start_location_data['latitude'], start_location_data['longitude'])
            self.update_user_state(user_id, 'start_location', start_location_tuple)
            if start_location_data and start_location_data.get('start_time'):
                start_time_str = start_location_data['start_time']
                if isinstance(start_time_str, str):
                    start_time = datetime.fromisoformat(start_time_str)
                else:
                    start_time = start_time_str
                self.update_user_state(user_id, 'start_time', start_time.isoformat() if isinstance(start_time, datetime) else start_time)

            # Формируем итоговое сообщение (форматируем маршрут для отображения)
            orders_data = self.db_service.get_today_orders(user_id)
            orders_dict = {od.get('order_number'): od for od in orders_data if od.get('order_number')}
            start_location_data = self.db_service.get_start_location(user_id, today) or {}
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
                    reply_markup=self._route_menu_markup(),
                    disable_web_page_preview=True
                )
            except Exception:
                # Если не удалось отредактировать (например, сообщение слишком длинное), отправляем новое
                self.bot.delete_message(message.chat.id, status_msg.message_id)
                self.bot.reply_to(message, summary_text, parse_mode='HTML', reply_markup=self._route_menu_markup(), disable_web_page_preview=True)

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
                        reply_markup=self._route_menu_markup()
                    )
                else:
                    # Если статусное сообщение не было создано, отправляем новое
                    self.bot.reply_to(message, f"❌ Ошибка оптимизации: {str(e)}", reply_markup=self._route_menu_markup())
            except Exception as edit_error:
                logger.warning(f"Ошибка при редактировании сообщения: {edit_error}")
                # Если не удалось отредактировать, отправляем новое сообщение
                try:
                    if 'status_msg' in locals():
                        self.bot.delete_message(message.chat.id, status_msg.message_id)
                except Exception as e:
                    logger.warning(f"Не удалось удалить сообщение: {e}")
                self.bot.reply_to(message, f"❌ Ошибка оптимизации: {str(e)}", reply_markup=self._route_menu_markup())

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
                    today = estimated_arrival.date()
                    window_start = datetime.combine(today, order.delivery_time_start)
                    window_end = datetime.combine(today, order.delivery_time_end)

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
            from src.database.connection import get_db_session
            from src.models.order import CallStatusDB
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

    def handle_view_route(self, message):
        """Handle /view_route command"""
        user_id = message.from_user.id
        today = date.today()
        
        # Загружаем из БД
        route_data = self.db_service.get_route_data(user_id, today)
        if not route_data:
            self.bot.reply_to(message, "❌ Маршрут не оптимизирован. Используйте /optimize_route", reply_markup=self._route_menu_markup())
            return
        
        route_points_data = route_data.get('route_points_data', [])
        route_order = route_data.get('route_order', [])
        
        # Проверка на старый формат (для обратной совместимости)
        if not route_points_data:
            old_route_summary = route_data.get('route_summary', [])
            if old_route_summary and isinstance(old_route_summary[0], str):
                # Старый формат - объединяем все в одно сообщение
                text = "<b>🗺️ Маршрут доставки</b>\n\n" + "\n\n".join(old_route_summary)
                # Если сообщение слишком длинное, разбиваем на части
                if len(text) > 4096:
                    # Разбиваем на части по 4000 символов
                    for i in range(0, len(text), 4000):
                        chunk = text[i:i + 4000]
                        if i == 0:
                            self.bot.reply_to(message, chunk, parse_mode='HTML', reply_markup=self._route_menu_markup(), disable_web_page_preview=True)
                        else:
                            self.bot.send_message(message.chat.id, chunk, parse_mode='HTML', disable_web_page_preview=True)
                else:
                    self.bot.reply_to(message, text, parse_mode='HTML', reply_markup=self._route_menu_markup(), disable_web_page_preview=True)
                return
        
        if not route_points_data or not route_order:
            self.bot.reply_to(message, "❌ Маршрут не оптимизирован. Используйте /optimize_route", reply_markup=self._route_menu_markup())
            return
        
        # Загружаем заказы из БД
        orders_data = self.db_service.get_today_orders(user_id)
        orders_dict = {od.get('order_number'): od for od in orders_data if od.get('order_number')}
        
        # Загружаем точку старта
        start_location_data = self.db_service.get_start_location(user_id, today) or {}
        
        # Форматируем маршрут
        maps_service = MapsService()
        route_summary = self._format_route_summary(user_id, route_points_data, orders_dict, start_location_data, maps_service)
        
        if not route_summary:
            self.bot.reply_to(message, "❌ Не удалось сформировать маршрут", reply_markup=self._route_menu_markup())
            return

        # Объединяем весь маршрут в одно сообщение
        text = "<b>🗺️ Маршрут доставки</b>\n\n" + "\n\n".join(route_summary)
        
        # Если сообщение слишком длинное (лимит Telegram - 4096 символов), разбиваем на части
        if len(text) > 4096:
            # Разбиваем на части по 4000 символов, стараясь не разрывать заказы
            parts = []
            current_part = "<b>🗺️ Маршрут доставки</b>\n\n"
            
            for order_text in route_summary:
                # Проверяем, поместится ли следующий заказ
                test_text = current_part + order_text + "\n\n"
                if len(test_text) > 4000:
                    # Сохраняем текущую часть и начинаем новую
                    parts.append(current_part.rstrip())
                    current_part = order_text + "\n\n"
                else:
                    current_part = test_text
            
            # Добавляем последнюю часть
            if current_part.strip():
                parts.append(current_part.rstrip())
            
            # Отправляем части
            for i, part in enumerate(parts):
                if i == 0:
                    self.bot.reply_to(message, part, parse_mode='HTML', reply_markup=self._route_menu_markup(), disable_web_page_preview=True)
                else:
                    self.bot.send_message(message.chat.id, part, parse_mode='HTML', disable_web_page_preview=True)
        else:
            # Отправляем все одним сообщением
            self.bot.reply_to(message, text, parse_mode='HTML', reply_markup=self._route_menu_markup(), disable_web_page_preview=True)

    def _format_call_schedule(self, call_schedule_data: List[Dict]) -> List[str]:
        """Форматирует график звонков из структурированных данных"""
        formatted = []
        for call_data in call_schedule_data:
            try:
                # Проверяем формат (старый или новый)
                if isinstance(call_data, str):
                    # Старый формат - просто возвращаем как есть
                    formatted.append(call_data)
                    continue
                
                # Новый формат - структурированные данные
                call_time = datetime.fromisoformat(call_data.get('call_time'))
                arrival_time = datetime.fromisoformat(call_data.get('arrival_time'))
                
                order_number = call_data.get('order_number')
                customer_name = call_data.get('customer_name')
                phone = call_data.get('phone')
                
                # Формируем информацию о клиенте
                call_info = order_number or customer_name or 'Клиент'
                if customer_name:
                    call_info = f"{customer_name} (№{order_number})" if order_number else customer_name
                
                time_info = f"к {arrival_time.strftime('%H:%M')}"
                
                if phone:
                    formatted.append(f"📞 {call_time.strftime('%H:%M')} - {call_info} ({phone}) - {time_info}")
                else:
                    formatted.append(f"📞 {call_time.strftime('%H:%M')} - {call_info} (телефон не указан) - {time_info}")
            except Exception as e:
                logger.error(f"Ошибка форматирования звонка: {e}", exc_info=True)
                continue
        
        return formatted

    def handle_calls(self, message):
        """Handle /calls command - формирует график звонков динамически из актуальных данных"""
        user_id = message.from_user.id
        today = date.today()
        
        # Загружаем маршрут из БД
        route_data = self.db_service.get_route_data(user_id, today)
        if not route_data:
            self.bot.reply_to(message, "❌ Маршрут не оптимизирован. Оптимизируйте маршрут сначала", reply_markup=self._route_menu_markup())
            return
        
        route_points_data = route_data.get('route_points_data', [])
        route_order = route_data.get('route_order', [])
        
        if not route_points_data or not route_order:
            self.bot.reply_to(message, "❌ Маршрут не оптимизирован. Оптимизируйте маршрут сначала", reply_markup=self._route_menu_markup())
            return
        
        # Загружаем актуальные данные заказов из БД
        orders_data = self.db_service.get_today_orders(user_id)
        orders_dict = {od.get('order_number'): od for od in orders_data if od.get('order_number')}
        
        # Формируем call_schedule динамически из route_points_data и актуальных данных заказов
        call_schedule = []
        for idx, order_num in enumerate(route_order):
            if idx >= len(route_points_data):
                continue
            
            order_data = orders_dict.get(order_num)
            if not order_data:
                continue
            
            point_data = route_points_data[idx]
            
            try:
                call_time_dt = datetime.fromisoformat(point_data.get('call_time'))
                arrival_time_dt = datetime.fromisoformat(point_data.get('estimated_arrival'))
            except Exception as e:
                logger.warning(f"Ошибка парсинга времени звонка/доставки: {e}")
                continue
            
            # Используем актуальные данные из БД
            call_data = {
                "order_number": order_num,
                "call_time": call_time_dt.isoformat(),
                "arrival_time": arrival_time_dt.isoformat(),
                "phone": order_data.get('phone') or None,
                "customer_name": order_data.get('customer_name') or None
            }
            call_schedule.append(call_data)
        
        if not call_schedule:
            self.bot.reply_to(message, "❌ Не удалось сформировать график звонков", reply_markup=self._route_menu_markup())
            return

        # Форматируем график звонков
        formatted_schedule = self._format_call_schedule(call_schedule)
        
        if not formatted_schedule:
            self.bot.reply_to(message, "❌ Не удалось сформировать график звонков", reply_markup=self._route_menu_markup())
            return

        text = "<b>📞 График звонков клиентам:</b>\n\n" + "\n".join(formatted_schedule)
        self.bot.reply_to(message, text, parse_mode='HTML', reply_markup=self._route_menu_markup())

    def handle_text_message(self, message):
        """Handle text messages based on user state"""
        user_id = message.from_user.id
        state_data = self.get_user_state(user_id)
        current_state = state_data.get('state')

        # Глобальные кнопки без состояния
        if not current_state:
            text = message.text.strip()
            # Главное меню
            if text == "📦 Заказы":
                return self.bot.reply_to(message, "📦 <b>Заказы</b>", parse_mode='HTML', reply_markup=self._orders_menu_markup())
            if text == "🗺️ Маршрут":
                return self.bot.reply_to(message, "🗺️ <b>Маршрут</b>", parse_mode='HTML', reply_markup=self._route_menu_markup())
            # Меню заказов
            if text == "➕ Добавить заказы":
                return self.handle_add_orders(message)
            if text == "ℹ️ Детали заказа":
                try:
                    return self.handle_order_details_start(message)
                except Exception as e:
                    logger.error(f"Ошибка в handle_order_details_start: {e}", exc_info=True)
                    self.bot.reply_to(message, f"❌ Ошибка: {str(e)}", reply_markup=self._orders_menu_markup())
                    return
            if text == "✅ Доставленные":
                try:
                    return self.handle_delivered_orders(message)
                except Exception as e:
                    logger.error(f"Ошибка в handle_delivered_orders: {e}", exc_info=True)
                    self.bot.reply_to(message, f"❌ Ошибка: {str(e)}", reply_markup=self._orders_menu_markup())
                    return
            # Меню маршрута
            if text == "📍 Точка старта":
                return self.handle_set_start(message)
            if text == "📍 Геопозиция":
                return self.handle_set_start_location_geo(message)
            if text == "✍️ Адрес":
                return self.handle_set_start_location_address(message)
            if text == "⏰ Время старта":
                return self.handle_set_start_time_change(message)
            if text == "▶️ Оптимизировать":
                return self.handle_optimize_route(message)
            if text == "📋 Показать маршрут":
                return self.handle_view_route(message)
            if text == "📞 Звонки":
                try:
                    return self.handle_calls(message)
                except Exception as e:
                    logger.error(f"Ошибка в handle_calls: {e}", exc_info=True)
                    self.bot.reply_to(message, f"❌ Ошибка: {str(e)}", reply_markup=self._route_menu_markup())
                    return
            if text == "🚦 Мониторинг":
                return self.handle_monitor(message)
            if text == "🛑 Стоп мониторинг":
                return self.handle_stop_monitor(message)
            if text == "ℹ️ Статус пробок":
                return self.handle_traffic_status(message)
            # Общие действия
            if text == "🗑️ Сбросить день":
                return self.handle_reset_day(message)
            if text == "✍️ Ввести другой адрес":
                user_id = message.from_user.id
                self.update_user_state(user_id, 'state', 'waiting_for_start_address')
                self.update_user_state(user_id, 'pending_start_address', None)
                self.update_user_state(user_id, 'pending_start_lat', None)
                self.update_user_state(user_id, 'pending_start_lon', None)
                self.update_user_state(user_id, 'pending_start_gid', None)
                from telebot import types
                markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
                markup.row("⬅️ Главное меню")
                return self.bot.reply_to(
                    message,
                    "✍️ <b>Введите адрес точки старта:</b>\n\nПример: ул. Ленина, д.10",
                    parse_mode='HTML',
                    reply_markup=markup
                )
            if text == "⬅️ Главное меню":
                self.update_user_state(message.from_user.id, 'state', None)
                self.update_user_state(message.from_user.id, 'updating_order_number', None)
                return self.bot.reply_to(message, "🏠 Главное меню", reply_markup=self._main_menu_markup())
        
        # Кнопки выбора поля для обновления заказа
        text = message.text.strip()
        if text in ["📞 Телефон", "👤 ФИО", "💬 Комментарий", "🏢 Подъезд", "🚪 Квартира", "🕐 Время доставки"]:
            user_id = message.from_user.id
            state_data = self.get_user_state(user_id)
            
            if text == "📞 Телефон":
                self.update_user_state(user_id, 'state', 'waiting_for_order_phone')
                self.bot.reply_to(message, "📞 Введите номер телефона:", reply_markup=self._update_order_back_markup())
            elif text == "👤 ФИО":
                self.update_user_state(user_id, 'state', 'waiting_for_order_name')
                self.bot.reply_to(message, "👤 Введите ФИО клиента:", reply_markup=self._update_order_back_markup())
            elif text == "💬 Комментарий":
                self.update_user_state(user_id, 'state', 'waiting_for_order_comment')
                self.bot.reply_to(message, "💬 Введите комментарий:", reply_markup=self._update_order_back_markup())
            elif text == "🏢 Подъезд":
                self.update_user_state(user_id, 'state', 'waiting_for_order_entrance')
                self.bot.reply_to(message, "🏢 Введите номер подъезда:", reply_markup=self._update_order_back_markup())
            elif text == "🚪 Квартира":
                self.update_user_state(user_id, 'state', 'waiting_for_order_apartment')
                self.bot.reply_to(message, "🚪 Введите номер квартиры:", reply_markup=self._update_order_back_markup())
            elif text == "🕐 Время доставки":
                order_number = state_data.get('updating_order_number')
                if order_number:
                    self.update_user_state(user_id, 'state', 'waiting_for_order_delivery_time')
                    # Показываем текущее время доставки если есть
                    orders = state_data.get('orders', [])
                    current_time = ""
                    for order_data in orders:
                        if order_data.get('order_number') == order_number:
                            if order_data.get('delivery_time_window'):
                                current_time = f"\nТекущее время: {order_data.get('delivery_time_window')}\n"
                            break
                    self.bot.reply_to(
                        message,
                        f"🕐 <b>Время доставки</b>{current_time}\nВведите новое время доставки в формате ЧЧ:ММ - ЧЧ:ММ\nПример: 10:00 - 13:00",
                        parse_mode='HTML',
                        reply_markup=self._update_order_back_markup()
                    )
                else:
                    self.bot.reply_to(message, "❌ Ошибка: номер заказа не найден")
            return

        if current_state == 'waiting_for_orders':
            self.process_order(message, state_data)
        elif current_state == 'waiting_for_start_location':
            self.process_start_location_choice(message, state_data)
        elif current_state == 'waiting_for_start_address':
            self.process_start_location(message, state_data)
        elif current_state == 'confirming_start_location':
            # Если пользователь вводит текст в состоянии подтверждения, обрабатываем как новый адрес
            text = message.text.strip()
            if text == "✍️ Ввести другой адрес" or text == "⬅️ Главное меню":
                # Обработка кнопок уже есть выше
                pass
            else:
                # Пользователь ввел новый адрес
                self.process_start_location(message, state_data)
        elif current_state == 'waiting_for_start_time':
            self.process_start_time(message, state_data)
        elif current_state == 'waiting_for_order_number':
            self.process_order_number(message, state_data)
        elif current_state == 'waiting_for_order_phone':
            self.process_order_phone(message, state_data)
        elif current_state == 'waiting_for_order_name':
            self.process_order_name(message, state_data)
        elif current_state == 'waiting_for_order_comment':
            self.process_order_comment(message, state_data)
        elif current_state == 'waiting_for_order_entrance':
            self.process_order_entrance(message, state_data)
        elif current_state == 'waiting_for_order_apartment':
            self.process_order_apartment(message, state_data)
        elif current_state == 'waiting_for_order_delivery_time':
            self.process_order_delivery_time(message, state_data)
        elif current_state == 'waiting_for_call_comment':
            self.process_call_comment(message, state_data)
        elif current_state == 'searching_order_by_number':
            self.process_search_order_by_number(message, state_data)
        else:
            # Если пользователь не в состоянии ожидания, проверяем, не ввел ли он номер заказа
            text = message.text.strip()
            # Проверяем, является ли текст числом (номером заказа)
            # Игнорируем команды и кнопки меню
            if (text.isdigit() and len(text) >= 4 and 
                not text.startswith('/') and 
                text not in ["⬅️ Главное меню", "✅ Готово", "/done", "/skip", "⏭️ Пропустить комментарий"]):
                # Проверяем, существует ли заказ с таким номером
                user_id = message.from_user.id
                try:
                    orders_data = self.db_service.get_today_orders(user_id)
                    order_found = False
                    for od in orders_data:
                        if od.get('order_number') == text:
                            order_found = True
                            # Открываем детали заказа
                            self.show_order_details(user_id, text, message.chat.id)
                            break
                    # Если заказ не найден, просто игнорируем (чтобы не мешать другим командам)
                except Exception as e:
                    logger.debug(f"Ошибка при поиске заказа по номеру (не критично): {e}")

    def process_order(self, message, state_data):
        """Process order input"""
        text = message.text.strip()
        user_id = message.from_user.id

        if text == "/done" or text == "✅ Готово":
            orders = state_data.get("orders", [])
            if not orders:
                self.bot.reply_to(message, "❌ Нет добавленных заказов", reply_markup=self._orders_menu_markup())
                return

            # Сохраняем заказы в БД
            today = date.today()
            saved_count = 0
            errors = []
            for i, order_data in enumerate(orders):
                try:
                    # Преобразуем строки времени обратно в time объекты, если они есть
                    order_dict = order_data.copy()
                    
                    # Убеждаемся, что address есть (обязательное поле)
                    if not order_dict.get('address'):
                        errors.append(f"Заказ {i+1}: отсутствует адрес")
                        continue
                    
                    # Преобразуем время, если оно в строковом формате
                    if isinstance(order_dict.get('delivery_time_start'), str):
                        try:
                            order_dict['delivery_time_start'] = datetime.fromisoformat(order_dict['delivery_time_start']).time()
                        except Exception as e:
                            logger.debug(f"Ошибка парсинга delivery_time_start: {e}")
                            order_dict['delivery_time_start'] = None
                    if isinstance(order_dict.get('delivery_time_end'), str):
                        try:
                            order_dict['delivery_time_end'] = datetime.fromisoformat(order_dict['delivery_time_end']).time()
                        except Exception as e:
                            logger.debug(f"Ошибка парсинга delivery_time_end: {e}")
                            order_dict['delivery_time_end'] = None
                    
                    # Убеждаемся, что все поля имеют правильные типы
                    # None значения оставляем как есть для необязательных полей
                    
                    order = Order(**order_dict)
                    self.db_service.save_order(user_id, order, today)
                    saved_count += 1
                except Exception as e:
                    error_msg = f"Заказ {i+1}: {str(e)}"
                    errors.append(error_msg)
                    logger.error(f"Ошибка сохранения заказа {i+1}: {e}, данные: {order_data}", exc_info=True)
                    import traceback
                    traceback.print_exc()
            
            # Очищаем временные данные
            self.update_user_state(user_id, 'state', None)
            self.update_user_state(user_id, 'orders', [])
            
            response_text = f"✅ Сохранено {saved_count} заказов за сегодня ({today.strftime('%d.%m.%Y')})"
            if errors:
                response_text += f"\n\n⚠️ Ошибки при сохранении:\n" + "\n".join(errors[:5])
            
            self.bot.reply_to(
                message,
                response_text,
                reply_markup=self._orders_menu_markup()
            )
            return

        if text == "⬅️ В меню" or text == "⬅️ Главное меню":
            self.update_user_state(user_id, 'state', None)
            self.bot.reply_to(message, "🏠 Возврат в главное меню", reply_markup=self._main_menu_markup())
            return

        def parse_line(line: str) -> dict:
            """Парсинг одной строки заказа в оба поддерживаемых формата."""
            line = line.strip()
            if not line:
                raise ValueError("Пустая строка")

            if "|" in line:
                parts = line.split("|")
                if len(parts) < 3:
                    raise ValueError("Недостаточно данных в расширенном формате")
                order = Order(
                    customer_name=parts[0].strip() if len(parts) > 0 and parts[0].strip() else None,
                    phone=parts[1].strip() if len(parts) > 1 and parts[1].strip() else None,
                    address=parts[2].strip(),
                    comment=parts[3].strip() if len(parts) > 3 and parts[3].strip() else None
                )
                return order.model_dump()

            # Формат: Время НомерЗаказа Адрес
            import re
            time_pattern = r'(\d{1,2}:\d{2}\s*-\s*\d{1,2}:\d{2})'
            time_match = re.search(time_pattern, line)

            if time_match:
                time_window = time_match.group(1).strip()
                remaining_text = line.replace(time_window, '').strip()
                order_num_match = re.match(r'(\d+)\s+', remaining_text)
                if order_num_match:
                    order_number = order_num_match.group(1)
                    address = remaining_text[order_num_match.end():].strip()
                else:
                    order_number = None
                    address = remaining_text
            else:
                time_window = None
                order_number = None
                address = line

            order = Order(
                address=address,
                order_number=order_number if order_number else None,
                delivery_time_window=time_window if time_window else None
            )
            return order.model_dump()

        # Если прислали несколько строк разом — разбираем все
        if "\n" in text:
            lines = [l.strip() for l in text.splitlines() if l.strip()]
            orders_ok = []
            errors = []
            for line in lines:
                try:
                    orders_ok.append(parse_line(line))
                except Exception as e:
                    errors.append(f"❌ {line} → {e}")

            if orders_ok:
                orders = state_data.get("orders", [])
                orders.extend(orders_ok)
                self.update_user_state(user_id, 'orders', orders)
                self.bot.reply_to(
                    message,
                    f"✅ Добавлено {len(orders_ok)} из {len(lines)} заказов\n"
                    + ("\n".join(errors) if errors else "")
                )
            else:
                self.bot.reply_to(message, "❌ Ни один заказ не добавлен. Проверьте формат.")
            return

        # Одиночная строка
        try:
            order_data = parse_line(text)

            orders = state_data.get("orders", [])
            orders.append(order_data)
            self.update_user_state(user_id, 'orders', orders)

            if order_data.get('order_number'):
                order_info = f"Заказ №{order_data['order_number']}"
                if order_data.get('delivery_time_window'):
                    order_info += f" ({order_data['delivery_time_window']})"
            else:
                order_info = order_data.get('customer_name') or 'Клиент'

            address_short = order_data['address'][:50] + "..." if len(order_data['address']) > 50 else order_data['address']

            self.bot.reply_to(message, f"✅ Заказ добавлен: {order_info}\n📍 {address_short}")

        except Exception as e:
            error_text = (
                f"❌ Ошибка в формате заказа: {str(e)}\n\n"
                "📋 <b>Поддерживаемые форматы:</b>\n\n"
                "1️⃣ <b>Ваш формат:</b>\n"
                "<code>Время НомерЗаказа Адрес</code>\n"
                "Пример: <code>10:00-13:00 3258104 ул Манчестерская, д 3</code>\n\n"
                "2️⃣ <b>Расширенный формат:</b>\n"
                "<code>Имя|Телефон|Адрес|Комментарий</code>\n"
                "Пример: <code>Иван|+79991234567|ул Ленина 10|домофон 05</code>"
            )
            self.bot.reply_to(message, error_text, parse_mode='HTML')

    def handle_set_start_location_geo(self, message):
        """Обработка выбора геопозиции для точки старта"""
        user_id = message.from_user.id
        self.update_user_state(user_id, 'state', 'waiting_for_start_location')
        
        from telebot import types
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
        button = types.KeyboardButton("📍 Отправить геопозицию", request_location=True)
        markup.add(button)
        markup.row("⬅️ Главное меню")

        text = (
            "📍 <b>Отправка геопозиции</b>\n\n"
            "Нажмите кнопку ниже, чтобы отправить ваше текущее местоположение:"
        )
        self.bot.reply_to(message, text, parse_mode='HTML', reply_markup=markup)

    def handle_set_start_location_address(self, message):
        """Обработка выбора адреса для точки старта"""
        user_id = message.from_user.id
        self.update_user_state(user_id, 'state', 'waiting_for_start_address')
        
        from telebot import types
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
        markup.row("⬅️ Главное меню")
        
        text = (
            "📝 <b>Ввод адреса</b>\n\n"
            "Введите адрес точки старта:\n"
            "Пример: ул. Ленина, д.10"
        )
        self.bot.reply_to(message, text, parse_mode='HTML', reply_markup=markup)

    def handle_set_start_time_change(self, message):
        """Обработка изменения времени старта"""
        user_id = message.from_user.id
        self.update_user_state(user_id, 'state', 'waiting_for_start_time')
        
        from telebot import types
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
        markup.row("⬅️ Главное меню")
        
        state_data = self.get_user_state(user_id)
        start_time_str = state_data.get('start_time')
        current_time = ""
        if start_time_str:
            start_time = datetime.fromisoformat(start_time_str)
            current_time = f"\nТекущее время: {start_time.strftime('%H:%M')}\n"
        
        text = (
            f"⏰ <b>Время старта</b>{current_time}\n"
            "Укажите время начала маршрута в формате ЧЧ:ММ\n"
            "Пример: 09:00"
        )
        self.bot.reply_to(message, text, parse_mode='HTML', reply_markup=markup)

    def process_start_location_choice(self, message, state_data):
        """Process choice between location and address input"""
        user_id = message.from_user.id
        choice = message.text.strip()

        if choice == "✍️ Ввести адрес вручную" or choice == "✍️ Адрес":
            self.update_user_state(user_id, 'state', 'waiting_for_start_address')
            # Убираем клавиатуру
            from telebot import types
            markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
            markup.row("⬅️ Главное меню")
            text = (
                "📝 <b>Ввод адреса</b>\n\n"
                "Введите адрес точки старта:\n"
                "Пример: ул. Ленина, д.10"
            )
            self.bot.reply_to(message, text, parse_mode='HTML', reply_markup=markup)

        elif choice == "📍 Отправить геопозицию" or choice == "📍 Геопозиция":
            from telebot import types
            markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
            button = types.KeyboardButton("📍 Отправить геопозицию", request_location=True)
            markup.add(button)
            markup.row("⬅️ Главное меню")

            text = (
                "📍 <b>Отправка геопозиции</b>\n\n"
                "Нажмите кнопку ниже, чтобы отправить ваше текущее местоположение:"
            )
            self.bot.reply_to(message, text, parse_mode='HTML', reply_markup=markup)

        else:
            # Пользователь ввел адрес напрямую
            self.process_start_location(message, state_data)

    def handle_callback_query(self, call):
        """Обработка callback запросов от inline кнопок"""
        user_id = call.from_user.id
        callback_data = call.data
        
        if callback_data.startswith("order_details_"):
            # Показать детали заказа
            order_number = callback_data.replace("order_details_", "")
            try:
                self.show_order_details(user_id, order_number, call.message.chat.id)
                self.bot.answer_callback_query(call.id)
            except Exception as e:
                logger.error(f"Ошибка в show_order_details: {e}", exc_info=True)
                self.bot.answer_callback_query(call.id, f"❌ Ошибка: {str(e)}", show_alert=True)
                self.bot.send_message(call.message.chat.id, f"❌ Ошибка при загрузке заказа: {str(e)}", reply_markup=self._main_menu_markup())
        elif callback_data == "view_delivered_orders":
            # Показать доставленные заказы
            self.show_delivered_orders(user_id, call.message.chat.id)
            self.bot.answer_callback_query(call.id)
        elif callback_data.startswith("mark_delivered_"):
            # Пометить заказ как доставленный
            order_number = callback_data.replace("mark_delivered_", "")
            self.mark_order_delivered(user_id, order_number, call.message.chat.id)
            self.bot.answer_callback_query(call.id, "✅ Заказ помечен как доставленный")
        elif callback_data == "reset_day_confirm":
            # Подтверждение сброса дня
            self.handle_reset_day_confirm(call)
        elif callback_data == "reset_day_cancel":
            # Отмена сброса дня
            self.bot.answer_callback_query(call.id, "❌ Отменено")
            self.bot.edit_message_text(
                "❌ Сброс дня отменен",
                call.message.chat.id,
                call.message.message_id,
                reply_markup=None
            )
        elif callback_data == "confirm_start_address":
            # Подтверждение адреса точки старта
            self.handle_confirm_start_address(call)
        elif callback_data == "change_start_address":
            # Изменение адреса точки старта
            self.bot.answer_callback_query(call.id, "✍️ Введите новый адрес")
            self.bot.send_message(
                call.message.chat.id,
                "✍️ <b>Введите новый адрес точки старта:</b>\n\nПример: ул. Ленина, д.10",
                parse_mode='HTML',
                reply_markup=self._update_order_back_markup()
            )
            user_id = call.from_user.id
            self.update_user_state(user_id, 'state', 'waiting_for_start_address')
        elif callback_data.startswith("call_confirm_"):
            # Подтверждение звонка
            call_status_id = int(callback_data.replace("call_confirm_", ""))
            self.handle_call_confirm(call, call_status_id)
        elif callback_data.startswith("call_reject_"):
            # Отклонение звонка
            call_status_id = int(callback_data.replace("call_reject_", ""))
            self.handle_call_reject(call, call_status_id)
        elif callback_data == "search_order_by_number":
            # Поиск заказа по номеру
            self.bot.answer_callback_query(call.id, "🔍 Введите номер заказа")
            from telebot import types
            markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
            markup.row("⬅️ Главное меню")
            self.bot.send_message(
                call.message.chat.id,
                "🔍 <b>Поиск заказа</b>\n\nВведите номер заказа для просмотра деталей:",
                parse_mode='HTML',
                reply_markup=markup
            )
            user_id = call.from_user.id
            self.update_user_state(user_id, 'state', 'searching_order_by_number')

    def show_order_details(self, user_id: int, order_number: str, chat_id: int):
        """Показать детали заказа с кнопкой Доставлен"""
        today = date.today()
        
        # Загружаем из БД
        try:
            orders_data = self.db_service.get_today_orders(user_id)
        except Exception as e:
            logger.error(f"Ошибка загрузки заказов из БД: {e}", exc_info=True)
            self.bot.send_message(chat_id, f"❌ Ошибка загрузки данных: {str(e)}", reply_markup=self._main_menu_markup())
            return
        
        order_found = False
        order_data = None
        for od in orders_data:
            if od.get('order_number') == order_number:
                order_found = True
                order_data = od
                break
        
        if not order_found:
            self.bot.send_message(chat_id, f"❌ Заказ №{order_number} не найден", reply_markup=self._main_menu_markup())
            return
        
        # Преобразуем строки времени обратно в time объекты
        order_dict = order_data.copy()
        try:
            if order_dict.get('delivery_time_start'):
                if isinstance(order_dict['delivery_time_start'], str):
                    # Парсим формат HH:MM:SS или HH:MM
                    time_str = order_dict['delivery_time_start']
                    if ':' in time_str:
                        parts = time_str.split(':')
                        if len(parts) >= 2:
                            order_dict['delivery_time_start'] = time(int(parts[0]), int(parts[1]))
                        else:
                            order_dict['delivery_time_start'] = None
                    else:
                        order_dict['delivery_time_start'] = None
            if order_dict.get('delivery_time_end'):
                if isinstance(order_dict['delivery_time_end'], str):
                    # Парсим формат HH:MM:SS или HH:MM
                    time_str = order_dict['delivery_time_end']
                    if ':' in time_str:
                        parts = time_str.split(':')
                        if len(parts) >= 2:
                            order_dict['delivery_time_end'] = time(int(parts[0]), int(parts[1]))
                        else:
                            order_dict['delivery_time_end'] = None
                    else:
                        order_dict['delivery_time_end'] = None
        except Exception as e:
            logger.warning(f"Ошибка преобразования времени: {e}")
            order_dict['delivery_time_start'] = None
            order_dict['delivery_time_end'] = None
        
        # Показываем детали заказа
        try:
            order = Order(**order_dict)
        except Exception as e:
            logger.error(f"Ошибка создания Order: {e}, данные: {order_dict}", exc_info=True)
            import traceback
            traceback.print_exc()
            self.bot.send_message(chat_id, f"❌ Ошибка обработки данных заказа: {str(e)}", reply_markup=self._main_menu_markup())
            return
        details = [
            f"ℹ️ <b>Детали заказа №{order_number}</b>\n",
            f"📍 <b>Адрес:</b> {order.address}",
        ]
        
        if order.customer_name:
            details.append(f"👤 <b>ФИО:</b> {order.customer_name}")
        else:
            details.append(f"👤 <b>ФИО:</b> Не указано")
        
        if order.phone:
            details.append(f"📞 <b>Телефон:</b> {order.phone}")
        else:
            details.append(f"📞 <b>Телефон:</b> Не указан")
        
        if order.delivery_time_window:
            details.append(f"🕐 <b>Время доставки:</b> {order.delivery_time_window}")
        else:
            details.append(f"🕐 <b>Время доставки:</b> Не указано")
        
        if order.entrance_number:
            details.append(f"🏢 <b>Подъезд:</b> {order.entrance_number}")
        else:
            details.append(f"🏢 <b>Подъезд:</b> Не указан")
        
        if order.apartment_number:
            details.append(f"🚪 <b>Квартира:</b> {order.apartment_number}")
        else:
            details.append(f"🚪 <b>Квартира:</b> Не указана")
        
        if order.comment:
            details.append(f"💬 <b>Комментарий:</b> {order.comment}")
        else:
            details.append(f"💬 <b>Комментарий:</b> Нет")
        
        if order.latitude and order.longitude:
            details.append(f"🗺️ <b>Координаты:</b> {order.latitude:.6f}, {order.longitude:.6f}")
        
        # Создаем inline кнопку "Доставлен"
        from telebot import types
        inline_markup = types.InlineKeyboardMarkup()
        inline_markup.add(
            types.InlineKeyboardButton(
                "✅ Доставлен",
                callback_data=f"mark_delivered_{order_number}"
            )
        )
        
        # Показываем кнопки для редактирования
        reply_markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
        reply_markup.row("📞 Телефон", "👤 ФИО")
        reply_markup.row("💬 Комментарий", "🏢 Подъезд")
        reply_markup.row("🚪 Квартира", "🕐 Время доставки")
        reply_markup.row("⬅️ Главное меню")
        
        # Сохраняем номер заказа для быстрого редактирования
        self.update_user_state(user_id, 'updating_order_number', order_number)
        
        try:
            self.bot.send_message(chat_id, "\n".join(details), parse_mode='HTML', reply_markup=reply_markup)
            self.bot.send_message(chat_id, "Нажмите кнопку ниже, чтобы пометить заказ как доставленный:", reply_markup=inline_markup)
        except Exception as e:
            logger.error(f"Ошибка отправки сообщения с деталями заказа: {e}", exc_info=True)
            self.bot.send_message(chat_id, f"❌ Ошибка отображения деталей заказа: {str(e)}", reply_markup=self._main_menu_markup())

    def mark_order_delivered(self, user_id: int, order_number: str, chat_id: int):
        """Пометить заказ как доставленный"""
        today = date.today()
        
        # Обновляем в БД
        updated = self.db_service.update_order(
            user_id, order_number, {'status': 'delivered'}, today
        )
        
        if updated:
            # Очищаем маршрут, так как заказ доставлен
            self.update_user_state(user_id, 'route_summary', [])
            self.update_user_state(user_id, 'call_schedule', [])
            self.update_user_state(user_id, 'route_order', [])
            
            # Также удаляем маршрут из БД
            self.db_service.get_route_data(user_id, today)  # Загружаем для проверки
            # Можно оставить маршрут в БД, но очистить его при следующей оптимизации
            
            self.bot.send_message(
                chat_id,
                f"✅ Заказ №{order_number} помечен как доставленный и исключен из маршрута",
                reply_markup=self._main_menu_markup()
            )
        else:
            self.bot.send_message(chat_id, f"❌ Заказ №{order_number} не найден")

    def show_delivered_orders(self, user_id: int, chat_id: int):
        """Показать список доставленных заказов"""
        today = date.today()
        
        # Загружаем из БД
        orders_data = self.db_service.get_today_orders(user_id)
        
        delivered_orders = [od for od in orders_data if od.get('status', 'pending') == 'delivered']
        
        if not delivered_orders:
            self.bot.send_message(chat_id, "✅ Нет доставленных заказов", reply_markup=self._main_menu_markup())
            return
        
        text = "✅ <b>Доставленные заказы</b>\n\n"
        
        for i, order_data in enumerate(delivered_orders, 1):
            order_number = order_data.get('order_number', 'Без номера')
            address = order_data.get('address', 'Адрес не указан')
            time_window = order_data.get('delivery_time_window', 'Время не указано')
            
            address_short = address[:40] + "..." if len(address) > 40 else address
            
            text += f"{i}. <b>№{order_number}</b>\n"
            text += f"   📍 {address_short}\n"
            text += f"   🕐 {time_window}\n\n"
        
        self.bot.send_message(chat_id, text, parse_mode='HTML', reply_markup=self._main_menu_markup())

    def handle_location_message(self, message):
        """Handle location message"""
        user_id = message.from_user.id
        state_data = self.get_user_state(user_id)
        today = date.today()

        if state_data.get('state') == 'waiting_for_start_location':
            lat = message.location.latitude
            lon = message.location.longitude

            # Сохраняем в БД
            self.db_service.save_start_location(
                user_id, 'geo', None, lat, lon, None, today
            )
            
            # Также сохраняем в state для обратной совместимости
            self.update_user_state(user_id, 'start_location', {'lat': lat, 'lon': lon})
            self.update_user_state(user_id, 'state', 'waiting_for_start_time')

            from telebot import types
            markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
            markup.row("⬅️ Главное меню")

            text = (
                f"✅ <b>Геопозиция получена!</b>\n\n"
                f"📍 Координаты: {lat:.6f}, {lon:.6f}\n\n"
                f"⏰ <b>Время старта</b>\n\n"
                f"Укажите время начала маршрута в формате ЧЧ:ММ\n"
                f"Пример: 09:00"
            )
            self.bot.reply_to(message, text, parse_mode='HTML', reply_markup=markup)

    def process_start_location(self, message, state_data):
        """Process start location input (address)"""
        user_id = message.from_user.id
        today = date.today()
        address = message.text.strip()

        if address == "⬅️ Главное меню":
            self.update_user_state(user_id, 'state', None)
            self.bot.reply_to(message, "🏠 Возврат в главное меню", reply_markup=self._main_menu_markup())
            return

        # Геокодируем адрес сразу
        self.bot.send_chat_action(message.chat.id, 'typing')
        maps_service = MapsService()
        
        try:
            lat, lon, gid = maps_service.geocode_address_sync(address)
            
            if not lat or not lon:
                from telebot import types
                markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
                markup.row("✍️ Ввести другой адрес")
                markup.row("⬅️ Главное меню")
                
                self.bot.reply_to(
                    message,
                    f"❌ Не удалось определить координаты для адреса:\n<code>{address}</code>\n\nПопробуйте ввести адрес более подробно или используйте геопозицию.",
                    parse_mode='HTML',
                    reply_markup=markup
                )
                return
            
            # Сохраняем адрес и координаты во временное состояние для подтверждения
            self.update_user_state(user_id, 'pending_start_address', address)
            self.update_user_state(user_id, 'pending_start_lat', lat)
            self.update_user_state(user_id, 'pending_start_lon', lon)
            self.update_user_state(user_id, 'pending_start_gid', gid)
            self.update_user_state(user_id, 'state', 'confirming_start_location')
            
            # Строим ссылки на карту
            point_links = maps_service.build_point_links(lat, lon, gid)
            
            from telebot import types
            inline_markup = types.InlineKeyboardMarkup()
            inline_markup.add(
                types.InlineKeyboardButton("✅ Подтвердить", callback_data="confirm_start_address"),
                types.InlineKeyboardButton("❌ Изменить", callback_data="change_start_address")
            )
            
            reply_markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
            reply_markup.row("✍️ Ввести другой адрес")
            reply_markup.row("⬅️ Главное меню")
            
            text = (
                f"📍 <b>Проверьте адрес точки старта</b>\n\n"
                f"<b>Адрес:</b> {address}\n"
                f"<b>Координаты:</b> {lat:.6f}, {lon:.6f}\n\n"
                f"🔗 <a href=\"{point_links['2gis']}\">Открыть в 2ГИС</a> | "
                f"<a href=\"{point_links['yandex']}\">Открыть в Яндекс Картах</a>\n\n"
                f"Правильно ли определен адрес?"
            )
            
            self.bot.reply_to(message, text, parse_mode='HTML', reply_markup=reply_markup)
            self.bot.send_message(message.chat.id, "Подтвердите или измените адрес:", reply_markup=inline_markup)
            
        except Exception as e:
            logger.error(f"Ошибка геокодирования адреса точки старта: {e}", exc_info=True)
            
            from telebot import types
            markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
            markup.row("✍️ Ввести другой адрес")
            markup.row("⬅️ Главное меню")
            
            self.bot.reply_to(
                message,
                f"❌ Ошибка при определении координат: {str(e)}\n\nПопробуйте ввести адрес еще раз.",
                reply_markup=markup
            )

    def handle_confirm_start_address(self, call):
        """Подтверждение адреса точки старта"""
        user_id = call.from_user.id
        today = date.today()
        state_data = self.get_user_state(user_id)
        
        address = state_data.get('pending_start_address')
        lat = state_data.get('pending_start_lat')
        lon = state_data.get('pending_start_lon')
        gid = state_data.get('pending_start_gid')
        
        if not address or not lat or not lon:
            self.bot.answer_callback_query(call.id, "❌ Ошибка: данные не найдены")
            self.bot.send_message(call.message.chat.id, "❌ Ошибка: данные адреса не найдены. Введите адрес заново.", reply_markup=self._main_menu_markup())
            return
        
        # Сохраняем в БД
        try:
            self.db_service.save_start_location(
                user_id, 'address', address, lat, lon, None, today
            )
            
            # Очищаем временные данные
            self.update_user_state(user_id, 'pending_start_address', None)
            self.update_user_state(user_id, 'pending_start_lat', None)
            self.update_user_state(user_id, 'pending_start_lon', None)
            self.update_user_state(user_id, 'pending_start_gid', None)
            self.update_user_state(user_id, 'state', 'waiting_for_start_time')
            
            # Также сохраняем в state для обратной совместимости
            self.update_user_state(user_id, 'start_address', address)
            self.update_user_state(user_id, 'start_location', {'lat': lat, 'lon': lon})
            
            self.bot.answer_callback_query(call.id, "✅ Адрес подтвержден")
            self.bot.edit_message_text(
                f"✅ <b>Адрес подтвержден!</b>\n\n📍 {address}\n\nТеперь укажите время старта.",
                call.message.chat.id,
                call.message.message_id,
                parse_mode='HTML',
                reply_markup=None
            )
            
            from telebot import types
            markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
            markup.row("⬅️ Главное меню")
            
            text = (
                "⏰ <b>Время старта</b>\n\n"
                "Укажите время начала маршрута в формате ЧЧ:ММ\n"
                "Пример: 09:00"
            )
            self.bot.send_message(call.message.chat.id, text, parse_mode='HTML', reply_markup=markup)
            
        except Exception as e:
            logger.error(f"Ошибка сохранения адреса точки старта: {e}", exc_info=True)
            self.bot.answer_callback_query(call.id, f"❌ Ошибка: {str(e)}")
            self.bot.send_message(call.message.chat.id, f"❌ Ошибка сохранения: {str(e)}", reply_markup=self._main_menu_markup())

    def process_start_time(self, message, state_data):
        """Process start time input"""
        user_id = message.from_user.id
        text = message.text.strip()

        if text == "⬅️ Главное меню":
            self.update_user_state(user_id, 'state', None)
            self.bot.reply_to(message, "🏠 Возврат в главное меню", reply_markup=self._main_menu_markup())
            return

        try:
            start_time = datetime.strptime(text, "%H:%M").time()

            # Combine with today's date
            today = datetime.now().date()
            start_datetime = datetime.combine(today, start_time)
            
            # Обновляем время старта в БД
            start_location_data = self.db_service.get_start_location(user_id, today)
            if start_location_data:
                location_type = start_location_data.get('location_type', 'address')
                address = start_location_data.get('address')
                lat = start_location_data.get('latitude')
                lon = start_location_data.get('longitude')
                
                self.db_service.save_start_location(
                    user_id, location_type, address, lat, lon, start_datetime, today
                )
            else:
                # Если точки старта нет, создаем с адресом по умолчанию
                self.db_service.save_start_location(
                    user_id, 'address', 'Не указан', None, None, start_datetime, today
                )

            # Также сохраняем в state для обратной совместимости
            self.update_user_state(user_id, 'start_time', start_datetime.isoformat())
            self.update_user_state(user_id, 'state', None)

            # Возвращаем в меню точки старта
            self.bot.reply_to(
                message,
                f"✅ Время старта установлено: {text}\n\nТеперь можно оптимизировать маршрут командой /optimize_route",
                parse_mode='HTML',
                reply_markup=self._main_menu_markup()
            )

        except ValueError:
            self.bot.reply_to(message, "❌ Неверный формат времени. Используйте ЧЧ:ММ (например, 09:00)")

    def handle_monitor(self, message):
        """Handle /monitor command"""
        user_id = message.from_user.id
        state_data = self.get_user_state(user_id)

        # Получаем сохраненный маршрут из state (сохранен после оптимизации)
        optimized_route = state_data.get('optimized_route')
        orders = state_data.get('optimized_orders', [])
        start_location = state_data.get('start_location')
        start_time_str = state_data.get('start_time')

        if not optimized_route or not orders or not start_location or not start_time_str:
            self.bot.reply_to(message, "❌ Сначала оптимизируйте маршрут командой /optimize_route", reply_markup=self._main_menu_markup())
            return

        # Преобразуем start_time в datetime
        if isinstance(start_time_str, str):
            start_datetime = datetime.fromisoformat(start_time_str)
        else:
            start_datetime = start_time_str

        # Запустить мониторинг для этого пользователя
        self.traffic_monitor.start_monitoring(user_id, optimized_route, orders, start_location, start_datetime)
        self.bot.reply_to(message, "🚦 <b>Мониторинг пробок запущен!</b>\n\nБуду проверять пробки каждые 5 минут и уведомлять об изменениях.", parse_mode='HTML', reply_markup=self._main_menu_markup())

    def handle_stop_monitor(self, message):
        """Handle /stop_monitor command"""
        user_id = message.from_user.id
        self.traffic_monitor.stop_monitoring(user_id)
        self.bot.reply_to(message, "🛑 Мониторинг пробок остановлен", reply_markup=self._main_menu_markup())

    def handle_traffic_status(self, message):
        """Handle /traffic_status command"""
        user_id = message.from_user.id
        status = self.traffic_monitor.get_current_traffic_status(user_id)

        if status['is_monitoring']:
            last_check = status['last_check']
            if last_check:
                last_check_dt = datetime.fromisoformat(last_check)
                time_diff = datetime.now() - last_check_dt
                last_check_str = f"{time_diff.seconds // 60} мин назад"
            else:
                last_check_str = "еще не проверялось"

            text = f"🚦 <b>Статус мониторинга:</b>\n\n"
            text += f"📍 Точек маршрута: {status['route_points']}\n"
            text += f"⏰ Интервал проверки: {status['check_interval_minutes']} мин\n"
            text += f"🔍 Последняя проверка: {last_check_str}\n"
            text += f"✅ Статус: Активен"
        else:
            text = "🚦 <b>Мониторинг не активен</b>\n\nИспользуйте кнопку 🚦 Мониторинг для запуска"

        self.bot.reply_to(message, text, parse_mode='HTML', reply_markup=self._main_menu_markup())

    def handle_delivered_orders(self, message):
        """Показать список доставленных заказов"""
        user_id = message.from_user.id
        self.show_delivered_orders(user_id, message.chat.id)

    def handle_order_details_start(self, message):
        """Начало просмотра деталей заказа - компактный список в одном сообщении"""
        user_id = message.from_user.id
        today = date.today()
        
        # Загружаем из БД
        orders_data = self.db_service.get_today_orders(user_id)
        
        if not orders_data:
            self.bot.reply_to(
                message,
                "❌ Нет добавленных заказов",
                reply_markup=self._orders_menu_markup()
            )
            return
        
        # Фильтруем только не доставленные заказы
        active_orders = [od for od in orders_data if od.get('status', 'pending') != 'delivered']
        
        if not active_orders:
            self.bot.reply_to(
                message,
                "✅ Все заказы доставлены!",
                reply_markup=self._orders_menu_markup()
            )
            return
        
        # Формируем только кнопки с информацией
        from telebot import types
        
        # Сортируем по номеру заказа для удобства
        active_orders_sorted = sorted(active_orders, key=lambda x: x.get('order_number', ''))
        
        inline_markup = types.InlineKeyboardMarkup(row_width=1)
        
        for order_data in active_orders_sorted:
            order_number = order_data.get('order_number', 'Без номера')
            address = order_data.get('address', 'Адрес не указан')
            time_window = order_data.get('delivery_time_window', '')
            customer_name = order_data.get('customer_name', '')
            phone = order_data.get('phone', '')
            comment = order_data.get('comment', '')
            entrance = order_data.get('entrance_number', '')
            apartment = order_data.get('apartment_number', '')
            
            # Формируем максимально информативный текст кнопки с индикаторами заполненности
            # Формат: "№3259394 🕐13:00-16:00 👤Иван 📞+7... 📍ул..."
            
            button_parts = [f"№{order_number}"]
            
            # Время доставки
            if time_window:
                time_short = time_window.replace(" - ", "-")
                button_parts.append(f"🕐{time_short}")
            else:
                button_parts.append("🕐❌")
            
            # Имя клиента
            if customer_name:
                name_short = customer_name[:8] if len(customer_name) > 8 else customer_name
                button_parts.append(f"👤{name_short}")
            else:
                button_parts.append("👤❌")
            
            # Телефон
            if phone:
                phone_short = phone[:10] if len(phone) > 10 else phone
                button_parts.append(f"📞{phone_short}")
            else:
                button_parts.append("📞❌")
            
            # Адрес (короткий)
            short_address = address
            address_parts = address.split(',')
            if len(address_parts) >= 2:
                short_address = ','.join(address_parts[-2:]).strip()
            elif len(address_parts) == 1:
                short_address = address_parts[0].strip()
            
            # Подъезд и квартира
            location_parts = []
            if entrance:
                location_parts.append(f"🏢{entrance}")
            if apartment:
                location_parts.append(f"🚪{apartment}")
            
            # Комментарий (только если короткий)
            if comment and len(comment) <= 8:
                button_parts.append(f"💬{comment}")
            
            # Собираем все части
            button_text = " ".join(button_parts)
            
            # Добавляем адрес и подъезд/квартиру в конец, если есть место
            if location_parts:
                location_str = " ".join(location_parts)
                if len(button_text) + len(location_str) + 1 <= 64:
                    button_text += f" {location_str}"
            
            # Если адрес короткий, добавляем его
            if len(short_address) <= 15 and len(button_text) + len(short_address) + 2 <= 64:
                button_text += f" 📍{short_address[:15]}"
            
            # Обрезаем до максимума в 64 символа (лимит Telegram)
            if len(button_text) > 64:
                # Пробуем сократить адрес
                current_len = len(" ".join(button_parts))
                if location_parts:
                    location_str = " ".join(location_parts)
                    if current_len + len(location_str) + 1 <= 64:
                        button_text = " ".join(button_parts) + " " + location_str
                    else:
                        button_text = " ".join(button_parts)
                else:
                    button_text = " ".join(button_parts)
                
                # Если все еще длинно, убираем адрес и оставляем только основные поля
                if len(button_text) > 64:
                    # Оставляем только номер, время, имя, телефон
                    essential_parts = [f"№{order_number}"]
                    if time_window:
                        time_short = time_window.replace(" - ", "-")
                        essential_parts.append(f"🕐{time_short}")
                    if customer_name:
                        name_short = customer_name[:6] if len(customer_name) > 6 else customer_name
                        essential_parts.append(f"👤{name_short}")
                    if phone:
                        phone_short = phone[:8] if len(phone) > 8 else phone
                        essential_parts.append(f"📞{phone_short}")
                    button_text = " ".join(essential_parts)
            
            inline_markup.add(
                types.InlineKeyboardButton(
                    button_text,
                    callback_data=f"order_details_{order_number}"
                )
            )
        
        # Добавляем кнопку для поиска по номеру
        inline_markup.add(
            types.InlineKeyboardButton(
                "🔍 Найти по номеру",
                callback_data="search_order_by_number"
            )
        )
        
        # Добавляем кнопку для просмотра доставленных заказов, если они есть
        delivered_count = len([od for od in orders_data if od.get('status', 'pending') == 'delivered'])
        if delivered_count > 0:
            inline_markup.add(
                types.InlineKeyboardButton(
                    f"✅ Доставленные ({delivered_count})",
                    callback_data="view_delivered_orders"
                )
            )
        
        # Отправляем только заголовок и кнопки
        header_text = f"📋 <b>Заказы</b> ({len(active_orders)} шт.)\n\n💡 <i>Выберите заказ или введите номер в чат</i>"
        
        self.bot.reply_to(
            message,
            header_text,
            parse_mode='HTML',
            reply_markup=inline_markup,
            disable_web_page_preview=True
        )

    def handle_update_order_start(self, message):
        """Начало обновления заказа - запрос номера заказа"""
        user_id = message.from_user.id
        self.update_user_state(user_id, 'state', 'waiting_for_order_number')
        
        from telebot import types
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
        markup.row("⬅️ Главное меню")
        
        text = (
            "✏️ <b>Обновление заказа</b>\n\n"
            "Введите номер заказа для обновления:"
        )
        self.bot.reply_to(message, text, parse_mode='HTML', reply_markup=markup)

    def process_order_number(self, message, state_data):
        """Обработка ввода номера заказа"""
        user_id = message.from_user.id
        text = message.text.strip()
        
        if text == "⬅️ Главное меню":
            self.update_user_state(user_id, 'state', None)
            self.bot.reply_to(message, "🏠 Возврат в главное меню", reply_markup=self._main_menu_markup())
            return
        
        order_number = text
        orders = state_data.get("orders", [])
        
        # Проверяем, существует ли заказ
        order_found = False
        for order_data in orders:
            if order_data.get('order_number') == order_number:
                order_found = True
                break
        
        if not order_found:
            self.bot.reply_to(message, f"❌ Заказ №{order_number} не найден. Введите другой номер:")
            return
        
        # Сохраняем номер заказа для обновления
        self.update_user_state(user_id, 'updating_order_number', order_number)
        
        # Показываем кнопки для выбора поля
        from telebot import types
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
        markup.row("📞 Телефон", "👤 ФИО")
        markup.row("💬 Комментарий", "🏢 Подъезд")
        markup.row("🚪 Квартира", "🕐 Время доставки")
        markup.row("⬅️ Главное меню")
        
        order_info = f"Заказ №{order_number}"
        for order_data in orders:
            if order_data.get('order_number') == order_number:
                if order_data.get('customer_name'):
                    order_info += f" ({order_data.get('customer_name')})"
                break
        
        text = (
            f"✅ <b>Заказ найден: {order_info}</b>\n\n"
            "Выберите поле для обновления:"
        )
        self.bot.reply_to(message, text, parse_mode='HTML', reply_markup=markup)

    def process_order_phone(self, message, state_data):
        """Обработка ввода телефона"""
        user_id = message.from_user.id
        text = message.text.strip()
        
        if text == "⬅️ Главное меню":
            self.update_user_state(user_id, 'state', None)
            self.update_user_state(user_id, 'updating_order_number', None)
            self.bot.reply_to(message, "🏠 Возврат в главное меню", reply_markup=self._main_menu_markup())
            return
        
        order_number = state_data.get('updating_order_number')
        if not order_number:
            self.bot.reply_to(message, "❌ Ошибка: номер заказа не найден")
            return
        
        # Обновляем телефон
        self._update_order_field(user_id, order_number, 'phone', text, message)

    def process_order_name(self, message, state_data):
        """Обработка ввода ФИО"""
        user_id = message.from_user.id
        text = message.text.strip()
        
        if text == "⬅️ Главное меню":
            self.update_user_state(user_id, 'state', None)
            self.update_user_state(user_id, 'updating_order_number', None)
            self.bot.reply_to(message, "🏠 Возврат в главное меню", reply_markup=self._main_menu_markup())
            return
        
        order_number = state_data.get('updating_order_number')
        if not order_number:
            self.bot.reply_to(message, "❌ Ошибка: номер заказа не найден")
            return
        
        # Обновляем ФИО
        self._update_order_field(user_id, order_number, 'customer_name', text, message)

    def process_call_comment(self, message, state_data):
        """Обработка ввода комментария к звонку"""
        from src.database.connection import get_db_session
        from src.models.order import CallStatusDB
        
        user_id = message.from_user.id
        text = message.text.strip()
        
        if text == "⬅️ Главное меню" or text == "⏭️ Пропустить комментарий" or text == "/skip":
            self.update_user_state(user_id, 'state', None)
            self.update_user_state(user_id, 'pending_call_status_id', None)
            self.bot.reply_to(message, "✅ Комментарий пропущен", reply_markup=self._main_menu_markup())
            return
        
        call_status_id = state_data.get('pending_call_status_id')
        if not call_status_id:
            self.bot.reply_to(message, "❌ Ошибка: не найден ID звонка", reply_markup=self._main_menu_markup())
            return
        
        try:
            with get_db_session() as session:
                call_status = session.query(CallStatusDB).filter(CallStatusDB.id == call_status_id).first()
                if call_status:
                    call_status.confirmation_comment = text
                    session.commit()
                    
                    self.bot.reply_to(
                        message,
                        f"✅ <b>Комментарий сохранен</b>\n\n💬 {text}",
                        parse_mode='HTML',
                        reply_markup=self._main_menu_markup()
                    )
                else:
                    self.bot.reply_to(message, "❌ Запись о звонке не найдена", reply_markup=self._main_menu_markup())
        except Exception as e:
            logger.error(f"Ошибка при сохранении комментария: {e}", exc_info=True)
            self.bot.reply_to(message, f"❌ Ошибка: {str(e)}", reply_markup=self._main_menu_markup())
        
        self.update_user_state(user_id, 'state', None)
        self.update_user_state(user_id, 'pending_call_status_id', None)
    
    def process_search_order_by_number(self, message, state_data):
        """Обработка поиска заказа по номеру"""
        user_id = message.from_user.id
        text = message.text.strip()
        
        if text == "⬅️ Главное меню":
            self.update_user_state(user_id, 'state', None)
            self.bot.reply_to(message, "🏠 Возврат в главное меню", reply_markup=self._main_menu_markup())
            return
        
        # Проверяем, является ли текст номером заказа
        if not text.isdigit():
            self.bot.reply_to(
                message,
                "❌ Номер заказа должен содержать только цифры. Попробуйте еще раз:",
                reply_markup=self._orders_menu_markup()
            )
            return
        
        # Ищем заказ
        try:
            orders_data = self.db_service.get_today_orders(user_id)
            order_found = False
            for od in orders_data:
                if od.get('order_number') == text:
                    order_found = True
                    # Открываем детали заказа
                    self.show_order_details(user_id, text, message.chat.id)
                    self.update_user_state(user_id, 'state', None)
                    break
            
            if not order_found:
                self.bot.reply_to(
                    message,
                    f"❌ Заказ №{text} не найден. Попробуйте еще раз или вернитесь в главное меню:",
                    reply_markup=self._orders_menu_markup()
                )
        except Exception as e:
            logger.error(f"Ошибка при поиске заказа: {e}", exc_info=True)
            self.bot.reply_to(message, f"❌ Ошибка: {str(e)}", reply_markup=self._orders_menu_markup())
            self.update_user_state(user_id, 'state', None)
    
    def handle_call_confirm(self, call, call_status_id: int):
        """Обработка подтверждения звонка"""
        from src.database.connection import get_db_session
        from src.models.order import CallStatusDB
        from sqlalchemy import and_
        
        user_id = call.from_user.id
        
        try:
            with get_db_session() as session:
                # Проверяем, что звонок принадлежит этому пользователю
                call_status = session.query(CallStatusDB).filter(
                    and_(
                        CallStatusDB.id == call_status_id,
                        CallStatusDB.user_id == user_id
                    )
                ).first()
                if not call_status:
                    self.bot.answer_callback_query(call.id, "❌ Запись о звонке не найдена", show_alert=True)
                    return
                
                # Обновляем статус на confirmed
                call_status.status = "confirmed"
                session.commit()
                
                # Обновляем сообщение, убирая кнопки
                customer_info = call_status.customer_name or "Клиент"
                order_info = f"Заказ №{call_status.order_number}" if call_status.order_number else "Заказ"
                
                updated_text = (
                    f"📞 <b>Время звонка!</b>\n\n"
                    f"👤 {customer_info}\n"
                    f"📦 {order_info}\n"
                    f"📱 {call_status.phone}\n"
                    f"🕐 Время: {call_status.call_time.strftime('%H:%M')}\n\n"
                    f"✅ <b>Подтверждено</b>"
                )
                
                try:
                    self.bot.edit_message_text(
                        updated_text,
                        call.message.chat.id,
                        call.message.message_id,
                        parse_mode='HTML'
                    )
                except Exception as edit_error:
                    logger.warning(f"Ошибка обновления сообщения: {edit_error}")
                    # Если не удалось обновить, просто отвечаем на callback
                
                # Запрашиваем комментарий
                self.bot.answer_callback_query(call.id, "✅ Звонок подтвержден")
                self.update_user_state(call.from_user.id, 'state', 'waiting_for_call_comment')
                self.update_user_state(call.from_user.id, 'pending_call_status_id', call_status_id)
                
                from telebot import types
                markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
                markup.row("⏭️ Пропустить комментарий")
                markup.row("⬅️ Главное меню")
                
                self.bot.send_message(
                    call.message.chat.id,
                    "💬 <b>Введите комментарий к звонку</b> (или нажмите кнопку чтобы пропустить):",
                    parse_mode='HTML',
                    reply_markup=markup
                )
        except Exception as e:
            logger.error(f"Ошибка при подтверждении звонка: {e}", exc_info=True)
            self.bot.answer_callback_query(call.id, f"❌ Ошибка: {str(e)}", show_alert=True)
    
    def handle_call_reject(self, call, call_status_id: int):
        """Обработка отклонения звонка"""
        from src.database.connection import get_db_session
        from src.models.order import CallStatusDB
        from datetime import datetime, timedelta
        from sqlalchemy import and_
        
        user_id = call.from_user.id
        
        try:
            with get_db_session() as session:
                # Проверяем, что звонок принадлежит этому пользователю
                call_status = session.query(CallStatusDB).filter(
                    and_(
                        CallStatusDB.id == call_status_id,
                        CallStatusDB.user_id == user_id
                    )
                ).first()
                if not call_status:
                    self.bot.answer_callback_query(call.id, "❌ Запись о звонке не найдена", show_alert=True)
                    return
                
                # Увеличиваем количество попыток
                call_status.attempts += 1
                
                customer_info = call_status.customer_name or "Клиент"
                order_info = f"Заказ №{call_status.order_number}" if call_status.order_number else "Заказ"
                
                if call_status.attempts >= 3:
                    # После 3 попыток помечаем как failed
                    call_status.status = "failed"
                    call_status.next_attempt_time = None
                    session.commit()
                    
                    # Обновляем сообщение, убирая кнопки
                    updated_text = (
                        f"📞 <b>Время звонка!</b>\n\n"
                        f"👤 {customer_info}\n"
                        f"📦 {order_info}\n"
                        f"📱 {call_status.phone}\n"
                        f"🕐 Время: {call_status.call_time.strftime('%H:%M')}\n\n"
                        f"❌ <b>Недозвон</b>\nПревышено количество попыток (3)"
                    )
                    
                    try:
                        self.bot.edit_message_text(
                            updated_text,
                            call.message.chat.id,
                            call.message.message_id,
                            parse_mode='HTML'
                        )
                    except Exception as edit_error:
                        logger.warning(f"Ошибка обновления сообщения: {edit_error}")
                    
                    self.bot.answer_callback_query(call.id, "❌ Превышено количество попыток (3)")
                    self.bot.send_message(
                        call.message.chat.id,
                        f"❌ <b>Недозвон</b>\n\nЗаказ №{call_status.order_number}\nПревышено количество попыток звонка (3)",
                        parse_mode='HTML',
                        reply_markup=self._route_menu_markup()
                    )
                else:
                    # Планируем повторную попытку через 2 минуты
                    now = get_local_now()
                    if now.tzinfo is not None:
                        now = now.replace(tzinfo=None)
                    call_status.status = "rejected"
                    call_status.next_attempt_time = now + timedelta(minutes=2)
                    session.commit()
                    
                    # Обновляем сообщение, убирая кнопки
                    updated_text = (
                        f"📞 <b>Время звонка!</b>\n\n"
                        f"👤 {customer_info}\n"
                        f"📦 {order_info}\n"
                        f"📱 {call_status.phone}\n"
                        f"🕐 Время: {call_status.call_time.strftime('%H:%M')}\n\n"
                        f"❌ <b>Отклонено</b>\nПовтор через 2 минуты (попытка {call_status.attempts}/3)"
                    )
                    
                    try:
                        self.bot.edit_message_text(
                            updated_text,
                            call.message.chat.id,
                            call.message.message_id,
                            parse_mode='HTML'
                        )
                    except Exception as edit_error:
                        logger.warning(f"Ошибка обновления сообщения: {edit_error}")
                    
                    self.bot.answer_callback_query(call.id, f"❌ Отклонено. Повтор через 2 минуты (попытка {call_status.attempts}/3)")
                    self.bot.send_message(
                        call.message.chat.id,
                        f"⏰ <b>Повторный звонок запланирован</b>\n\nЗаказ №{call_status.order_number}\nПовтор через 2 минуты (попытка {call_status.attempts}/3)",
                        parse_mode='HTML',
                        reply_markup=self._route_menu_markup()
                    )
        except Exception as e:
            logger.error(f"Ошибка при отклонении звонка: {e}", exc_info=True)
            self.bot.answer_callback_query(call.id, f"❌ Ошибка: {str(e)}", show_alert=True)
    
    def process_order_comment(self, message, state_data):
        """Обработка ввода комментария"""
        user_id = message.from_user.id
        text = message.text.strip()
        
        if text == "⬅️ Главное меню":
            self.update_user_state(user_id, 'state', None)
            self.update_user_state(user_id, 'updating_order_number', None)
            self.bot.reply_to(message, "🏠 Возврат в главное меню", reply_markup=self._main_menu_markup())
            return
        
        order_number = state_data.get('updating_order_number')
        if not order_number:
            self.bot.reply_to(message, "❌ Ошибка: номер заказа не найден")
            return
        
        # Обновляем комментарий
        self._update_order_field(user_id, order_number, 'comment', text, message)

    def process_order_entrance(self, message, state_data):
        """Обработка ввода номера подъезда"""
        user_id = message.from_user.id
        text = message.text.strip()
        
        if text == "⬅️ Главное меню":
            self.update_user_state(user_id, 'state', None)
            self.update_user_state(user_id, 'updating_order_number', None)
            self.bot.reply_to(message, "🏠 Возврат в главное меню", reply_markup=self._main_menu_markup())
            return
        
        order_number = state_data.get('updating_order_number')
        if not order_number:
            self.bot.reply_to(message, "❌ Ошибка: номер заказа не найден")
            return
        
        # Обновляем подъезд
        self._update_order_field(user_id, order_number, 'entrance_number', text, message)

    def process_order_apartment(self, message, state_data):
        """Обработка ввода номера квартиры"""
        user_id = message.from_user.id
        text = message.text.strip()
        
        if text == "⬅️ Главное меню":
            self.update_user_state(user_id, 'state', None)
            self.update_user_state(user_id, 'updating_order_number', None)
            self.bot.reply_to(message, "🏠 Возврат в главное меню", reply_markup=self._main_menu_markup())
            return
        
        order_number = state_data.get('updating_order_number')
        if not order_number:
            self.bot.reply_to(message, "❌ Ошибка: номер заказа не найден")
            return
        
        # Обновляем квартиру (новое поле)
        self._update_order_field(user_id, order_number, 'apartment_number', text, message)

    def process_order_delivery_time(self, message, state_data):
        """Обработка ввода времени доставки"""
        user_id = message.from_user.id
        text = message.text.strip()
        
        if text == "⬅️ Главное меню":
            self.update_user_state(user_id, 'state', None)
            self.update_user_state(user_id, 'updating_order_number', None)
            self.bot.reply_to(message, "🏠 Возврат в главное меню", reply_markup=self._main_menu_markup())
            return
        
        order_number = state_data.get('updating_order_number')
        if not order_number:
            self.bot.reply_to(message, "❌ Ошибка: номер заказа не найден")
            return
        
        # Проверяем формат времени доставки (ЧЧ:ММ - ЧЧ:ММ)
        import re
        time_pattern = r'(\d{1,2}:\d{2})\s*-\s*(\d{1,2}:\d{2})'
        match = re.match(time_pattern, text)
        
        if not match:
            self.bot.reply_to(
                message,
                "❌ Неверный формат времени. Используйте формат ЧЧ:ММ - ЧЧ:ММ\nПример: 10:00 - 13:00",
                reply_markup=self._update_order_back_markup()
            )
            return
        
        # Обновляем время доставки
        self._update_order_field(user_id, order_number, 'delivery_time_window', text, message)
        
        # Пересчитываем время звонков для этого заказа
        state_data = self.get_user_state(user_id)
        route_summary = state_data.get('route_summary', [])
        if route_summary:
            orders = state_data.get('orders', [])
            for order_data in orders:
                if order_data.get('order_number') == order_number:
                    updated_order = Order(**order_data)
                    self._update_route_point(user_id, order_number, updated_order, MapsService(), state_data)
                    break

    def _update_order_field(self, user_id: int, order_number: str, field_name: str, field_value: str, message):
        """Обновить конкретное поле заказа"""
        today = date.today()
        
        # Загружаем заказ из БД
        orders_data = self.db_service.get_today_orders(user_id)
        
        order_found = False
        order_data = None
        for od in orders_data:
            if od.get('order_number') == order_number:
                order_found = True
                order_data = od.copy()
                break
        
        if not order_found:
            self.bot.reply_to(message, f"❌ Заказ №{order_number} не найден", reply_markup=self._main_menu_markup())
            return
        
        # Обновляем поле
        updates = {field_name: field_value}
        
        # Если обновлен подъезд, обновляем адрес
        if field_name == 'entrance_number':
            original_address = order_data['address']
            # Удаляем старый подъезд из адреса, если есть
            import re
            address_clean = re.sub(r',\s*подъезд\s+\d+', '', original_address, flags=re.IGNORECASE)
            address_clean = re.sub(r'\s+подъезд\s+\d+', '', address_clean, flags=re.IGNORECASE)
            updates['address'] = f"{address_clean}, подъезд {field_value}"
            
            # Пересчитываем геокодирование
            maps_service = MapsService()
            lat, lon, gid = maps_service.geocode_address_sync(updates['address'])
            if lat and lon:
                updates['latitude'] = lat
                updates['longitude'] = lon
                updates['gis_id'] = gid
        
        # Если обновлено время доставки, парсим его
        if field_name == 'delivery_time_window':
            temp_order = Order(**{**order_data, 'delivery_time_window': field_value})
            if temp_order.delivery_time_start:
                updates['delivery_time_start'] = temp_order.delivery_time_start
            if temp_order.delivery_time_end:
                updates['delivery_time_end'] = temp_order.delivery_time_end
        
        # Обновляем в БД
        try:
            self.db_service.update_order(user_id, order_number, updates, today)
            
            # Если обновлен телефон, обновляем call_status и call_schedule
            if field_name == 'phone':
                from src.database.connection import get_db_session
                from src.models.order import CallStatusDB
                with get_db_session() as session:
                    call_status = session.query(CallStatusDB).filter(
                        CallStatusDB.user_id == user_id,
                        CallStatusDB.order_number == order_number,
                        CallStatusDB.call_date == today
                    ).first()
                    if call_status:
                        call_status.phone = field_value
                        # Если статус был "sent" (уведомление уже отправлено), сбрасываем на pending для повторной отправки
                        if call_status.status == "sent":
                            call_status.status = "pending"
                        session.commit()
                        logger.debug(f"Обновлен телефон в call_status для заказа {order_number}: {field_value}")
                    else:
                        # Если записи нет, создаем ее (если есть маршрут)
                        route_data_check = self.db_service.get_route_data(user_id, today)
                        if route_data_check and route_data_check.get('route_points_data'):
                            # Находим время звонка из route_points_data
                            route_points_data_check = route_data_check.get('route_points_data', [])
                            route_order_check = route_data_check.get('route_order', [])
                            try:
                                order_index = route_order_check.index(order_number)
                                if order_index < len(route_points_data_check):
                                    point_data = route_points_data_check[order_index]
                                    call_time_str = point_data.get('call_time')
                                    if call_time_str:
                                        call_time = datetime.fromisoformat(call_time_str)
                                        # Создаем запись о звонке
                                        self.call_notifier.create_call_status(
                                            user_id,
                                            order_number,
                                            call_time,
                                            field_value,
                                            order_data.get('customer_name'),
                                            today
                                        )
                                        logger.debug(f"Создана запись call_status для заказа {order_number} при обновлении телефона")
                            except (ValueError, KeyError, Exception) as e:
                                logger.warning(f"Не удалось создать call_status при обновлении телефона: {e}")
            
            # Обновляем маршрут если он существует
            route_data = self.db_service.get_route_data(user_id, today)
            if route_data and (route_data.get('route_summary') or route_data.get('route_points_data')):
                # Загружаем обновленный заказ
                updated_orders_data = self.db_service.get_today_orders(user_id)
                updated_order_data = None
                for od in updated_orders_data:
                    if od.get('order_number') == order_number:
                        updated_order_data = od.copy()
                        break
                
                if updated_order_data:
                    # Если обновлены поля, влияющие на маршрут - пересчитываем маршрут
                    if field_name in ['address', 'entrance_number', 'apartment_number', 'delivery_time_window']:
                        # Преобразуем время
                        if updated_order_data.get('delivery_time_start'):
                            if isinstance(updated_order_data['delivery_time_start'], str):
                                parts = updated_order_data['delivery_time_start'].split(':')
                                if len(parts) >= 2:
                                    updated_order_data['delivery_time_start'] = time(int(parts[0]), int(parts[1]))
                        if updated_order_data.get('delivery_time_end'):
                            if isinstance(updated_order_data['delivery_time_end'], str):
                                parts = updated_order_data['delivery_time_end'].split(':')
                                if len(parts) >= 2:
                                    updated_order_data['delivery_time_end'] = time(int(parts[0]), int(parts[1]))
                        
                        try:
                            updated_order = Order(**updated_order_data)
                            
                            # Загружаем точку старта из БД
                            start_location_data = self.db_service.get_start_location(user_id, today)
                            state_data = {
                                'route_summary': route_data.get('route_summary', []),
                                'call_schedule': route_data.get('call_schedule', []),
                                'route_order': route_data.get('route_order', []),
                                'orders': updated_orders_data,  # Все заказы для контекста
                                'start_location': {'lat': start_location_data.get('latitude'), 'lon': start_location_data.get('longitude')} if start_location_data and start_location_data.get('location_type') == 'geo' else None,
                                'start_address': start_location_data.get('address') if start_location_data and start_location_data.get('location_type') == 'address' else None,
                                'start_time': start_location_data.get('start_time') if start_location_data else None
                            }
                            self._update_route_point(user_id, order_number, updated_order, MapsService(), state_data)
                        except Exception as e:
                            logger.error(f"Ошибка обновления маршрута: {e}", exc_info=True)
                    
                    # Телефон, имя, комментарий не влияют на маршрут и call_schedule
                    # call_schedule теперь формируется динамически при запросе из актуальных данных БД
            
            # Показываем кнопки для выбора следующего поля
            from telebot import types
            markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
            markup.row("📞 Телефон", "👤 ФИО")
            markup.row("💬 Комментарий", "🏢 Подъезд")
            markup.row("🚪 Квартира", "🕐 Время доставки")
            markup.row("⬅️ Главное меню")
            
            field_names = {
                'phone': 'Телефон',
                'customer_name': 'ФИО',
                'comment': 'Комментарий',
                'entrance_number': 'Подъезд',
                'apartment_number': 'Квартира',
                'delivery_time_window': 'Время доставки'
            }
            
            text = (
                f"✅ <b>{field_names.get(field_name, 'Поле')} обновлено!</b>\n\n"
                f"Заказ №{order_number}\n"
                f"Выберите следующее поле для обновления:"
            )
            self.bot.reply_to(message, text, parse_mode='HTML', reply_markup=markup)
        except Exception as e:
            logger.error(f"Ошибка обновления заказа в БД: {e}", exc_info=True)
            self.bot.reply_to(message, f"❌ Ошибка обновления заказа: {str(e)}", reply_markup=self._main_menu_markup())

    def handle_update_order(self, message):
        """Handle /update_order command"""
        user_id = message.from_user.id
        text = message.text.strip()

        try:
            # Формат: /update_order НомерЗаказа Телефон Имя [Комментарий] [подъезд:НомерПодъезда]
            parts = text.split()
            if len(parts) < 3:
                raise ValueError("Недостаточно параметров")

            command = parts[0]  # /update_order
            order_number = parts[1]
            phone = parts[2] if len(parts) > 2 else None

            # Остальные параметры
            remaining_parts = parts[3:] if len(parts) > 3 else []

            # Ищем подъезд в формате "подъезд:номер" или "подъезд номер"
            entrance_number = None
            comment_parts = []

            for i, part in enumerate(remaining_parts):
                if part.lower().startswith('подъезд:') or part.lower().startswith('подъезд'):
                    # Нашли подъезд
                    if ':' in part:
                        entrance_number = part.split(':', 1)[1].strip()
                    elif i + 1 < len(remaining_parts):
                        entrance_number = remaining_parts[i + 1]
                    break
                else:
                    comment_parts.append(part)

            customer_name = comment_parts[0] if comment_parts else None
            comment = ' '.join(comment_parts[1:]) if len(comment_parts) > 1 else None

            # Ищем заказ по номеру
            state_data = self.get_user_state(user_id)
            orders = state_data.get("orders", [])

            order_found = False
            for i, order_data in enumerate(orders):
                if order_data.get('order_number') == order_number:
                    # Обновляем информацию
                    if phone:
                        orders[i]['phone'] = phone
                    if customer_name:
                        orders[i]['customer_name'] = customer_name
                    if comment:
                        orders[i]['comment'] = comment
                    if entrance_number:
                        orders[i]['entrance_number'] = entrance_number
                        # Добавляем подъезд к адресу для более точного геокодирования
                        original_address = orders[i]['address']
                        if 'подъезд' not in original_address.lower():
                            orders[i]['address'] = f"{original_address}, подъезд {entrance_number}"

                    order_found = True
                    break

            if order_found:
                maps_service = MapsService()
                updated_order = Order(**orders[i])
                
                # Если обновлен адрес (добавлен подъезд), пересчитываем геокодирование
                if entrance_number:
                    # Пересчитываем координаты с новым адресом
                    lat, lon, gid = maps_service.geocode_address_sync(updated_order.address)
                    if lat and lon:
                        orders[i]['latitude'] = lat
                        orders[i]['longitude'] = lon
                        orders[i]['gis_id'] = gid
                
                # Сохраняем обновленные заказы
                self.update_user_state(user_id, 'orders', orders)
                
                # Получаем актуальный state_data после обновления
                updated_state_data = self.get_user_state(user_id)
                route_summary = updated_state_data.get('route_summary', [])
                
                if route_summary:
                    # Находим обновленный заказ в маршруте и обновляем только его
                    self._update_route_point(user_id, order_number, updated_order, maps_service, updated_state_data)

                update_info = []
                if phone:
                    update_info.append(f"📞 Телефон: {phone}")
                if customer_name:
                    update_info.append(f"👤 Имя: {customer_name}")
                if comment:
                    update_info.append(f"💬 Комментарий: {comment}")
                if entrance_number:
                    update_info.append(f"🏢 Подъезд: {entrance_number}")

                text = f"✅ <b>Заказ №{order_number} обновлен!</b>\n\n" + "\n".join(update_info)
                
                # Проверяем, был ли обновлен маршрут автоматически
                final_state = self.get_user_state(user_id)
                route_summary_updated = final_state.get('route_summary', [])
                if route_summary_updated:
                    text += f"\n\n✅ <b>Маршрут обновлен автоматически!</b> Используйте /view_route для просмотра."
                else:
                    if entrance_number:
                        text += f"\n\n📍 <b>Адрес обновлен! Пересчитайте маршрут командой /optimize_route</b>"
                    else:
                        text += f"\n\n💡 <b>Пересчитайте маршрут командой /optimize_route для обновления данных</b>"
            else:
                text = f"❌ Заказ №{order_number} не найден в текущем списке"

        except Exception as e:
            text = (
                f"❌ Ошибка обновления: {str(e)}\n\n"
                "📝 <b>Формат команды:</b>\n"
                "<code>/update_order НомерЗаказа Телефон Имя Комментарий подъезд:Номер</code>\n\n"
                "Примеры:\n"
                "<code>/update_order 3258104 +79991234567 Иван домофон 05 подъезд:3</code>\n"
                "<code>/update_order 3258981 +79992345678 Анна оставить у двери</code>"
            )

        self.bot.reply_to(message, text, parse_mode='HTML', reply_markup=self._main_menu_markup())

    def _update_route_point(self, user_id: int, order_number: str, updated_order: Order, maps_service: MapsService, state_data: Dict):
        """Обновить только один пункт в существующем маршруте"""
        today = date.today()
        
        # Загружаем данные из БД
        route_data = self.db_service.get_route_data(user_id, today)
        if not route_data:
            return
        
        route_points_data = route_data.get('route_points_data', [])
        call_schedule = route_data.get('call_schedule', [])
        route_order = route_data.get('route_order', [])
        
        # Проверка на старый формат
        if not route_points_data or (route_points_data and isinstance(route_points_data[0], str)):
            # Старый формат - очищаем маршрут, требуется переоптимизация
            return
        
        # Загружаем заказы из БД
        orders_data = self.db_service.get_today_orders(user_id)
        orders_dict = {od.get('order_number'): od for od in orders_data if od.get('order_number')}
        
        # Загружаем точку старта
        start_location_data = self.db_service.get_start_location(user_id, today) or {}
        if not start_location_data:
            return
        
        # Получаем время старта
        start_time = start_location_data.get('start_time')
        if not start_time:
            return
        if isinstance(start_time, str):
            start_datetime = datetime.fromisoformat(start_time)
        else:
            start_datetime = start_time
        
        # Находим позицию обновленного заказа в маршруте
        point_index = None
        if route_order:
            try:
                point_index = route_order.index(order_number)
            except ValueError:
                # Если не найден в route_order, ищем в route_points_data
                for idx, point_data in enumerate(route_points_data):
                    if point_data.get('order_number') == order_number:
                        point_index = idx
                        break
        
        if point_index is None:
            return
        
        # Находим обновленный заказ
        updated_order_in_list = updated_order
        
        # Получаем координаты старта
        if start_location_data.get('location_type') == 'geo':
            start_lat = start_location_data.get('latitude')
            start_lon = start_location_data.get('longitude')
            start_location_coords = (start_lat, start_lon) if start_lat and start_lon else None
        elif start_location_data.get('latitude') and start_location_data.get('longitude'):
            start_location_coords = (start_location_data.get('latitude'), start_location_data.get('longitude'))
        else:
            start_address = start_location_data.get('address')
            if start_address:
                start_lat, start_lon, _ = maps_service.geocode_address_sync(start_address)
                if not start_lat or not start_lon:
                    return
                start_location_coords = (start_lat, start_lon)
            else:
                return
        
        # Пересчитываем координаты обновленного заказа если нужно
        if not updated_order_in_list.latitude or not updated_order_in_list.longitude:
            lat, lon, gid = maps_service.geocode_address_sync(updated_order_in_list.address)
            if lat and lon:
                updated_order_in_list.latitude = lat
                updated_order_in_list.longitude = lon
                updated_order_in_list.gis_id = gid
        
        # Находим координаты предыдущей и следующей точек
        prev_latlon = start_location_coords
        prev_gid = None
        
        # Проходим по всем заказам до обновленного в порядке маршрута
        for i in range(point_index):
            prev_order_num = route_order[i]
            prev_order_data = orders_dict.get(prev_order_num)
            if prev_order_data:
                try:
                    prev_order = Order(**prev_order_data)
                    if prev_order.latitude and prev_order.longitude:
                        prev_latlon = (prev_order.latitude, prev_order.longitude)
                        prev_gid = prev_order.gis_id
                except Exception as e:
                    logger.error(f"Ошибка создания Order: {e}", exc_info=True)
                    continue
        
        # Пересчитываем расстояния и время только от предыдущей точки до обновленной
        if updated_order_in_list.latitude and updated_order_in_list.longitude:
            # От предыдущей до обновленной
            dist_from_prev, time_from_prev = maps_service.get_route_sync(
                prev_latlon[0], prev_latlon[1],
                updated_order_in_list.latitude, updated_order_in_list.longitude
            )
            
            # Рассчитываем время прибытия на предыдущую точку
            # Суммируем время всех сегментов от старта до предыдущей точки
            total_time_to_prev = 0
            current_prev_latlon = start_location_coords
            
            for i in range(point_index):
                prev_order_num = route_order[i]
                prev_order_data = orders_dict.get(prev_order_num)
                if prev_order_data:
                    try:
                        prev_order = Order(**prev_order_data)
                        if prev_order.latitude and prev_order.longitude:
                            # Время от текущей предыдущей точки до следующей
                            _, seg_time = maps_service.get_route_sync(
                                current_prev_latlon[0], current_prev_latlon[1],
                                prev_order.latitude, prev_order.longitude
                            )
                            total_time_to_prev += seg_time + 10  # +10 минут на доставку
                            current_prev_latlon = (prev_order.latitude, prev_order.longitude)
                    except Exception as e:
                        logger.error(f"Ошибка создания Order: {e}", exc_info=True)
                        continue
            
            # Рассчитываем время прибытия на обновленную точку
            # Время до предыдущей + время от предыдущей до обновленной + 10 минут на доставку
            arrival_time = start_datetime + timedelta(minutes=total_time_to_prev + time_from_prev + 10)
            
            # Проверяем, что время прибытия попадает в окно доставки
            window_start = None
            window_end = None
            if updated_order_in_list.delivery_time_start and updated_order_in_list.delivery_time_end:
                today = arrival_time.date()
                window_start = datetime.combine(today, updated_order_in_list.delivery_time_start)
                window_end = datetime.combine(today, updated_order_in_list.delivery_time_end)
                
                # Если прибытие раньше окна - сдвигаем на начало окна
                if arrival_time < window_start:
                    arrival_time = window_start
                # Если прибытие позже окна - оставляем как есть (но покажем предупреждение)
            
            # Формируем обновленную информацию о заказе
            order_title = f"Заказ №{updated_order_in_list.order_number}"
            if updated_order_in_list.customer_name:
                order_title += f" ({updated_order_in_list.customer_name})"
            
            # Calculate call time (40 min before delivery, but not before start of delivery window)
            call_time = arrival_time - timedelta(minutes=40)
            if window_start:
                earliest_call = window_start - timedelta(minutes=40)
                if call_time < earliest_call:
                    call_time = earliest_call
            
            # Новый компактный формат
            order_info = [f"<b>{point_index + 1}. {order_title}</b>"]
            
            # Адрес
            order_info.append(f"📍 {updated_order_in_list.address}")
            
            # Контакты (компактно)
            contact_parts = []
            if updated_order_in_list.customer_name:
                contact_parts.append(f"👤 {updated_order_in_list.customer_name}")
            if updated_order_in_list.phone:
                contact_parts.append(f"📞 {updated_order_in_list.phone}")
            if contact_parts:
                order_info.append(" | ".join(contact_parts))
            elif not updated_order_in_list.phone:
                order_info.append("📞 Телефон не указан")

            # Время доставки и статус
            if updated_order_in_list.delivery_time_window:
                arrival_status = ""
                if window_start and window_end:
                    if arrival_time < window_start:
                        arrival_status = f" ⚠️ Раньше окна"
                    elif arrival_time > window_end:
                        arrival_status = f" 🚨 Позже окна"
                    else:
                        arrival_status = f" ✅"
                
                order_info.append(f"🕐 {updated_order_in_list.delivery_time_window} | Прибытие: {arrival_time.strftime('%H:%M')}{arrival_status}")

            # Детали доставки (компактно)
            delivery_details = []
            if updated_order_in_list.entrance_number:
                delivery_details.append(f"🏢 Подъезд {updated_order_in_list.entrance_number}")
            if updated_order_in_list.apartment_number:
                delivery_details.append(f"🚪 Кв. {updated_order_in_list.apartment_number}")
            if delivery_details:
                order_info.append(" | ".join(delivery_details))
            
            # Время звонка и маршрут (компактно)
            route_info = [f"📞 Звонок: {call_time.strftime('%H:%M')}"]
            route_info.append(f"📏 {dist_from_prev:.1f} км")
            route_info.append(f"⏱️ {time_from_prev:.0f} мин")
            order_info.append(" | ".join(route_info))

            # Ссылки на карты (компактно)
            links = maps_service.build_route_links(
                prev_latlon[0], prev_latlon[1],
                updated_order_in_list.latitude, updated_order_in_list.longitude,
                prev_gid, updated_order_in_list.gis_id
            )
            point_links = maps_service.build_point_links(
                updated_order_in_list.latitude, updated_order_in_list.longitude, updated_order_in_list.gis_id
            )
            
            order_info.append(
                "🔗 <a href=\"{dg}\">Маршрут 2ГИС</a> | <a href=\"{ya}\">Яндекс</a> | "
                "<a href=\"{pdg}\">Точка 2ГИС</a> | <a href=\"{pya}\">Яндекс</a>".format(
                    dg=links["2gis"],
                    ya=links["yandex"],
                    pdg=point_links["2gis"],
                    pya=point_links["yandex"]
                )
            )

            # Комментарий (если есть)
            if updated_order_in_list.comment:
                order_info.append(f"💬 {updated_order_in_list.comment}")
            
            # Обновляем структурированные данные маршрута
            today = date.today()
            route_data = self.db_service.get_route_data(user_id, today)
            if route_data:
                route_points_data = route_data.get('route_points_data', [])
                
                # Если старый формат - очищаем и требуем переоптимизации
                if not route_points_data or (route_points_data and isinstance(route_points_data[0], str)):
                    # Старый формат - очищаем маршрут
                    self.db_service.save_route_data(
                        user_id,
                        [],  # Очищаем маршрут
                        [],
                        [],
                        0, 0, None, today
                    )
                    return
                
                # Обновляем структурированные данные для этой точки
                if point_index < len(route_points_data):
                    route_points_data[point_index] = {
                        "order_number": order_number,
                        "estimated_arrival": arrival_time.isoformat(),
                        "distance_from_previous": dist_from_prev,
                        "time_from_previous": time_from_prev,
                        "call_time": call_time.isoformat()
                    }
                
                # Пересоздаем call_schedule с актуальными данными из БД
                # Загружаем все заказы заново для актуальных данных
                all_orders_data = self.db_service.get_today_orders(user_id)
                all_orders_dict = {od.get('order_number'): od for od in all_orders_data if od.get('order_number')}
                
                # Пересоздаем call_schedule с актуальными данными
                call_schedule = []
                for idx, order_num in enumerate(route_order):
                    order_data = all_orders_dict.get(order_num)
                    if not order_data:
                        continue
                    
                    try:
                        order_obj = Order(**order_data)
                    except:
                        continue
                    
                    # Получаем время звонка из route_points_data
                    if idx < len(route_points_data):
                        point_data = route_points_data[idx]
                        try:
                            call_time_dt = datetime.fromisoformat(point_data.get('call_time'))
                            arrival_time_dt = datetime.fromisoformat(point_data.get('estimated_arrival'))
                        except:
                            continue
                        
                        # Сохраняем структурированные данные
                        call_data = {
                            "order_number": order_obj.order_number or str(order_obj.id),
                            "call_time": call_time_dt.isoformat(),
                            "arrival_time": arrival_time_dt.isoformat(),
                            "phone": order_obj.phone or None,
                            "customer_name": order_obj.customer_name or None
                        }
                        call_schedule.append(call_data)
                
                # Сохраняем обновленные данные в БД
                self.db_service.save_route_data(
                    user_id,
                    route_points_data,  # Структурированные данные
                    call_schedule,
                    route_data.get('route_order', []),
                    route_data.get('total_distance', 0),
                    route_data.get('total_time', 0),
                    route_data.get('estimated_completion'),
                    today
                )
                
                # Обновляем state
                self.update_user_state(user_id, 'route_points_data', route_points_data)
                self.update_user_state(user_id, 'call_schedule', call_schedule)

    def handle_reset_day(self, message):
        """Обработчик кнопки 'Сбросить текущий день'"""
        user_id = message.from_user.id
        today = date.today()
        
        # Подтверждение
        from telebot import types
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("✅ Да, сбросить", callback_data=f"reset_day_confirm"))
        markup.add(types.InlineKeyboardButton("❌ Отмена", callback_data=f"reset_day_cancel"))
        
        self.bot.reply_to(
            message,
            f"⚠️ <b>Внимание!</b>\n\n"
            f"Вы уверены, что хотите удалить все данные за сегодня ({today.strftime('%d.%m.%Y')})?\n\n"
            f"Будут удалены:\n"
            f"• Все заказы\n"
            f"• Точка старта\n"
            f"• Маршрут и график звонков\n\n"
            f"Это действие нельзя отменить!",
            parse_mode='HTML',
            reply_markup=markup
        )

    def handle_reset_day_confirm(self, call):
        """Подтверждение сброса дня"""
        user_id = call.from_user.id
        today = date.today()
        
        try:
            result = self.db_service.delete_all_data_by_date(user_id, today)
            
            # Также очищаем user_states
            self.update_user_state(user_id, 'orders', [])
            self.update_user_state(user_id, 'start_location', None)
            self.update_user_state(user_id, 'start_time', None)
            self.update_user_state(user_id, 'route_summary', None)
            self.update_user_state(user_id, 'call_schedule', None)
            self.update_user_state(user_id, 'route_order', None)
            self.update_user_state(user_id, 'state', None)
            
            self.bot.answer_callback_query(call.id, "✅ Данные за сегодня удалены")
            self.bot.edit_message_text(
                f"✅ <b>Данные за сегодня удалены</b>\n\n"
                f"Удалено:\n"
                f"• Заказов: {result['orders']}\n"
                f"• Точек старта: {result['locations']}\n"
                f"• Маршрутов: {result['routes']}",
                call.message.chat.id,
                call.message.message_id,
                parse_mode='HTML',
                reply_markup=None
            )
            self.bot.send_message(
                call.message.chat.id,
                "🏠 Главное меню",
                reply_markup=self._main_menu_markup()
            )
        except Exception as e:
            self.bot.answer_callback_query(call.id, f"❌ Ошибка: {str(e)}")
            self.bot.edit_message_text(
                f"❌ Ошибка при удалении данных: {str(e)}",
                call.message.chat.id,
                call.message.message_id,
                parse_mode='HTML'
            )

    def send_traffic_alert(self, user_id: int, changes: List[Dict], total_time: float):
        """Отправить уведомление о изменениях в пробках"""
        alert_text = "🚨 <b>ВНИМАНИЕ! Изменения в пробках!</b>\n\n"

        for change in changes:
            order = change['order']
            alert_text += f"📍 <b>Заказ {change['step']}:</b> {order.customer_name}\n"
            alert_text += f"   🚦 Задержка: {change['delay']:.1f} мин\n"
            alert_text += f"   📊 Текущее время: {change['current_time']:.1f} мин\n"

        alert_text += f"   📈 Общее увеличение времени: {total_time:.0f} мин"
        alert_text += "\n💡 Рекомендуется пересчитать маршрут: /optimize_route"

        try:
            self.bot.send_message(user_id, alert_text, parse_mode='HTML')
        except Exception as e:
            logger.warning(f"Не удалось отправить уведомление пользователю {user_id}: {e}", exc_info=True)
