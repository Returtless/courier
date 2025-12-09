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
            "📝 <b>Обновление заказов:</b>\n"
            "/update_order - Добавить контакты и подъезд\n\n"
            "Выберите действие:"
        )
        self.bot.reply_to(message, text, parse_mode='HTML')

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
            "Отправляйте по одному заказу в сообщении.\n"
            "Когда закончите, отправьте /done"
        )
        self.bot.reply_to(message, text, parse_mode='HTML')

    def handle_set_start(self, message):
        """Handle /set_start command"""
        user_id = message.from_user.id
        self.update_user_state(user_id, 'state', 'waiting_for_start_location')

        # Создаем клавиатуру с вариантами
        from telebot import types
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
        markup.add(
            types.KeyboardButton("📍 Отправить геопозицию", request_location=True),
            types.KeyboardButton("✍️ Ввести адрес вручную")
        )

        text = (
            "📍 <b>Точка старта</b>\n\n"
            "Выберите способ установки точки старта:\n"
            "• 📍 <b>Отправить геопозицию</b> - точнее и быстрее\n"
            "• ✍️ <b>Ввести адрес вручную</b> - если геопозиция недоступна"
        )
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

        if (not start_address and not start_location) or not start_time_str:
            self.bot.reply_to(message, "❌ Не установлена точка старта. Используйте /set_start")
            return

        # Convert data back to Order objects
        orders = [Order(**order_data) for order_data in orders_data]
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
                start_lat, start_lon = maps_service.geocode_address_sync(start_address)
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

            for i, point in enumerate(optimized_route.points, 1):
                order = point.order

                # Определяем заголовок заказа
                if order.order_number:
                    order_title = f"Заказ №{order.order_number}"
                    if order.customer_name:
                        order_title += f" ({order.customer_name})"
                else:
                    order_title = order.customer_name or 'Клиент'

                # Формируем информацию о заказе
                order_info = [
                    f"{i}. {order_title}",
                    f"   📍 {order.address}"
                ]

                if order.phone:
                    order_info.append(f"   📞 {order.phone}")

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

                order_info.extend([
                    f"   📏 Расстояние: {point.distance_from_previous:.1f} км",
                    f"   ⏱️ Время в пути: {point.time_from_previous:.0f} мин"
                ])

                if order.comment:
                    order_info.append(f"   📝 {order.comment}")

                route_summary.append("\n".join(order_info))

                # Calculate call time (40 min before delivery, but not before start of delivery window)
                call_time = point.estimated_arrival - timedelta(minutes=40)

                # If order has time window, ensure call is not too early
                if order.delivery_time_start:
                    today = point.estimated_arrival.date()
                    window_start = datetime.combine(today, order.delivery_time_start)
                    earliest_call = window_start - timedelta(minutes=40)

                    if call_time < earliest_call:
                        call_time = earliest_call

                # Формируем информацию для звонка
                call_info = order.order_number or order.customer_name or 'Клиент'
                time_info = f"к {point.estimated_arrival.strftime('%H:%M')}"
                if order.phone:
                    call_schedule.append(f"📞 {call_time.strftime('%H:%M')} - {call_info} ({order.phone}) - {time_info}")
                else:
                    call_schedule.append(f"📞 {call_time.strftime('%H:%M')} - {call_info} (телефон не указан) - {time_info}")

            # Save to state
            self.update_user_state(user_id, 'route_summary', route_summary)
            self.update_user_state(user_id, 'call_schedule', call_schedule)

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

            self.bot.reply_to(message, summary_text, parse_mode='HTML')

        except Exception as e:
            self.bot.reply_to(message, f"❌ Ошибка оптимизации: {str(e)}")

    def handle_view_route(self, message):
        """Handle /view_route command"""
        user_id = message.from_user.id
        route_summary = self.get_user_state(user_id).get("route_summary", [])

        if not route_summary:
            self.bot.reply_to(message, "❌ Маршрут не оптимизирован. Используйте /optimize_route")
            return

        # Send in chunks
        chunk_size = 3
        for i in range(0, len(route_summary), chunk_size):
            chunk = route_summary[i:i + chunk_size]
            text = f"<b>Маршрут (заказы {i+1}-{min(i+chunk_size, len(route_summary))}):</b>\n\n" + "\n\n".join(chunk)
            self.bot.reply_to(message, text, parse_mode='HTML')

    def handle_calls(self, message):
        """Handle /calls command"""
        user_id = message.from_user.id
        call_schedule = self.get_user_state(user_id).get("call_schedule", [])

        if not call_schedule:
            self.bot.reply_to(message, "❌ График звонков не сформирован. Оптимизируйте маршрут сначала")
            return

        text = "<b>📞 График звонков клиентам:</b>\n\n" + "\n".join(call_schedule)
        self.bot.reply_to(message, text, parse_mode='HTML')

    def handle_text_message(self, message):
        """Handle text messages based on user state"""
        user_id = message.from_user.id
        state_data = self.get_user_state(user_id)
        current_state = state_data.get('state')

        if current_state == 'waiting_for_orders':
            self.process_order(message, state_data)
        elif current_state == 'waiting_for_start_location':
            self.process_start_location_choice(message, state_data)
        elif current_state == 'waiting_for_start_address':
            self.process_start_location(message, state_data)
        elif current_state == 'waiting_for_start_time':
            self.process_start_time(message, state_data)

    def process_order(self, message, state_data):
        """Process order input"""
        text = message.text.strip()
        user_id = message.from_user.id

        if text == "/done":
            orders = state_data.get("orders", [])
            if not orders:
                self.bot.reply_to(message, "❌ Нет добавленных заказов")
                return

            self.update_user_state(user_id, 'state', None)
            self.bot.reply_to(message, f"✅ Добавлено {len(orders)} заказов\n\nТеперь укажите точку старта командой /set_start")
            return

        # Parse order
        try:
            # Проверяем формат: если содержит "|" - это расширенный формат
            if "|" in text:
                # Формат: Имя|Телефон|Адрес|Комментарий
                parts = text.split("|")
                if len(parts) < 3:
                    raise ValueError("Недостаточно данных в расширенном формате")

                # Создаем объект Order для автоматического парсинга
                order = Order(
                    customer_name=parts[0].strip() if len(parts) > 0 else None,
                    phone=parts[1].strip() if len(parts) > 1 else None,
                    address=parts[2].strip(),
                    comment=parts[3].strip() if len(parts) > 3 else None
                )
                order_data = order.dict()
            else:
                # Формат: Время НомерЗаказа Адрес
                # Пример: "10:00 - 13:00 3258104 г Санкт-Петербург, ул Манчестерская, д 3 стр 1"

                # Ищем паттерн времени (ЧЧ:ММ - ЧЧ:ММ)
                import re
                time_pattern = r'(\d{1,2}:\d{2}\s*-\s*\d{1,2}:\d{2})'
                time_match = re.search(time_pattern, text)

                if time_match:
                    time_window = time_match.group(1).strip()
                    # Убираем время из текста, чтобы остался номер заказа и адрес
                    remaining_text = text.replace(time_window, '').strip()

                    # Ищем номер заказа (число в начале)
                    order_num_match = re.match(r'(\d+)\s+', remaining_text)
                    if order_num_match:
                        order_number = order_num_match.group(1)
                        address = remaining_text[order_num_match.end():].strip()
                    else:
                        # Если номер не найден, берем весь текст как адрес
                        order_number = None
                        address = remaining_text
                else:
                    # Если время не найдено, весь текст считаем адресом
                    time_window = None
                    order_number = None
                    address = text

        # Создаем объект Order для автоматического парсинга времени
        order = Order(
            address=address,
            order_number=order_number,
            delivery_time_window=time_window
        )
        order_data = order.dict()

            # Add to orders
            orders = state_data.get("orders", [])
            orders.append(order_data)
            self.update_user_state(user_id, 'orders', orders)

            # Формируем информативное сообщение о добавленном заказе
            if order_data['order_number']:
                order_info = f"Заказ №{order_data['order_number']}"
                if order_data['delivery_time_window']:
                    order_info += f" ({order_data['delivery_time_window']})"
            else:
                order_info = order_data['customer_name'] or 'Клиент'

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

    def process_start_location_choice(self, message, state_data):
        """Process choice between location and address input"""
        user_id = message.from_user.id
        choice = message.text.strip()

        if choice == "✍️ Ввести адрес вручную":
            self.update_user_state(user_id, 'state', 'waiting_for_start_address')
            # Убираем клавиатуру
            from telebot import types
            markup = types.ReplyKeyboardRemove()
            text = (
                "📝 <b>Ввод адреса</b>\n\n"
                "Введите адрес точки старта:\n"
                "Пример: ул. Ленина, д.10"
            )
            self.bot.reply_to(message, text, parse_mode='HTML', reply_markup=markup)

        elif choice == "📍 Отправить геопозицию":
            from telebot import types
            markup = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
            button = types.KeyboardButton("📍 Отправить геопозицию", request_location=True)
            markup.add(button)

            text = (
                "📍 <b>Отправка геопозиции</b>\n\n"
                "Нажмите кнопку ниже, чтобы отправить ваше текущее местоположение:"
            )
            self.bot.reply_to(message, text, parse_mode='HTML', reply_markup=markup)

        else:
            # Пользователь ввел адрес напрямую
            self.process_start_location(message, state_data)

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

            # Убираем клавиатуру
            from telebot import types
            markup = types.ReplyKeyboardRemove()

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

        self.update_user_state(user_id, 'start_address', address)
        self.update_user_state(user_id, 'state', 'waiting_for_start_time')

        text = (
            "⏰ <b>Время старта</b>\n\n"
            "Укажите время начала маршрута в формате ЧЧ:ММ\n"
            "Пример: 09:00"
        )
        self.bot.reply_to(message, text, parse_mode='HTML')

    def process_start_time(self, message, state_data):
        """Process start time input"""
        user_id = message.from_user.id

        try:
            start_time_str = message.text.strip()
            start_time = datetime.strptime(start_time_str, "%H:%M").time()

            # Combine with today's date
            today = datetime.now().date()
            start_datetime = datetime.combine(today, start_time)

            self.update_user_state(user_id, 'start_time', start_datetime.isoformat())
            self.update_user_state(user_id, 'state', None)

            self.bot.reply_to(message, f"✅ Точка старта установлена: {message.text}\n\nТеперь можно оптимизировать маршрут командой /optimize_route", parse_mode='HTML')

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
            self.bot.reply_to(message, "❌ Сначала оптимизируйте маршрут командой /optimize_route")
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
            estimated_arrival = start_datetime.replace(hour=10+i, minute=0)
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
        self.bot.reply_to(message, "🚦 <b>Мониторинг пробок запущен!</b>\n\nБуду проверять пробки каждые 5 минут и уведомлять об изменениях.", parse_mode='HTML')

    def handle_stop_monitor(self, message):
        """Handle /stop_monitor command"""
        self.traffic_monitor.stop_monitoring()
        self.bot.reply_to(message, "🛑 Мониторинг пробок остановлен")

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

        self.bot.reply_to(message, text, parse_mode='HTML')

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
                # Сохраняем обновленные заказы
                self.update_user_state(user_id, 'orders', orders)

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
                if entrance_number:
                    text += f"\n\n📍 <b>Адрес обновлен для точного маршрута!</b>"
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

        self.bot.reply_to(message, text, parse_mode='HTML')

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
