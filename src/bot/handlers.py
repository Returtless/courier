import telebot
from typing import Dict, List
from datetime import datetime, time, timedelta
from src.models.order import Order
from src.services.maps_service import MapsService
from src.services.route_optimizer import RouteOptimizer
from src.services.traffic_monitor import TrafficMonitor
# from src.services.llm_service import LLMService  # Пока отключено


class CourierBot:
    def __init__(self, bot: telebot.TeleBot, llm_service=None):
        self.bot = bot
        self.llm_service = llm_service
        self.traffic_monitor = TrafficMonitor(MapsService())
        self.setup_traffic_callbacks()
        self.user_states = {}  # user_id -> state data

    @staticmethod
    def _main_menu_markup():
        from telebot import types
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
        markup.row("➕ Добавить заказы", "📍 Точка старта")
        markup.row("▶️ Оптимизировать", "🗺️ Маршрут")
        markup.row("📞 Звонки", "ℹ️ Детали заказа")
        markup.row("✅ Доставленные")
        markup.row("🚦 Мониторинг", "🛑 Стоп мониторинг")
        markup.row("ℹ️ Статус пробок")
        return markup

    @staticmethod
    def _orders_menu_markup():
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
        def traffic_change_callback(changes, total_time):
            # Отправить уведомление всем пользователям с активными маршрутами
            for user_id, state in self.user_states.items():
                if state.get('route_summary'):
                    try:
                        self.send_traffic_alert(user_id, changes, total_time)
                    except Exception as e:
                        print(f"Ошибка отправки уведомления пользователю {user_id}: {e}")

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
        self.bot.reply_to(message, text, parse_mode='HTML', reply_markup=self._orders_menu_markup())

    def handle_set_start(self, message):
        """Handle /set_start command"""
        user_id = message.from_user.id
        state_data = self.get_user_state(user_id)
        
        # Проверяем, есть ли уже установленная точка старта
        start_address = state_data.get("start_address")
        start_location = state_data.get("start_location")
        start_time_str = state_data.get("start_time")
        
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
        user_id = message.from_user.id
        state_data = self.get_user_state(user_id)

        orders_data = state_data.get("orders", [])
        start_address = state_data.get("start_address")
        start_location = state_data.get("start_location")  # координаты из геопозиции
        start_time_str = state_data.get("start_time")

        if not orders_data:
            self.bot.reply_to(message, "❌ Нет добавленных заказов. Добавьте их командой /add_orders")
            return

        # Фильтруем доставленные заказы
        active_orders_data = [od for od in orders_data if od.get('status', 'pending') != 'delivered']
        
        if not active_orders_data:
            self.bot.reply_to(message, "❌ Нет активных заказов для оптимизации. Все заказы доставлены.")
            return

        if (not start_address and not start_location) or not start_time_str:
            self.bot.reply_to(message, "❌ Не установлена точка старта. Используйте /set_start")
            return

        # Convert data back to Order objects (только активные заказы)
        orders = [Order(**order_data) for order_data in active_orders_data]
        start_datetime = datetime.fromisoformat(start_time_str)

        self.bot.reply_to(message, "🔄 Оптимизирую маршрут...")

        try:
            # Initialize services
            maps_service = MapsService()

            # Get start location coordinates
            if start_location:
                # Используем координаты из геопозиции
                start_lat, start_lon = start_location['lat'], start_location['lon']
                start_location_coords = (start_lat, start_lon)
                location_description = f"геопозиции ({start_lat:.6f}, {start_lon:.6f})"
            elif start_address:
                # Geocode address
                start_lat, start_lon, _ = maps_service.geocode_address_sync(start_address)
                if not start_lat or not start_lon:
                    self.bot.reply_to(message, f"❌ Не удалось определить координаты точки старта: {start_address}")
                    return
                start_location_coords = (start_lat, start_lon)
                location_description = f"адреса: {start_address}"
            else:
                self.bot.reply_to(message, "❌ Не удалось получить координаты точки старта")
                return

            # Initialize route optimizer
            route_optimizer = RouteOptimizer(maps_service)
            optimized_route = route_optimizer.optimize_route_sync(
                orders, start_location_coords, start_datetime
            )

            # Build route summary
            route_summary = []
            call_schedule = []

            prev_latlon = start_location_coords
            prev_gid = None
            for i, point in enumerate(optimized_route.points, 1):
                order = point.order

                # Определяем заголовок заказа
                if order.order_number:
                    order_title = f"Заказ №{order.order_number}"
                    if order.customer_name:
                        order_title += f" ({order.customer_name})"
                else:
                    order_title = order.customer_name or 'Клиент'

                # Calculate call time (40 min before delivery, but not before start of delivery window)
                call_time = point.estimated_arrival - timedelta(minutes=40)

                # If order has time window, ensure call is not too early
                if order.delivery_time_start:
                    today = point.estimated_arrival.date()
                    window_start = datetime.combine(today, order.delivery_time_start)
                    earliest_call = window_start - timedelta(minutes=40)

                    if call_time < earliest_call:
                        call_time = earliest_call

                # Формируем информацию о заказе
                order_info = [
                    f"{i}. {order_title}",
                    f"   📍 {order.address}"
                ]

                # Полные данные клиента
                if order.customer_name:
                    order_info.append(f"   👤 {order.customer_name}")
                if order.phone:
                    order_info.append(f"   📞 {order.phone}")
                else:
                    order_info.append(f"   📞 Телефон не указан")

                if order.delivery_time_window:
                    order_info.append(f"   🕐 Время доставки: {order.delivery_time_window}")

                    # Проверяем, попадает ли прибытие в окно доставки
                    if order.delivery_time_start and order.delivery_time_end:
                        today = point.estimated_arrival.date()
                        window_start = datetime.combine(today, order.delivery_time_start)
                        window_end = datetime.combine(today, order.delivery_time_end)

                        if point.estimated_arrival < window_start:
                            order_info.append(f"   ⚠️ Раннее прибытие: {point.estimated_arrival.strftime('%H:%M')} (окно с {window_start.strftime('%H:%M')})")
                        elif point.estimated_arrival > window_end:
                            order_info.append(f"   🚨 Позднее прибытие: {point.estimated_arrival.strftime('%H:%M')} (окно до {window_end.strftime('%H:%M')})")
                        else:
                            order_info.append(f"   ✅ В окне доставки: {point.estimated_arrival.strftime('%H:%M')}")

                if order.entrance_number:
                    order_info.append(f"   🏢 Подъезд: {order.entrance_number}")
                if order.apartment_number:
                    order_info.append(f"   🚪 Квартира: {order.apartment_number}")
                
                # Время звонка
                order_info.append(f"   📞 Звонок: {call_time.strftime('%H:%M')} (доставка {point.estimated_arrival.strftime('%H:%M')})")

                # Ссылки на маршрут (2ГИС/Яндекс)
                if order.latitude and order.longitude:
                    # Ссылка на маршрут от предыдущей точки
                    links = maps_service.build_route_links(
                        prev_latlon[0],
                        prev_latlon[1],
                        order.latitude,
                        order.longitude,
                        prev_gid,
                        order.gis_id
                    )
                    # Ссылки на точку
                    point_links = maps_service.build_point_links(order.latitude, order.longitude, order.gis_id)

                    order_info.append(
                        "🔗 Маршрут: <a href=\"{dg}\">2ГИС</a> | <a href=\"{ya}\">Яндекс</a>".format(
                            dg=links["2gis"],
                            ya=links["yandex"]
                        )
                    )
                    order_info.append(
                        "📍 Точка: <a href=\"{dg}\">2ГИС</a> | <a href=\"{ya}\">Яндекс</a>".format(
                            dg=point_links["2gis"],
                            ya=point_links["yandex"]
                        )
                    )

                    # Обновляем prev_latlon для следующей точки
                    prev_latlon = (order.latitude, order.longitude)
                    prev_gid = order.gis_id

                order_info.extend([
                    f"   📏 Расстояние: {point.distance_from_previous:.1f} км",
                    f"   ⏱️ Время в пути: {point.time_from_previous:.0f} мин"
                ])

                if order.comment:
                    order_info.append(f"   📝 {order.comment}")

                route_summary.append("\n".join(order_info))

                # Формируем информацию для графика звонков
                call_info = order.order_number or order.customer_name or 'Клиент'
                if order.customer_name:
                    call_info = f"{order.customer_name} (№{order.order_number})" if order.order_number else order.customer_name
                time_info = f"к {point.estimated_arrival.strftime('%H:%M')}"
                if order.phone:
                    call_schedule.append(f"📞 {call_time.strftime('%H:%M')} - {call_info} ({order.phone}) - {time_info}")
                else:
                    call_schedule.append(f"📞 {call_time.strftime('%H:%M')} - {call_info} (телефон не указан) - {time_info}")

            # Save to state
            self.update_user_state(user_id, 'route_summary', route_summary)
            self.update_user_state(user_id, 'call_schedule', call_schedule)
            # Сохраняем порядок заказов в маршруте для быстрого поиска
            route_order = [point.order.order_number for point in optimized_route.points]
            self.update_user_state(user_id, 'route_order', route_order)

            # Send summary
            summary_text = (
                f"✅ <b>Маршрут оптимизирован!</b>\n\n"
                f"📊 Всего заказов: {len(optimized_route.points)}\n"
                f"📏 Общее расстояние: {optimized_route.total_distance:.1f} км\n"
                f"⏱️ Общее время: {optimized_route.total_time:.0f} мин\n"
                f"🏁 Завершение: {optimized_route.estimated_completion.strftime('%H:%M')}\n\n"
                f"<b>Маршрут:</b>\n" + "\n\n".join(route_summary[:3])
            )

            if len(route_summary) > 3:
                summary_text += f"\n... и ещё {len(route_summary) - 3} заказов"

            self.bot.reply_to(message, summary_text, parse_mode='HTML', reply_markup=self._main_menu_markup())

        except Exception as e:
            self.bot.reply_to(message, f"❌ Ошибка оптимизации: {str(e)}", reply_markup=self._main_menu_markup())

    def handle_view_route(self, message):
        """Handle /view_route command"""
        user_id = message.from_user.id
        route_summary = self.get_user_state(user_id).get("route_summary", [])

        if not route_summary:
            self.bot.reply_to(message, "❌ Маршрут не оптимизирован. Используйте /optimize_route", reply_markup=self._main_menu_markup())
            return

        # Send in chunks
        chunk_size = 3
        for i in range(0, len(route_summary), chunk_size):
            chunk = route_summary[i:i + chunk_size]
            text = f"<b>Маршрут (заказы {i+1}-{min(i+chunk_size, len(route_summary))}):</b>\n\n" + "\n\n".join(chunk)
            self.bot.reply_to(message, text, parse_mode='HTML', reply_markup=self._main_menu_markup())

    def handle_calls(self, message):
        """Handle /calls command"""
        user_id = message.from_user.id
        call_schedule = self.get_user_state(user_id).get("call_schedule", [])

        if not call_schedule:
            self.bot.reply_to(message, "❌ График звонков не сформирован. Оптимизируйте маршрут сначала", reply_markup=self._main_menu_markup())
            return

        text = "<b>📞 График звонков клиентам:</b>\n\n" + "\n".join(call_schedule)
        self.bot.reply_to(message, text, parse_mode='HTML', reply_markup=self._main_menu_markup())

    def handle_text_message(self, message):
        """Handle text messages based on user state"""
        user_id = message.from_user.id
        state_data = self.get_user_state(user_id)
        current_state = state_data.get('state')

        # Глобальные кнопки без состояния
        if not current_state:
            text = message.text.strip()
            if text == "➕ Добавить заказы":
                return self.handle_add_orders(message)
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
            if text == "🗺️ Маршрут":
                return self.handle_view_route(message)
            if text == "📞 Звонки":
                return self.handle_calls(message)
            if text == "ℹ️ Детали заказа":
                return self.handle_order_details_start(message)
            if text == "✅ Доставленные":
                return self.handle_delivered_orders(message)
            if text == "🚦 Мониторинг":
                return self.handle_monitor(message)
            if text == "🛑 Стоп мониторинг":
                return self.handle_stop_monitor(message)
            if text == "ℹ️ Статус пробок":
                return self.handle_traffic_status(message)
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

    def process_order(self, message, state_data):
        """Process order input"""
        text = message.text.strip()
        user_id = message.from_user.id

        if text == "/done" or text == "✅ Готово":
            orders = state_data.get("orders", [])
            if not orders:
                self.bot.reply_to(message, "❌ Нет добавленных заказов", reply_markup=self._orders_menu_markup())
                return

            self.update_user_state(user_id, 'state', None)
            self.bot.reply_to(
                message,
                f"✅ Добавлено {len(orders)} заказов\n\nТеперь укажите точку старта",
                reply_markup=self._main_menu_markup()
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
                    customer_name=parts[0].strip() if len(parts) > 0 else None,
                    phone=parts[1].strip() if len(parts) > 1 else None,
                    address=parts[2].strip(),
                    comment=parts[3].strip() if len(parts) > 3 else None
                )
                return order.dict()

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
                order_number=order_number,
                delivery_time_window=time_window
            )
            return order.dict()

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
            self.show_order_details(user_id, order_number, call.message.chat.id)
            self.bot.answer_callback_query(call.id)
        elif callback_data == "view_delivered_orders":
            # Показать доставленные заказы
            self.show_delivered_orders(user_id, call.message.chat.id)
            self.bot.answer_callback_query(call.id)
        elif callback_data.startswith("mark_delivered_"):
            # Пометить заказ как доставленный
            order_number = callback_data.replace("mark_delivered_", "")
            self.mark_order_delivered(user_id, order_number, call.message.chat.id)
            self.bot.answer_callback_query(call.id, "✅ Заказ помечен как доставленный")

    def show_order_details(self, user_id: int, order_number: str, chat_id: int):
        """Показать детали заказа с кнопкой Доставлен"""
        state_data = self.get_user_state(user_id)
        orders = state_data.get("orders", [])
        
        order_found = False
        order_data = None
        for od in orders:
            if od.get('order_number') == order_number:
                order_found = True
                order_data = od
                break
        
        if not order_found:
            self.bot.send_message(chat_id, f"❌ Заказ №{order_number} не найден")
            return
        
        # Показываем детали заказа
        order = Order(**order_data)
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
        
        self.bot.send_message(chat_id, "\n".join(details), parse_mode='HTML', reply_markup=reply_markup)
        self.bot.send_message(chat_id, "Нажмите кнопку ниже, чтобы пометить заказ как доставленный:", reply_markup=inline_markup)

    def mark_order_delivered(self, user_id: int, order_number: str, chat_id: int):
        """Пометить заказ как доставленный"""
        state_data = self.get_user_state(user_id)
        orders = state_data.get("orders", [])
        
        order_found = False
        for i, order_data in enumerate(orders):
            if order_data.get('order_number') == order_number:
                orders[i]['status'] = 'delivered'
                order_found = True
                break
        
        if order_found:
            # Сохраняем обновленные заказы
            self.update_user_state(user_id, 'orders', orders)
            
            # Очищаем маршрут, так как заказ доставлен
            self.update_user_state(user_id, 'route_summary', [])
            self.update_user_state(user_id, 'call_schedule', [])
            self.update_user_state(user_id, 'route_order', [])
            
            self.bot.send_message(
                chat_id,
                f"✅ Заказ №{order_number} помечен как доставленный и исключен из маршрута",
                reply_markup=self._main_menu_markup()
            )
        else:
            self.bot.send_message(chat_id, f"❌ Заказ №{order_number} не найден")

    def show_delivered_orders(self, user_id: int, chat_id: int):
        """Показать список доставленных заказов"""
        state_data = self.get_user_state(user_id)
        orders = state_data.get("orders", [])
        
        delivered_orders = [od for od in orders if od.get('status', 'pending') == 'delivered']
        
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

        if state_data.get('state') == 'waiting_for_start_location':
            lat = message.location.latitude
            lon = message.location.longitude

            # Сохраняем координаты вместо адреса
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
        address = message.text.strip()

        if address == "⬅️ Главное меню":
            self.update_user_state(user_id, 'state', None)
            self.bot.reply_to(message, "🏠 Возврат в главное меню", reply_markup=self._main_menu_markup())
            return

        self.update_user_state(user_id, 'start_address', address)
        self.update_user_state(user_id, 'state', 'waiting_for_start_time')

        from telebot import types
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
        markup.row("⬅️ Главное меню")

        text = (
            "⏰ <b>Время старта</b>\n\n"
            "Укажите время начала маршрута в формате ЧЧ:ММ\n"
            "Пример: 09:00"
        )
        self.bot.reply_to(message, text, parse_mode='HTML', reply_markup=markup)

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

        route_summary = state_data.get('route_summary', [])
        orders_data = state_data.get('orders', [])
        start_time_str = state_data.get('start_time')

        if not route_summary or not orders_data:
            self.bot.reply_to(message, "❌ Сначала оптимизируйте маршрут командой /optimize_route", reply_markup=self._main_menu_markup())
            return

        # Восстановить данные маршрута
        orders = [Order(**order_data) for order_data in orders_data]
        start_location = (55.7558, 37.6173)  # Default Moscow center, should be saved
        start_datetime = datetime.fromisoformat(start_time_str)

        # Создать объект маршрута для мониторинга
        from src.models.order import OptimizedRoute, RoutePoint
        points = []
        for i, order_data in enumerate(orders_data, 1):
            order = Order(**order_data)
            # Примерные данные, в реальности нужно сохранять полную информацию
            estimated_arrival = start_datetime + timedelta(minutes=30 * i)
            point = RoutePoint(
                order=order,
                estimated_arrival=estimated_arrival,
                distance_from_previous=5.0,
                time_from_previous=15.0
            )
            points.append(point)

        route = OptimizedRoute(
            points=points,
            total_distance=25.0,
            total_time=120.0,
            estimated_completion=start_datetime + timedelta(hours=2)
        )

        # Запустить мониторинг
        self.traffic_monitor.start_monitoring(route, orders, start_location, start_datetime)
        self.bot.reply_to(message, "🚦 <b>Мониторинг пробок запущен!</b>\n\nБуду проверять пробки каждые 5 минут и уведомлять об изменениях.", parse_mode='HTML', reply_markup=self._main_menu_markup())

    def handle_stop_monitor(self, message):
        """Handle /stop_monitor command"""
        self.traffic_monitor.stop_monitoring()
        self.bot.reply_to(message, "🛑 Мониторинг пробок остановлен", reply_markup=self._main_menu_markup())

    def handle_traffic_status(self, message):
        """Handle /traffic_status command"""
        status = self.traffic_monitor.get_current_traffic_status()

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
            text = "🚦 <b>Мониторинг не активен</b>\n\nИспользуйте /monitor для запуска"

        self.bot.reply_to(message, text, parse_mode='HTML', reply_markup=self._main_menu_markup())

    def handle_delivered_orders(self, message):
        """Показать список доставленных заказов"""
        user_id = message.from_user.id
        self.show_delivered_orders(user_id, message.chat.id)

    def handle_order_details_start(self, message):
        """Начало просмотра деталей заказа - показ списка заказов"""
        user_id = message.from_user.id
        state_data = self.get_user_state(user_id)
        orders = state_data.get("orders", [])
        
        if not orders:
            self.bot.reply_to(
                message,
                "❌ Нет добавленных заказов",
                reply_markup=self._main_menu_markup()
            )
            return
        
        # Фильтруем только не доставленные заказы
        active_orders = [od for od in orders if od.get('status', 'pending') != 'delivered']
        
        if not active_orders:
            self.bot.reply_to(
                message,
                "✅ Все заказы доставлены!",
                reply_markup=self._main_menu_markup()
            )
            return
        
        # Формируем список заказов
        text = "ℹ️ <b>Список заказов</b>\n\n"
        text += "Выберите заказ для просмотра деталей:\n\n"
        
        # Создаем inline клавиатуру с номерами заказов
        from telebot import types
        inline_markup = types.InlineKeyboardMarkup()
        
        for i, order_data in enumerate(active_orders):
            order_number = order_data.get('order_number', 'Без номера')
            address = order_data.get('address', 'Адрес не указан')
            time_window = order_data.get('delivery_time_window', 'Время не указано')
            
            # Ограничиваем длину адреса для читаемости
            address_short = address[:40] + "..." if len(address) > 40 else address
            
            text += f"{i+1}. <b>№{order_number}</b>\n"
            text += f"   📍 {address_short}\n"
            text += f"   🕐 {time_window}\n\n"
            
            # Добавляем inline кнопку для каждого заказа
            inline_markup.add(
                types.InlineKeyboardButton(
                    f"№{order_number}",
                    callback_data=f"order_details_{order_number}"
                )
            )
        
        # Добавляем кнопку для просмотра доставленных заказов
        delivered_count = len([od for od in orders if od.get('status', 'pending') == 'delivered'])
        if delivered_count > 0:
            inline_markup.add(
                types.InlineKeyboardButton(
                    f"✅ Доставленные ({delivered_count})",
                    callback_data="view_delivered_orders"
                )
            )
        
        # Reply клавиатура для возврата
        reply_markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
        reply_markup.row("⬅️ Главное меню")
        
        self.bot.reply_to(message, text, parse_mode='HTML', reply_markup=reply_markup)
        # Отправляем отдельное сообщение с inline кнопками
        self.bot.send_message(
            user_id,
            "Нажмите на номер заказа для просмотра деталей:",
            reply_markup=inline_markup
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
        state_data = self.get_user_state(user_id)
        orders = state_data.get("orders", [])
        
        order_found = False
        order_index = None
        for i, order_data in enumerate(orders):
            if order_data.get('order_number') == order_number:
                # Обновляем поле
                orders[i][field_name] = field_value
                order_index = i
                
                # Если обновлен подъезд, обновляем адрес
                if field_name == 'entrance_number':
                    original_address = orders[i]['address']
                    if 'подъезд' not in original_address.lower():
                        orders[i]['address'] = f"{original_address}, подъезд {field_value}"
                
                # Если обновлен адрес (подъезд), пересчитываем геокодирование
                if field_name == 'entrance_number':
                    maps_service = MapsService()
                    updated_order = Order(**orders[i])
                    lat, lon, gid = maps_service.geocode_address_sync(updated_order.address)
                    if lat and lon:
                        orders[i]['latitude'] = lat
                        orders[i]['longitude'] = lon
                        orders[i]['gis_id'] = gid
                
                # Если обновлено время доставки, парсим его
                if field_name == 'delivery_time_window':
                    updated_order = Order(**orders[i])
                    # Order.__init__ автоматически парсит delivery_time_window
                    if updated_order.delivery_time_start:
                        orders[i]['delivery_time_start'] = updated_order.delivery_time_start.isoformat()
                    if updated_order.delivery_time_end:
                        orders[i]['delivery_time_end'] = updated_order.delivery_time_end.isoformat()
                
                order_found = True
                break
        
        if order_found and order_index is not None:
            # Сохраняем обновленные заказы
            self.update_user_state(user_id, 'orders', orders)
            
            # Обновляем маршрут если он существует
            updated_state = self.get_user_state(user_id)
            route_summary = updated_state.get('route_summary', [])
            if route_summary:
                updated_order = Order(**orders[order_index])
                self._update_route_point(user_id, order_number, updated_order, MapsService(), updated_state)
            
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
        else:
            self.bot.reply_to(message, f"❌ Заказ №{order_number} не найден")

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
        # Получаем актуальные данные
        current_state = self.get_user_state(user_id)
        route_summary = current_state.get('route_summary', [])
        call_schedule = current_state.get('call_schedule', [])
        orders_data = current_state.get('orders', [])
        start_location = current_state.get('start_location')
        start_address = current_state.get('start_address')
        start_time_str = current_state.get('start_time')
        
        if not route_summary or not start_time_str:
            return
        
        # Находим позицию обновленного заказа в маршруте
        route_order = state_data.get('route_order', [])
        point_index = None
        if route_order:
            try:
                point_index = route_order.index(order_number)
            except ValueError:
                # Если не найден в route_order, ищем в route_summary
                for idx, summary_line in enumerate(route_summary):
                    if order_number in summary_line:
                        point_index = idx
                        break
        else:
            # Fallback: ищем в route_summary
            for idx, summary_line in enumerate(route_summary):
                if order_number in summary_line:
                    point_index = idx
                    break
        
        if point_index is None:
            return
        
        # Получаем все заказы для восстановления контекста
        orders_dict = {od.get('order_number'): Order(**od) for od in orders_data}
        
        # Находим обновленный заказ
        updated_order_in_list = orders_dict.get(order_number)
        if not updated_order_in_list:
            return
        
        # Получаем порядок заказов в маршруте
        route_order = current_state.get('route_order', [])
        if not route_order:
            # Если нет сохраненного порядка, используем порядок из route_summary
            route_order = [od.get('order_number') for od in orders_data]
        
        # Получаем координаты старта
        if start_location:
            start_lat, start_lon = start_location['lat'], start_location['lon']
            start_location_coords = (start_lat, start_lon)
        elif start_address:
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
            prev_order = orders_dict.get(prev_order_num)
            if prev_order and prev_order.latitude and prev_order.longitude:
                prev_latlon = (prev_order.latitude, prev_order.longitude)
                prev_gid = prev_order.gis_id
        
        # Пересчитываем расстояния и время только от предыдущей точки до обновленной
        if updated_order_in_list.latitude and updated_order_in_list.longitude:
            # От предыдущей до обновленной
            dist_from_prev, time_from_prev = maps_service.get_route_sync(
                prev_latlon[0], prev_latlon[1],
                updated_order_in_list.latitude, updated_order_in_list.longitude
            )
            
            # Восстанавливаем start_datetime для расчета времени прибытия
            start_datetime = datetime.fromisoformat(start_time_str)
            
            # Рассчитываем время прибытия на предыдущую точку
            # Суммируем время всех сегментов от старта до предыдущей точки
            total_time_to_prev = 0
            current_prev_latlon = start_location_coords
            
            for i in range(point_index):
                prev_order_num = route_order[i]
                prev_order = orders_dict.get(prev_order_num)
                if prev_order and prev_order.latitude and prev_order.longitude:
                    # Время от текущей предыдущей точки до следующей
                    _, seg_time = maps_service.get_route_sync(
                        current_prev_latlon[0], current_prev_latlon[1],
                        prev_order.latitude, prev_order.longitude
                    )
                    total_time_to_prev += seg_time + 10  # +10 минут на доставку
                    current_prev_latlon = (prev_order.latitude, prev_order.longitude)
            
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
            
            order_info = [
                f"{point_index + 1}. {order_title}",
                f"   📍 {updated_order_in_list.address}"
            ]
            
            if updated_order_in_list.customer_name:
                order_info.append(f"   👤 {updated_order_in_list.customer_name}")
            if updated_order_in_list.phone:
                order_info.append(f"   📞 {updated_order_in_list.phone}")
            else:
                order_info.append(f"   📞 Телефон не указан")
            
            if updated_order_in_list.delivery_time_window:
                order_info.append(f"   🕐 Время доставки: {updated_order_in_list.delivery_time_window}")
                
                # Проверяем, попадает ли прибытие в окно доставки
                if window_start and window_end:
                    if arrival_time < window_start:
                        order_info.append(f"   ⚠️ Раннее прибытие: {arrival_time.strftime('%H:%M')} (окно с {window_start.strftime('%H:%M')})")
                    elif arrival_time > window_end:
                        order_info.append(f"   🚨 Позднее прибытие: {arrival_time.strftime('%H:%M')} (окно до {window_end.strftime('%H:%M')})")
                    else:
                        order_info.append(f"   ✅ В окне доставки: {arrival_time.strftime('%H:%M')}")
            
            if updated_order_in_list.entrance_number:
                order_info.append(f"   🏢 Подъезд: {updated_order_in_list.entrance_number}")
            if updated_order_in_list.apartment_number:
                order_info.append(f"   🚪 Квартира: {updated_order_in_list.apartment_number}")
            
            order_info.append(f"   📞 Звонок: {call_time.strftime('%H:%M')} (доставка {arrival_time.strftime('%H:%M')})")
            
            # Ссылки
            links = maps_service.build_route_links(
                prev_latlon[0], prev_latlon[1],
                updated_order_in_list.latitude, updated_order_in_list.longitude,
                prev_gid, updated_order_in_list.gis_id
            )
            point_links = maps_service.build_point_links(
                updated_order_in_list.latitude, updated_order_in_list.longitude, updated_order_in_list.gis_id
            )
            
            order_info.append(
                "🔗 Маршрут: <a href=\"{dg}\">2ГИС</a> | <a href=\"{ya}\">Яндекс</a>".format(
                    dg=links["2gis"],
                    ya=links["yandex"]
                )
            )
            order_info.append(
                "📍 Точка: <a href=\"{dg}\">2ГИС</a> | <a href=\"{ya}\">Яндекс</a>".format(
                    dg=point_links["2gis"],
                    ya=point_links["yandex"]
                )
            )
            
            order_info.extend([
                f"   📏 Расстояние: {dist_from_prev:.1f} км",
                f"   ⏱️ Время в пути: {time_from_prev:.0f} мин"
            ])
            
            if updated_order_in_list.comment:
                order_info.append(f"   📝 {updated_order_in_list.comment}")
            
            # Обновляем route_summary
            route_summary[point_index] = "\n".join(order_info)
            
            # Обновляем call_schedule
            call_info = updated_order_in_list.order_number or updated_order_in_list.customer_name or 'Клиент'
            if updated_order_in_list.customer_name:
                call_info = f"{updated_order_in_list.customer_name} (№{updated_order_in_list.order_number})" if updated_order_in_list.order_number else updated_order_in_list.customer_name
            time_info = f"к {arrival_time.strftime('%H:%M')}"
            if updated_order_in_list.phone:
                call_schedule[point_index] = f"📞 {call_time.strftime('%H:%M')} - {call_info} ({updated_order_in_list.phone}) - {time_info}"
            else:
                call_schedule[point_index] = f"📞 {call_time.strftime('%H:%M')} - {call_info} (телефон не указан) - {time_info}"
            
            # Сохраняем обновленные данные
            self.update_user_state(user_id, 'route_summary', route_summary)
            self.update_user_state(user_id, 'call_schedule', call_schedule)

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
            print(f"Не удалось отправить уведомление пользователю {user_id}: {e}")
