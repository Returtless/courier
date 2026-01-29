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
        
        # Загружаем через RouteService
        start_location_dto = self.parent.route_service.get_start_location(user_id, today)
        start_location_data = start_location_dto.dict() if start_location_dto else None
        
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
            
            # Сохраняем через RouteService
            from src.application.dto.route_dto import StartLocationDTO
            location_dto = StartLocationDTO(
                location_type='geo',
                latitude=lat,
                longitude=lon
            )
            self.parent.route_service.save_start_location(user_id, location_dto, today)
            
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
        
        # Сохраняем через RouteService
        from src.application.dto.route_dto import StartLocationDTO
        location_dto = StartLocationDTO(
            location_type='address',
            address=pending_location['address'],
            latitude=pending_location['lat'],
            longitude=pending_location['lon']
        )
        self.parent.route_service.save_start_location(user_id, location_dto, today)
        
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
        
        # Обновляем время старта через RouteService
        from src.application.dto.route_dto import StartLocationDTO
        existing_location = self.parent.route_service.get_start_location(user_id, today)
        if existing_location:
            existing_location.start_time = start_datetime
            self.parent.route_service.save_start_location(user_id, existing_location, today)
        
        self.bot.send_message(
            message.chat.id,
            f"✅ Время старта установлено: {start_datetime.strftime('%H:%M')}",
            reply_markup=self.parent._main_menu_markup(user_id)
        )
        
        self.parent.clear_user_state(user_id)
    
    # ==================== ОПТИМИЗАЦИЯ МАРШРУТА ====================
    
    def handle_optimize_route(self, message):
        """Handle /optimize_route command"""
        user_id = message.from_user.id
        today = date.today()

        logger.info(f"🚀 Начало оптимизации для user_id={user_id}, date={today}")

        # Проверяем наличие точки старта и времени старта
        logger.debug(f"Проверяю точку старта для user_id={user_id}")
        start_location = self.parent.route_service.get_start_location(user_id, today)
        logger.debug(f"Получена точка старта: {start_location}")
        if not start_location:
            logger.warning(f"Точка старта не найдена для user_id={user_id}")
            self.bot.reply_to(
                message,
                "❌ Не установлена точка старта. Используйте кнопку 📍 Точка старта",
                reply_markup=self.parent._route_menu_markup()
            )
            return

        logger.debug(f"Проверяю время старта: {start_location.start_time}")
        if not start_location.start_time:
            logger.warning(f"Время старта не установлено для user_id={user_id}")
            self.bot.reply_to(
                message,
                "❌ Не установлено время старта. Используйте кнопку 📍 Точка старта",
                reply_markup=self.parent._route_menu_markup()
            )
            return

        status_msg = self.bot.reply_to(
            message,
            "🔄 <b>Начинаю оптимизацию маршрута...</b>\n\n⏳ Загружаю данные...",
            parse_mode='HTML'
        )

        try:
            logger.info(f"Вызываю optimize_route для user_id={user_id}, date={today}")
            import sys
            sys.stdout.flush()  # Принудительно сбрасываем буфер вывода
            result = self.parent.route_service.optimize_route(user_id, today)
            logger.info(f"Оптимизация завершена, результат: success={result.success if result else None}, "
                       f"error_message={result.error_message if result and result.error_message else None}, "
                       f"route={result.route is not None if result else False}")
            sys.stdout.flush()
        except Exception as e:
            import sys
            import traceback
            error_traceback = traceback.format_exc()
            logger.error(f"❌ ИСКЛЮЧЕНИЕ при оптимизации маршрута для user_id={user_id}: {e}", exc_info=True)
            logger.error(f"Полный traceback:\n{error_traceback}")
            sys.stdout.flush()
            try:
                self.bot.edit_message_text(
                    f"❌ Ошибка оптимизации маршрута: {str(e)}\n\nПроверьте логи для подробностей.",
                    message.chat.id,
                    status_msg.message_id,
                    parse_mode='HTML'
                )
            except Exception as bot_error:
                logger.error(f"Ошибка отправки сообщения об ошибке: {bot_error}")
                # Попытка отправить новое сообщение
                try:
                    self.bot.send_message(
                        message.chat.id,
                        f"❌ Ошибка оптимизации маршрута: {str(e)}",
                        parse_mode='HTML'
                    )
                except Exception as send_error:
                    logger.error(f"Не удалось отправить сообщение об ошибке: {send_error}")
            return

        if not result or not result.success or not result.route:
            error_text = result.error_message if result and result.error_message else "Не удалось оптимизировать маршрут"
            logger.warning(f"⚠️ Оптимизация не удалась для user_id={user_id}: {error_text}")
            try:
                # Пытаемся отредактировать сообщение с клавиатурой
                self.bot.edit_message_text(
                    f"❌ <b>Не удалось оптимизировать маршрут</b>\n\n{error_text}",
                    message.chat.id,
                    status_msg.message_id,
                    parse_mode='HTML',
                    reply_markup=self.parent._route_menu_markup()
                )
            except Exception as edit_error:
                # Если не получилось с клавиатурой, отправляем новое сообщение
                logger.warning(f"Не удалось отредактировать сообщение с клавиатурой: {edit_error}, отправляю новое")
                try:
                    self.bot.send_message(
                        message.chat.id,
                        f"❌ <b>Не удалось оптимизировать маршрут</b>\n\n{error_text}",
                        parse_mode='HTML',
                        reply_markup=self.parent._route_menu_markup()
                    )
                except Exception as send_error:
                    logger.error(f"Не удалось отправить сообщение об ошибке: {send_error}")
            return

        # Успешная оптимизация – показываем маршрут через существующий механизм
        from types import SimpleNamespace
        self.bot.edit_message_text(
            "✅ <b>Маршрут оптимизирован</b>\n\n📋 Показываю маршрут...",
            message.chat.id,
            status_msg.message_id,
            parse_mode='HTML'
        )
        # Создаем fake_message с message_id для корректной работы bot.reply_to()
        # Используем message_id из исходного сообщения, если есть, иначе из status_msg
        msg_id = getattr(message, 'message_id', None) or status_msg.message_id
        fake_message = SimpleNamespace(
            from_user=message.from_user, 
            chat=message.chat,
            message_id=msg_id
        )
        self.handle_show_route(fake_message)
        return

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
                    prev_gid = start_location_data.get('gis_id')
                    logger.debug(f"Инициализирован prev_latlon из start_location (geo): {prev_latlon}")
                elif start_location_data.get('latitude') and start_location_data.get('longitude'):
                    prev_latlon = (start_location_data.get('latitude'), start_location_data.get('longitude'))
                    prev_gid = start_location_data.get('gis_id')
                    logger.debug(f"Инициализирован prev_latlon из start_location: {prev_latlon}")
            else:
                logger.warning("⚠️ start_location_data пустой, prev_latlon не инициализирован - для первого заказа не будет ссылок на маршрут")
        
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
            
            # Окно из маршрута (после синхронизации близких адресов) переопределяет данные из БД
            order_data_display = dict(order_data)
            route_window = point_data.get('delivery_time_window')
            if not route_window and point_data.get('delivery_time_start') and point_data.get('delivery_time_end'):
                route_window = f"{point_data['delivery_time_start']} - {point_data['delivery_time_end']}"
            if route_window:
                order_data_display['delivery_time_window'] = route_window
            
            # Преобразуем данные заказа
            try:
                lat = order_data_display.get('latitude')
                lon = order_data_display.get('longitude')
                logger.debug(f"Заказ {order_number}: lat={lat}, lon={lon}, gis_id={order_data_display.get('gis_id')}")
                
                order = Order(**order_data_display)
                
                # Проверяем координаты после создания Order
                if not order.latitude or not order.longitude:
                    logger.warning(f"⚠️ Заказ {order_number} без координат после создания Order: lat={order.latitude}, lon={order.longitude} (было в данных: lat={lat}, lon={lon})")
            except Exception as e:
                logger.error(f"Ошибка создания Order из данных для заказа {order_number}: {e}", exc_info=True)
                logger.debug(f"Данные заказа {order_number}: {order_data}")
                continue
            
            # Парсим время (может быть строкой или datetime)
            try:
                estimated_arrival = point_data['estimated_arrival']
                if isinstance(estimated_arrival, str):
                    estimated_arrival = datetime.fromisoformat(estimated_arrival)
                elif not isinstance(estimated_arrival, datetime):
                    logger.error(f"Неверный тип estimated_arrival: {type(estimated_arrival)}")
                    continue
                
                call_time = point_data.get('call_time')
                if call_time is None:
                    logger.warning(f"call_time отсутствует для заказа {order_number}")
                    continue
                if isinstance(call_time, str):
                    call_time = datetime.fromisoformat(call_time)
                elif not isinstance(call_time, datetime):
                    logger.error(f"Неверный тип call_time: {type(call_time)}")
                    continue
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
                    elif estimated_arrival > window_end + timedelta(minutes=1):
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

            # Ссылки на карты (в тексте, как было раньше)
            logger.debug(f"🔍 Проверка координат для заказа {order.order_number}: lat={order.latitude}, lon={order.longitude}, gis_id={order.gis_id}")
            
            if order.latitude and order.longitude:
                try:
                    # Ссылки на точку (всегда показываем)
                    point_links = maps_service.build_point_links(order.latitude, order.longitude, order.gis_id)
                    logger.debug(f"✅ Созданы ссылки на точку для заказа {order.order_number}: 2ГИС={point_links.get('2gis')[:50] if point_links.get('2gis') else None}...")
                    
                    # Ссылки на маршрут (только если есть предыдущая точка)
                    if prev_latlon:
                        links = maps_service.build_route_links(
                            prev_latlon[0],
                            prev_latlon[1],
                            order.latitude,
                            order.longitude,
                            prev_gid,
                            order.gis_id
                        )
                        logger.debug(f"✅ Созданы ссылки на маршрут для заказа {order.order_number}: prev_latlon={prev_latlon}")
                        
                        map_links_text = (
                            "🔗 <a href=\"{dg}\">Маршрут 2ГИС</a> | <a href=\"{ya}\">Яндекс</a> | "
                            "<a href=\"{pdg}\">Точка 2ГИС</a> | <a href=\"{pya}\">Яндекс</a>".format(
                                dg=links["2gis"],
                                ya=links["yandex"],
                                pdg=point_links["2gis"],
                                pya=point_links["yandex"]
                            )
                        )
                        order_info.append(map_links_text)
                        logger.info(f"✅ Добавлены ссылки на карты для заказа {order.order_number}: маршрут + точка (4 ссылки)")
                    else:
                        # Для первого заказа - только кнопки точки (если нет предыдущей точки)
                        map_links_text = (
                            "🔗 <a href=\"{pdg}\">Точка 2ГИС</a> | <a href=\"{pya}\">Яндекс</a>".format(
                                pdg=point_links["2gis"],
                                pya=point_links["yandex"]
                            )
                        )
                        order_info.append(map_links_text)
                        logger.info(f"✅ Добавлены ссылки на карты для заказа {order.order_number}: только точка (2 ссылки, нет prev_latlon)")

                    # Обновляем prev_latlon для следующей точки
                    prev_latlon = (order.latitude, order.longitude)
                    prev_gid = order.gis_id
                except Exception as e:
                    logger.error(f"❌ Ошибка создания ссылок на карты для заказа {order.order_number}: {e}", exc_info=True)
            else:
                logger.warning(f"⚠️ Заказ {order.order_number} без координат: lat={order.latitude}, lon={order.longitude} (координаты не будут отображены)")

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
        
        logger.info(f"🚀 handle_show_route вызван для user_id={user_id}, date={today}")
        import sys
        sys.stdout.flush()
        
        # Загружаем через RouteService
        logger.debug(f"Загружаю маршрут через RouteService для user_id={user_id}")
        try:
            route_dto = self.parent.route_service.get_route(user_id, today)
            logger.info(f"Получен route_dto: {route_dto is not None}")
            if route_dto:
                logger.info(f"  - route_points: {len(route_dto.route_points) if route_dto.route_points else 0}")
                logger.info(f"  - route_order: {len(route_dto.route_order) if route_dto.route_order else 0}")
        except Exception as e:
            import traceback
            logger.error(f"❌ Ошибка получения маршрута: {e}\n{traceback.format_exc()}")
            sys.stdout.flush()
            try:
                self.bot.reply_to(message, f"❌ Ошибка загрузки маршрута: {str(e)}", reply_markup=self.parent._route_menu_markup())
            except Exception:
                pass
            return
        
        if not route_dto:
            logger.warning(f"⚠️ Маршрут не найден для user_id={user_id}, date={today}")
            try:
                self.bot.reply_to(message, "❌ Маршрут не оптимизирован. Используйте кнопку ▶️ Оптимизировать", reply_markup=self.parent._route_menu_markup())
            except Exception as e:
                logger.error(f"Ошибка отправки сообщения: {e}")
            return
        
        # Преобразуем RouteDTO в формат для совместимости
        logger.debug("Преобразую RouteDTO в формат для совместимости")
        route_points_data = []
        for point in route_dto.route_points:
            try:
                route_points_data.append({
                    'order_number': point.order_number,
                    'estimated_arrival': point.estimated_arrival.isoformat() if point.estimated_arrival else None,
                    'call_time': point.call_time.isoformat() if point.call_time else None,
                    'distance_from_previous': point.distance_from_previous,
                    'time_from_previous': point.time_from_previous
                })
            except Exception as e:
                logger.error(f"Ошибка преобразования точки маршрута {point.order_number}: {e}")
        
        route_order = route_dto.route_order
        logger.info(f"Преобразовано {len(route_points_data)} точек маршрута, route_order: {len(route_order) if route_order else 0}")
        
        if not route_points_data or not route_order:
            logger.warning(f"⚠️ Пустой маршрут: route_points_data={len(route_points_data)}, route_order={len(route_order) if route_order else 0}")
            try:
                self.bot.reply_to(message, "❌ Маршрут не оптимизирован. Используйте кнопку ▶️ Оптимизировать", reply_markup=self.parent._route_menu_markup())
            except Exception as e:
                logger.error(f"Ошибка отправки сообщения: {e}")
            return
        
        # Загружаем заказы через OrderService
        logger.debug("Загружаю заказы через OrderService")
        try:
            orders_data = self.parent.get_today_orders_dict(user_id, today)
            logger.info(f"Загружено заказов: {len(orders_data)}")
        except Exception as e:
            import traceback
            logger.error(f"❌ Ошибка загрузки заказов: {e}\n{traceback.format_exc()}")
            sys.stdout.flush()
            try:
                self.bot.reply_to(message, f"❌ Ошибка загрузки заказов: {str(e)}", reply_markup=self.parent._route_menu_markup())
            except Exception:
                pass
            return
        
        # Фильтруем только активные (не доставленные) заказы
        active_orders_data = [od for od in orders_data if od.get('status', 'pending') != 'delivered']
        orders_dict = {od.get('order_number'): od for od in active_orders_data if od.get('order_number')}
        logger.info(f"Активных заказов: {len(active_orders_data)}, в словаре: {len(orders_dict)}")
        
        # Фильтруем route_points_data, оставляя только активные заказы
        active_order_numbers = set(orders_dict.keys())
        active_route_points_data = [p for p in route_points_data if p.get('order_number') in active_order_numbers]
        logger.info(f"Активных точек маршрута: {len(active_route_points_data)}")
        
        if not active_route_points_data:
            logger.info("Все заказы доставлены")
            try:
                self.bot.reply_to(message, "✅ Все заказы доставлены", reply_markup=self.parent._route_menu_markup())
            except Exception as e:
                logger.error(f"Ошибка отправки сообщения: {e}")
            return
        
        # Загружаем точку старта через RouteService
        logger.debug("Загружаю точку старта")
        start_location_data = self.parent.get_start_location_dict(user_id, today) or {}
        logger.info(f"Точка старта: {start_location_data is not None and bool(start_location_data)}")
        
        # Форматируем маршрут только для активных заказов
        logger.debug("Форматирую маршрут")
        try:
            maps_service = MapsService()
            route_summary = self._format_route_summary(user_id, active_route_points_data, orders_dict, start_location_data, maps_service)
            logger.info(f"Отформатировано {len(route_summary) if route_summary else 0} элементов маршрута")
        except Exception as e:
            import traceback
            logger.error(f"❌ Ошибка форматирования маршрута: {e}\n{traceback.format_exc()}")
            sys.stdout.flush()
            try:
                self.bot.reply_to(message, f"❌ Ошибка форматирования маршрута: {str(e)}", reply_markup=self.parent._route_menu_markup())
            except Exception:
                pass
            return
        
        if not route_summary:
            logger.warning("⚠️ route_summary пустой после форматирования")
            try:
                self.bot.reply_to(message, "❌ Не удалось сформировать маршрут", reply_markup=self.parent._route_menu_markup())
            except Exception as e:
                logger.error(f"Ошибка отправки сообщения: {e}")
            return
        
        # Отправляем маршрут по частям (по 3 заказа в сообщении) - БЕЗ кнопок
        logger.info(f"Отправляю маршрут ({len(route_summary)} элементов) пользователю {user_id}")
        text_header = "<b>🗺️ Маршрут доставки</b>\n\n"
        
        try:
            from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
            
            # Первое сообщение с заголовком и первыми заказами
            first_chunk = text_header + "\n\n".join(item["text"] for item in route_summary[:3])
            logger.debug(f"Отправляю первое сообщение (длина: {len(first_chunk)} символов)")
            self.bot.reply_to(message, first_chunk, parse_mode='HTML', reply_markup=self.parent._route_menu_markup(), disable_web_page_preview=True)
            logger.info("✅ Первое сообщение отправлено")
            
            # Остальные заказы по 5 в сообщении
            for i in range(3, len(route_summary), 5):
                chunk = "\n\n".join(item["text"] for item in route_summary[i:i+5])
                logger.debug(f"Отправляю сообщение {i//5 + 2} (элементы {i}-{min(i+5, len(route_summary))})")
                self.bot.send_message(message.chat.id, chunk, parse_mode='HTML', disable_web_page_preview=True)
            
            logger.info(f"✅ Маршрут успешно отправлен ({len(route_summary)} элементов)")
            sys.stdout.flush()
        except Exception as e:
            import traceback
            logger.error(f"❌ Ошибка отправки маршрута: {e}\n{traceback.format_exc()}")
            sys.stdout.flush()
            try:
                self.bot.reply_to(message, f"❌ Ошибка отправки маршрута: {str(e)}", reply_markup=self.parent._route_menu_markup())
            except Exception:
                pass
    
    def handle_show_calls(self, message):
        """Показать график звонков"""
        user_id = message.from_user.id
        today = date.today()
        
        # Загружаем через RouteService
        route_data = self.parent.get_route_data_dict(user_id, today)
        if not route_data:
            self.bot.reply_to(message, "❌ Маршрут не оптимизирован. Используйте кнопку ▶️ Оптимизировать", reply_markup=self.parent._route_menu_markup())
            return
        
        call_schedule = route_data.get('call_schedule', [])
        
        # Если графика звонков нет, но маршрут оптимизирован - строим график
        if not call_schedule:
            route_points_data = route_data.get('route_points_data', [])
            if route_points_data:
                logger.info(f"📞 График звонков не найден, но маршрут есть. Строю график из {len(route_points_data)} точек...")
                call_schedule = self._build_call_schedule_from_route_points(route_points_data, user_id, today)
                
                if call_schedule:
                    # Сохраняем график звонков в БД
                    self._save_call_schedule_to_db(user_id, today, call_schedule, route_data)
                    # Обновляем route_data для дальнейшей обработки
                    route_data['call_schedule'] = call_schedule
                    logger.info(f"✅ График звонков построен и сохранен: {len(call_schedule)} записей")
                else:
                    self.bot.reply_to(message, "❌ Не удалось построить график звонков. Проверьте, что у всех точек маршрута указано время прибытия.", reply_markup=self.parent._route_menu_markup())
                    return
            else:
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
    
    def _build_call_schedule_from_route_points(
        self,
        route_points_data: List[Dict],
        user_id: int,
        order_date: date
    ) -> List[Dict]:
        """
        Построить график звонков из точек маршрута
        
        Args:
            route_points_data: Список точек маршрута
            user_id: ID пользователя
            order_date: Дата маршрута
            
        Returns:
            Список записей графика звонков
        """
        from datetime import timedelta
        from src.services.user_settings_service import UserSettingsService
        
        call_schedule = []
        settings_service = UserSettingsService()
        user_settings = settings_service.get_settings(user_id)
        call_advance_minutes = user_settings.call_advance_minutes if user_settings else 10
        
        # Получаем информацию о заказах для добавления phone и customer_name
        from src.database.connection import get_db_session
        from src.models.order import OrderDB
        
        orders_dict = {}
        try:
            with get_db_session() as session:
                for point_data in route_points_data:
                    order_number = point_data.get('order_number')
                    if order_number and order_number not in orders_dict:
                        order_db = session.query(OrderDB).filter(
                            OrderDB.user_id == user_id,
                            OrderDB.order_number == order_number,
                            OrderDB.order_date == order_date
                        ).first()
                        if order_db:
                            orders_dict[order_number] = {
                                'phone': order_db.phone or 'Не указан',
                                'customer_name': order_db.customer_name or ''
                            }
        except Exception as e:
            logger.warning(f"Ошибка получения данных заказов для графика звонков: {e}")
        
        for point_data in route_points_data:
            estimated_arrival_str = point_data.get('estimated_arrival')
            if not estimated_arrival_str:
                continue
            
            try:
                if isinstance(estimated_arrival_str, str):
                    estimated_arrival = datetime.fromisoformat(estimated_arrival_str)
                else:
                    estimated_arrival = estimated_arrival_str
                
                # Рассчитываем время звонка
                call_time = estimated_arrival - timedelta(minutes=call_advance_minutes)
                
                order_number = point_data.get('order_number')
                order_info = orders_dict.get(order_number, {})
                
                call_schedule.append({
                    "order_number": order_number,
                    "call_time": call_time.isoformat(),
                    "arrival_time": estimated_arrival.isoformat(),
                    "phone": order_info.get('phone', 'Не указан'),
                    "customer_name": order_info.get('customer_name', '')
                })
            except Exception as e:
                logger.warning(f"Ошибка обработки точки маршрута для графика звонков: {e}")
                continue
        
        return call_schedule
    
    def _save_call_schedule_to_db(
        self,
        user_id: int,
        order_date: date,
        call_schedule: List[Dict],
        route_data: Dict
    ):
        """
        Сохранить график звонков в БД
        
        Args:
            user_id: ID пользователя
            order_date: Дата маршрута
            call_schedule: График звонков
            route_data: Данные маршрута
        """
        from src.database.connection import get_db_session
        from src.models.order import RouteDataDB
        from sqlalchemy.orm.attributes import flag_modified
        
        try:
            with get_db_session() as session:
                route_db = session.query(RouteDataDB).filter(
                    RouteDataDB.user_id == user_id,
                    RouteDataDB.route_date == order_date
                ).first()
                
                if route_db:
                    # Обновляем call_schedule
                    route_db.call_schedule = call_schedule
                    flag_modified(route_db, 'call_schedule')
                    session.commit()
                    logger.info(f"✅ График звонков сохранен в БД для user_id={user_id}, date={order_date}")
                else:
                    logger.warning(f"⚠️ Маршрут не найден в БД для сохранения графика звонков")
        except Exception as e:
            logger.error(f"❌ Ошибка сохранения графика звонков в БД: {e}", exc_info=True)
    
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
            # Удаляем все данные за сегодня через RouteService
            from src.database.connection import get_db_session
            with get_db_session() as session:
                self.parent.route_service.delete_all_data_by_date(user_id, today, session)
            
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
        
        # Загружаем маршрут через RouteService
        route_data = self.parent.get_route_data_dict(user_id, today)
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
        orders_data = self.parent.get_today_orders_dict(user_id, today)
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
        
        # Загружаем маршрут через RouteService
        route_data = self.parent.get_route_data_dict(user_id, today)
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
        
        orders_data = self.parent.get_today_orders_dict(user_id, today)
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
        orders_data = self.parent.get_today_orders_dict(user_id, today)
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
            start_location_data = self.parent.get_start_location_dict(user_id, today) or {}
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
                error_msg = str(e)
                # Игнорируем ошибку "message is not modified" - это не критично
                if "message is not modified" in error_msg.lower():
                    logger.debug(f"Сообщение не изменилось (это нормально): {error_msg}")
                    return  # Просто выходим, так как сообщение уже актуально
                else:
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
            logger.info(f"🔄 handle_mark_order_delivered вызван: callback_data={data}, user_id={user_id}")
            # Формат callback_data: route_delivered_<order_number>
            prefix = "route_delivered_"
            if not data.startswith(prefix):
                logger.warning(f"⚠️ Неверный формат callback_data: {data}")
                self.bot.answer_callback_query(call.id, "❌ Некорректные данные", show_alert=True)
                return

            order_number = data[len(prefix):]
            if not order_number:
                logger.warning(f"⚠️ Не указан номер заказа в callback_data: {data}")
                self.bot.answer_callback_query(call.id, "❌ Не указан номер заказа", show_alert=True)
                return
            
            logger.info(f"📦 Отмечаю заказ {order_number} как доставленный для user_id={user_id}")

            # Загружаем маршрут ДО обновления статуса, чтобы найти индекс текущего заказа
            route_data = self.parent.get_route_data_dict(user_id, today)
            if not route_data:
                # Если маршрута нет, просто обновляем статус
                from src.application.dto.order_dto import UpdateOrderDTO
                from src.database.connection import get_db_session
                update_dto = UpdateOrderDTO(status="delivered")
                with get_db_session() as session:
                    updated_order = self.parent.order_service.update_order(user_id, order_number, update_dto, today, session)
                updated = updated_order is not None
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
            orders_data_before = self.parent.get_today_orders_dict(user_id, today)
            active_order_numbers_before = {od.get('order_number') for od in orders_data_before if od.get('status', 'pending') != 'delivered'}
            active_points_before = [p for p in sorted_points if p.get('order_number') in active_order_numbers_before]
            current_index = next((i for i, p in enumerate(active_points_before) if p.get('order_number') == order_number), None)
            
            # Обновляем статус заказа через OrderService
            from src.application.dto.order_dto import UpdateOrderDTO
            from src.database.connection import get_db_session
            update_dto = UpdateOrderDTO(status="delivered")
            
            logger.info(f"💾 Обновляю статус заказа {order_number} на 'delivered' в БД")
            with get_db_session() as session:
                # Получаем заказ до обновления для проверки
                order_before = self.parent.order_service.get_order_by_number(user_id, order_number, today, session)
                logger.info(f"Статус заказа {order_number} ДО обновления: {order_before.status if order_before else 'не найден'}")
                
                updated_order = self.parent.order_service.update_order(user_id, order_number, update_dto, today, session)
                
                # Проверяем, что заказ действительно обновился
                if updated_order:
                    logger.info(f"✅ Статус заказа {order_number} обновлен в БД: {updated_order.status}")
                else:
                    logger.error(f"❌ Не удалось обновить статус заказа {order_number} в БД (update_order вернул None)")
                    
                # Явно коммитим изменения (хотя update_order уже должен это делать)
                session.commit()
                logger.info(f"💾 Изменения закоммичены в БД")
            
            updated = updated_order is not None

            if not updated:
                logger.error(f"❌ Не удалось обновить статус заказа {order_number} в БД")
                self.bot.answer_callback_query(
                    call.id,
                    f"❌ Заказ №{order_number} не найден за сегодня",
                    show_alert=True
                )
                return

            # Отвечаем на callback
            self.bot.answer_callback_query(call.id, f"✅ Заказ №{order_number} отмечен доставленным")
            
            # Загружаем активные заказы ПОСЛЕ обновления статуса (обязательно перезагружаем из БД)
            logger.info(f"🔄 Перезагружаю данные заказов и маршрута после обновления статуса")
            orders_data_after = self.parent.get_today_orders_dict(user_id, today)
            logger.debug(f"Загружено заказов после обновления: {len(orders_data_after)}")
            
            # Проверяем, что заказ действительно обновился
            updated_order_data = next((od for od in orders_data_after if od.get('order_number') == order_number), None)
            if updated_order_data:
                logger.info(f"Статус заказа {order_number} в загруженных данных: {updated_order_data.get('status')} (ожидается 'delivered')")
                if updated_order_data.get('status') != 'delivered':
                    logger.warning(f"⚠️ Статус заказа {order_number} НЕ обновился в БД! Текущий статус: {updated_order_data.get('status')}")
            else:
                logger.warning(f"⚠️ Заказ {order_number} не найден в загруженных данных после обновления")
            
            active_order_numbers_after = {od.get('order_number') for od in orders_data_after if od.get('status', 'pending') != 'delivered'}
            logger.info(f"Активных заказов после обновления: {len(active_order_numbers_after)} (было: {len(active_order_numbers_before)})")
            
            # Перезагружаем маршрут из БД, чтобы получить актуальные данные
            route_data_after = self.parent.get_route_data_dict(user_id, today)
            if route_data_after:
                route_points_data_after = route_data_after.get('route_points_data', [])
                try:
                    sorted_points_after = sorted(
                        route_points_data_after,
                        key=lambda pd: datetime.fromisoformat(pd.get("estimated_arrival"))
                    )
                except Exception:
                    sorted_points_after = route_points_data_after
                active_points_after = [p for p in sorted_points_after if p.get('order_number') in active_order_numbers_after]
            else:
                active_points_after = [p for p in sorted_points if p.get('order_number') in active_order_numbers_after]
            
            logger.info(f"Активных точек маршрута после обновления: {len(active_points_after)}")
            
            if active_points_after:
                # Определяем, какой заказ показать
                if current_index is not None:
                    # Находим следующий заказ в исходном списке активных заказов
                    # Если текущий заказ был не последним, следующий был на current_index + 1
                    # После удаления текущего заказа, следующий сдвинулся на current_index
                    if current_index < len(active_points_before) - 1:
                        # Текущий заказ был не последним - следующий заказ был на current_index + 1
                        # После удаления текущего, следующий стал на current_index
                        next_index = current_index
                        next_order_number = active_points_before[current_index + 1].get('order_number') if current_index + 1 < len(active_points_before) else None
                        logger.info(f"Текущий заказ {order_number} был на индексе {current_index}, следующий заказ {next_order_number} был на индексе {current_index + 1}, теперь он на индексе {next_index}")
                    else:
                        # Текущий заказ был последним - показываем предыдущий (который теперь последний)
                        next_index = len(active_points_after) - 1
                        logger.info(f"Текущий заказ {order_number} был последним (индекс {current_index}), показываю предыдущий заказ на индексе {next_index}")
                else:
                    # Если не нашли индекс (не должно случиться), показываем первый
                    next_index = 0
                    logger.warning(f"Не удалось найти индекс текущего заказа {order_number}, показываю первый заказ")
                
                # Проверяем, что индекс валидный
                if next_index >= len(active_points_after):
                    logger.warning(f"Индекс {next_index} выходит за пределы списка активных заказов ({len(active_points_after)}), показываю последний")
                    next_index = len(active_points_after) - 1
                
                next_order_number = active_points_after[next_index].get('order_number') if next_index < len(active_points_after) else None
                logger.info(f"🔄 Показываю следующий заказ {next_order_number} с индексом {next_index} из {len(active_points_after)} активных")
                self._show_order_at_index(call.message.chat.id, user_id, active_points_after, next_index, call.message.message_id)
            else:
                # Больше нет активных заказов
                logger.info(f"Все заказы доставлены, нет активных заказов для показа")
                try:
                    # Удаляем старое сообщение и отправляем новое с клавиатурой
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
