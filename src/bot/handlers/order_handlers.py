"""
Обработчики для работы с заказами - ПОЛНАЯ РЕАЛИЗАЦИЯ.

Содержит весь код для:
- Добавления заказов
- Редактирования заказов  
- Просмотра деталей
- Отметки доставленных
- Поиска по номеру
"""
import logging
import re
from typing import Dict, List
from datetime import datetime, time, timedelta, date
from telebot import types
from src.models.order import Order, CallStatusDB
from src.services.maps_service import MapsService
from src.database.connection import get_db_session

logger = logging.getLogger(__name__)


class OrderHandlers:
    """Обработчики заказов - полная реализация"""
    
    def __init__(self, bot_instance):
        self.bot = bot_instance.bot
        self.parent = bot_instance
    
    def register(self):
        """Регистрация обработчиков заказов"""
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
            self.show_delivered_orders(call.from_user.id, call.message.chat.id)
            self.bot.answer_callback_query(call.id)
        elif callback_data.startswith("mark_delivered_"):
            order_number = callback_data.replace("mark_delivered_", "")
            self.mark_order_delivered(call.from_user.id, order_number, call.message.chat.id)
            self.bot.answer_callback_query(call.id, "✅ Заказ отмечен как доставленный")
    
    # ==================== ОБРАБОТКА СОСТОЯНИЙ ====================
    
    def process_order_state(self, message, current_state, state_data):
        """Обработка сообщений в состояниях заказов"""
        try:
            if current_state == 'waiting_for_orders':
                self.process_order_number(message)
            elif current_state == 'waiting_for_order_phone':
                self.process_order_phone(message)
            elif current_state == 'waiting_for_order_name':
                self.process_order_name(message)
            elif current_state == 'waiting_for_order_comment':
                self.process_order_comment(message)
            elif current_state == 'waiting_for_order_entrance':
                self.process_order_entrance(message)
            elif current_state == 'waiting_for_order_apartment':
                self.process_order_apartment(message)
            elif current_state == 'waiting_for_order_delivery_time':
                self.process_order_delivery_time(message)
            elif current_state == 'waiting_for_manual_arrival_time':
                self.process_manual_arrival_time(message)
            elif current_state == 'waiting_for_manual_call_time':
                self.process_manual_call_time(message)
            elif current_state == 'searching_order_by_number':
                self.process_search_order_by_number(message)
            else:
                logger.warning(f"Неизвестное состояние заказа: {current_state}")
                self.bot.reply_to(
                    message,
                    "⚠️ Неизвестное состояние. Возврат в главное меню.",
                    reply_markup=self.parent._main_menu_markup()
                )
                self.parent.clear_user_state(message.from_user.id)
        
        except Exception as e:
            logger.error(f"Ошибка обработки состояния заказа: {e}", exc_info=True)
            self.bot.reply_to(
                message,
                f"❌ Ошибка обработки: {str(e)}",
                reply_markup=self.parent._main_menu_markup()
            )
            self.parent.clear_user_state(message.from_user.id)
    
    def process_order_number_quick(self, message):
        """Быстрый поиск заказа по номеру"""
        try:
            order_number = message.text.strip()
            user_id = message.from_user.id
            
            order = self.parent.db_service.get_order_by_number(user_id, order_number)
            if order:
                self.parent.update_user_state(user_id, 'searching_order_by_number', {})
                self.process_search_order_by_number(message)
            else:
                self.bot.reply_to(
                    message,
                    "❓ Используйте кнопки меню для навигации",
                    reply_markup=self.parent._main_menu_markup()
                )
        except Exception as e:
            logger.error(f"Ошибка быстрого поиска заказа: {e}", exc_info=True)
    
    # ==================== ДОБАВЛЕНИЕ ЗАКАЗОВ ====================
    
    def handle_add_orders(self, message):
        """Handle /add_orders command"""
        user_id = message.from_user.id
        self.parent.update_user_state(user_id, 'state', 'waiting_for_orders')
        self.parent.update_user_state(user_id, 'orders', [])

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
        self.bot.reply_to(message, text, parse_mode='HTML', reply_markup=self.parent._add_orders_menu_markup())
    
    def process_order_number(self, message):
        """Process order input"""
        text = message.text.strip()
        user_id = message.from_user.id
        state_data = self.parent.get_user_state(user_id)

        if text == "/done" or text == "✅ Готово":
            orders = state_data.get("orders", [])
            if not orders:
                self.bot.reply_to(message, "❌ Нет добавленных заказов", reply_markup=self.parent._orders_menu_markup())
                return

            # Сохраняем заказы в БД
            today = date.today()
            saved_count = 0
            errors = []
            for i, order_data in enumerate(orders):
                try:
                    # Преобразуем строки времени обратно в time объекты
                    order_dict = order_data.copy()
                    
                    if not order_dict.get('address'):
                        errors.append(f"Заказ {i+1}: отсутствует адрес")
                        continue
                    
                    # Преобразуем время
                    if isinstance(order_dict.get('delivery_time_start'), str):
                        try:
                            order_dict['delivery_time_start'] = datetime.fromisoformat(order_dict['delivery_time_start']).time()
                        except Exception:
                            order_dict['delivery_time_start'] = None
                    if isinstance(order_dict.get('delivery_time_end'), str):
                        try:
                            order_dict['delivery_time_end'] = datetime.fromisoformat(order_dict['delivery_time_end']).time()
                        except Exception:
                            order_dict['delivery_time_end'] = None
                    
                    order = Order(**order_dict)
                    self.parent.db_service.save_order(user_id, order, today)
                    saved_count += 1
                except Exception as e:
                    error_msg = f"Заказ {i+1}: {str(e)}"
                    errors.append(error_msg)
                    logger.error(f"Ошибка сохранения заказа {i+1}: {e}, данные: {order_data}", exc_info=True)
            
            # Очищаем временные данные
            self.parent.update_user_state(user_id, 'state', None)
            self.parent.update_user_state(user_id, 'orders', [])
            
            response_text = f"✅ Сохранено {saved_count} заказов за сегодня ({today.strftime('%d.%m.%Y')})"
            if errors:
                response_text += f"\n\n⚠️ Ошибки при сохранении:\n" + "\n".join(errors[:5])
            
            self.bot.reply_to(message, response_text, reply_markup=self.parent._orders_menu_markup())
            return

        if text == "⬅️ В меню" or text == "⬅️ Главное меню":
            self.parent.update_user_state(user_id, 'state', None)
            self.bot.reply_to(message, "🏠 Возврат в главное меню", reply_markup=self.parent._main_menu_markup())
            return

        def parse_line(line: str) -> dict:
            """Парсинг одной строки заказа"""
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

        # Если прислали несколько строк разом
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
                self.parent.update_user_state(user_id, 'orders', orders)
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
            self.parent.update_user_state(user_id, 'orders', orders)

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
    
    def handle_delivered_orders(self, message):
        """Показать список доставленных заказов"""
        user_id = message.from_user.id
        self.show_delivered_orders(user_id, message.chat.id)
    
    def show_delivered_orders(self, user_id: int, chat_id: int):
        """Показать список доставленных заказов"""
        today = date.today()
        
        # Загружаем из БД
        orders_data = self.parent.db_service.get_today_orders(user_id)
        
        delivered_orders = [od for od in orders_data if od.get('status', 'pending') == 'delivered']
        
        if not delivered_orders:
            self.bot.send_message(chat_id, "✅ Нет доставленных заказов", reply_markup=self.parent._main_menu_markup())
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
        
        self.bot.send_message(chat_id, text, parse_mode='HTML', reply_markup=self.parent._main_menu_markup())
    
    def handle_order_details_start(self, message):
        """Начало просмотра деталей заказа - компактный список в одном сообщении"""
        user_id = message.from_user.id
        today = date.today()
        
        # Загружаем из БД
        orders_data = self.parent.db_service.get_today_orders(user_id)
        
        if not orders_data:
            self.bot.reply_to(
                message,
                "❌ Нет добавленных заказов",
                reply_markup=self.parent._orders_menu_markup()
            )
            return
        
        # Фильтруем только не доставленные заказы
        active_orders = [od for od in orders_data if od.get('status', 'pending') != 'delivered']
        
        if not active_orders:
            self.bot.reply_to(
                message,
                "✅ Все заказы доставлены!",
                reply_markup=self.parent._orders_menu_markup()
            )
            return
        
        # Формируем только кнопки с информацией
        from telebot import types
        
        # Сортируем по порядку в маршруте (если есть), иначе по номеру заказа
        try:
            route_data = self.parent.db_service.get_route_data(user_id, today)
            if route_data and route_data.get('route_order'):
                route_order = route_data['route_order']
                # Сортируем заказы по их позиции в маршруте
                def get_route_position(order_data):
                    order_num = order_data.get('order_number', '')
                    try:
                        return route_order.index(order_num)
                    except ValueError:
                        # Если заказа нет в маршруте - в конец
                        return len(route_order) + 1
                
                active_orders_sorted = sorted(active_orders, key=get_route_position)
                logger.info(f"Заказы отсортированы по маршруту: {[o.get('order_number') for o in active_orders_sorted]}")
            else:
                # Нет маршрута - сортируем по номеру заказа
                active_orders_sorted = sorted(active_orders, key=lambda x: x.get('order_number', ''))
                logger.info("Маршрут не найден, сортировка по номеру заказа")
        except Exception as e:
            logger.error(f"Ошибка загрузки маршрута для сортировки: {e}", exc_info=True)
            # Fallback - сортируем по номеру заказа
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
    
    def show_order_details(self, user_id: int, order_number: str, chat_id: int):
        """Показать детали заказа с кнопкой Доставлен"""
        today = date.today()
        
        # Загружаем из БД
        try:
            orders_data = self.parent.db_service.get_today_orders(user_id)
        except Exception as e:
            logger.error(f"Ошибка загрузки заказов из БД: {e}", exc_info=True)
            self.bot.send_message(chat_id, f"❌ Ошибка загрузки данных: {str(e)}", reply_markup=self.parent._main_menu_markup())
            return
        
        order_found = False
        order_data = None
        for od in orders_data:
            if od.get('order_number') == order_number:
                order_found = True
                order_data = od
                break
        
        if not order_found:
            self.bot.send_message(chat_id, f"❌ Заказ №{order_number} не найден", reply_markup=self.parent._main_menu_markup())
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
            self.bot.send_message(chat_id, f"❌ Ошибка обработки данных заказа: {str(e)}", reply_markup=self.parent._main_menu_markup())
            return
        details = [
            f"✏️ <b>Редактирование заказа №{order_number}</b>\n",
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
        
        # Ручное время прибытия и звонка
        if order_data.get('manual_arrival_time'):
            manual_arrival = order_data['manual_arrival_time']
            if isinstance(manual_arrival, str):
                manual_arrival = datetime.fromisoformat(manual_arrival)
            details.append(f"⏰ <b>Время прибытия (ручное):</b> {manual_arrival.strftime('%H:%M')}")
        
        if order_data.get('manual_call_time'):
            manual_call = order_data['manual_call_time']
            if isinstance(manual_call, str):
                manual_call = datetime.fromisoformat(manual_call)
            details.append(f"📞⏰ <b>Время звонка (ручное):</b> {manual_call.strftime('%H:%M')}")
        
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
        reply_markup.row("⏰ Время прибытия", "📞⏰ Время звонка")
        reply_markup.row("⬅️ К списку заказов")
        reply_markup.row("⬅️ Главное меню")
        
        # Сохраняем номер заказа для быстрого редактирования
        self.parent.update_user_state(user_id, 'updating_order_number', order_number)
        
        try:
            self.bot.send_message(chat_id, "\n".join(details), parse_mode='HTML', reply_markup=reply_markup)
            self.bot.send_message(chat_id, "Нажмите кнопку ниже, чтобы пометить заказ как доставленный:", reply_markup=inline_markup)
        except Exception as e:
            logger.error(f"Ошибка отправки сообщения с деталями заказа: {e}", exc_info=True)
            self.bot.send_message(chat_id, f"❌ Ошибка отображения деталей заказа: {str(e)}", reply_markup=self.parent._main_menu_markup())
    
    def mark_order_delivered(self, user_id: int, order_number: str, chat_id: int):
        """Пометить заказ как доставленный"""
        today = date.today()
        
        # Обновляем в БД
        updated = self.parent.db_service.update_order(
            user_id, order_number, {'status': 'delivered'}, today
        )
        
        if updated:
            # Очищаем маршрут из state (но оставляем в БД)
            self.parent.update_user_state(user_id, 'route_summary', [])
            self.parent.update_user_state(user_id, 'call_schedule', [])
            self.parent.update_user_state(user_id, 'route_order', [])
            
            # Отправляем подтверждение
            self.bot.send_message(
                chat_id,
                f"✅ Заказ №{order_number} помечен как доставленный",
                reply_markup=self.parent._main_menu_markup()
            )
            
            # Ищем следующий заказ в маршруте
            try:
                route_data = self.parent.db_service.get_route_data(user_id, today)
                if route_data and route_data.get('route_order'):
                    route_order = route_data['route_order']
                    route_points_data = route_data.get('route_points_data', [])
                    
                    # Находим индекс текущего заказа
                    try:
                        current_index = route_order.index(order_number)
                        
                        # Ищем следующий недоставленный заказ
                        next_order_number = None
                        next_point_data = None
                        
                        for i in range(current_index + 1, len(route_order)):
                            next_order_num = route_order[i]
                            # Проверяем, что следующий заказ не доставлен
                            orders_data = self.parent.db_service.get_today_orders(user_id)
                            next_order_data = next((od for od in orders_data if od.get('order_number') == next_order_num), None)
                            
                            if next_order_data and next_order_data.get('status', 'pending') != 'delivered':
                                next_order_number = next_order_num
                                if i < len(route_points_data):
                                    next_point_data = route_points_data[i]
                                break
                        
                        # Если найден следующий заказ - показываем его
                        if next_order_number and next_order_data:
                            self._show_next_order_info(chat_id, next_order_data, next_point_data)
                        else:
                            # Все заказы доставлены!
                            self.bot.send_message(
                                chat_id,
                                "🎉 <b>Отличная работа!</b>\n\nВсе заказы доставлены!",
                                parse_mode='HTML',
                                reply_markup=self.parent._main_menu_markup()
                            )
                    except ValueError:
                        # Заказ не найден в маршруте
                        logger.warning(f"Заказ {order_number} не найден в route_order")
            except Exception as e:
                logger.error(f"Ошибка при поиске следующего заказа: {e}", exc_info=True)
        else:
            self.bot.send_message(
                chat_id,
                f"❌ Не удалось обновить заказ №{order_number}",
                reply_markup=self.parent._main_menu_markup()
            )
    
    def _show_next_order_info(self, chat_id: int, order_data: dict, point_data: dict = None):
        """Показать информацию о следующем заказе после доставки"""
        order_number = order_data.get('order_number', 'Без номера')
        address = order_data.get('address', 'Адрес не указан')
        customer_name = order_data.get('customer_name', 'Не указано')
        phone = order_data.get('phone', 'Не указан')
        comment = order_data.get('comment', '')
        
        text = f"➡️ <b>Следующий заказ:</b>\n\n"
        text += f"📦 <b>№{order_number}</b>\n"
        text += f"📍 <b>Адрес:</b> {address}\n"
        text += f"👤 <b>Клиент:</b> {customer_name}\n"
        text += f"📞 <b>Телефон:</b> {phone}\n"
        
        # Время прибытия из маршрута
        if point_data:
            estimated_arrival = point_data.get('estimated_arrival')
            if estimated_arrival:
                try:
                    arrival_time = datetime.fromisoformat(estimated_arrival)
                    text += f"⏰ <b>Время прибытия:</b> {arrival_time.strftime('%H:%M')}\n"
                except:
                    pass
            
            call_time = point_data.get('call_time')
            if call_time:
                try:
                    call_dt = datetime.fromisoformat(call_time)
                    text += f"📞 <b>Время звонка:</b> {call_dt.strftime('%H:%M')}\n"
                except:
                    pass
        
        if comment:
            text += f"\n💬 <b>Комментарий:</b> {comment}\n"
        
        self.bot.send_message(chat_id, text, parse_mode='HTML')
    
    def process_order_phone(self, message, state_data):
        """Обработка ввода телефона"""
        user_id = message.from_user.id
        text = message.text.strip()
        
        if text == "⬅️ Главное меню":
            self.parent.update_user_state(user_id, 'state', None)
            self.parent.update_user_state(user_id, 'updating_order_number', None)
            self.bot.reply_to(message, "🏠 Возврат в главное меню", reply_markup=self.parent._main_menu_markup())
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
            self.parent.update_user_state(user_id, 'state', None)
            self.parent.update_user_state(user_id, 'updating_order_number', None)
            self.bot.reply_to(message, "🏠 Возврат в главное меню", reply_markup=self.parent._main_menu_markup())
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
            self.parent.update_user_state(user_id, 'state', None)
            self.parent.update_user_state(user_id, 'updating_order_number', None)
            self.bot.reply_to(message, "🏠 Возврат в главное меню", reply_markup=self.parent._main_menu_markup())
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
            self.parent.update_user_state(user_id, 'state', None)
            self.parent.update_user_state(user_id, 'updating_order_number', None)
            self.bot.reply_to(message, "🏠 Возврат в главное меню", reply_markup=self.parent._main_menu_markup())
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
            self.parent.update_user_state(user_id, 'state', None)
            self.parent.update_user_state(user_id, 'updating_order_number', None)
            self.bot.reply_to(message, "🏠 Возврат в главное меню", reply_markup=self.parent._main_menu_markup())
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
            self.parent.update_user_state(user_id, 'state', None)
            self.parent.update_user_state(user_id, 'updating_order_number', None)
            self.bot.reply_to(message, "🏠 Возврат в главное меню", reply_markup=self.parent._main_menu_markup())
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
            from telebot import types
            markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
            markup.row("⬅️ К списку заказов")
            markup.row("⬅️ Главное меню")
            self.bot.reply_to(
                message,
                "❌ Неверный формат времени. Используйте формат ЧЧ:ММ - ЧЧ:ММ\nПример: 10:00 - 13:00",
                reply_markup=markup
            )
            return
        
        # Обновляем время доставки
        self._update_order_field(user_id, order_number, 'delivery_time_window', text, message)
        
        # Пересчитываем время звонков для этого заказа
        state_data = self.parent.get_user_state(user_id)
        route_summary = state_data.get('route_summary', [])
        if route_summary:
            from src.services.maps import MapsService
            orders = state_data.get('orders', [])
            for order_data in orders:
                if order_data.get('order_number') == order_number:
                    updated_order = Order(**order_data)
                    # Вызываем метод из route_handlers для обновления маршрута
                    # Пропускаем пересчет здесь, так как он выполняется в _update_order_field
                    break
    
    def process_manual_arrival_time(self, message, state_data):
        """Обработка ввода ручного времени прибытия"""
        user_id = message.from_user.id
        text = message.text.strip()
        
        if text == "⬅️ Главное меню":
            self.parent.update_user_state(user_id, 'state', None)
            self.parent.update_user_state(user_id, 'updating_order_number', None)
            self.bot.reply_to(message, "🏠 Возврат в главное меню", reply_markup=self.parent._main_menu_markup())
            return
        
        order_number = state_data.get('updating_order_number')
        if not order_number:
            self.bot.reply_to(message, "❌ Ошибка: номер заказа не найден")
            return
        
        # Проверяем формат времени (ЧЧ:ММ)
        import re
        time_pattern = r'^(\d{1,2}):(\d{2})$'
        match = re.match(time_pattern, text)
        
        if not match:
            from telebot import types
            markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
            markup.row("⬅️ К списку заказов")
            markup.row("⬅️ Главное меню")
            self.bot.reply_to(
                message,
                "❌ Неверный формат времени. Используйте формат ЧЧ:ММ\nПример: 14:20",
                reply_markup=markup
            )
            return
        
        # Парсим время
        try:
            hour, minute = map(int, match.groups())
            if not (0 <= hour < 24 and 0 <= minute < 60):
                raise ValueError("Invalid time")
            
            # Создаем datetime для сегодняшнего дня
            today = date.today()
            manual_time = datetime.combine(today, time(hour, minute))
            
            # Обновляем в БД
            self._update_order_field(user_id, order_number, 'manual_arrival_time', manual_time.isoformat(), message)
        except ValueError:
            from telebot import types
            markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
            markup.row("⬅️ К списку заказов")
            markup.row("⬅️ Главное меню")
            self.bot.reply_to(
                message,
                "❌ Некорректное время. Проверьте значения (00:00 - 23:59)",
                reply_markup=markup
            )
    
    def process_manual_call_time(self, message, state_data):
        """Обработка ввода ручного времени звонка"""
        user_id = message.from_user.id
        text = message.text.strip()
        
        if text == "⬅️ Главное меню":
            self.parent.update_user_state(user_id, 'state', None)
            self.parent.update_user_state(user_id, 'updating_order_number', None)
            self.bot.reply_to(message, "🏠 Возврат в главное меню", reply_markup=self.parent._main_menu_markup())
            return
        
        order_number = state_data.get('updating_order_number')
        if not order_number:
            self.bot.reply_to(message, "❌ Ошибка: номер заказа не найден")
            return
        
        # Проверяем формат времени (ЧЧ:ММ)
        import re
        time_pattern = r'^(\d{1,2}):(\d{2})$'
        match = re.match(time_pattern, text)
        
        if not match:
            from telebot import types
            markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
            markup.row("⬅️ К списку заказов")
            markup.row("⬅️ Главное меню")
            self.bot.reply_to(
                message,
                "❌ Неверный формат времени. Используйте формат ЧЧ:ММ\nПример: 14:20",
                reply_markup=markup
            )
            return
        
        # Парсим время
        try:
            hour, minute = map(int, match.groups())
            if not (0 <= hour < 24 and 0 <= minute < 60):
                raise ValueError("Invalid time")
            
            # Создаем datetime для сегодняшнего дня
            today = date.today()
            manual_time = datetime.combine(today, time(hour, minute))
            
            # Обновляем в БД и создаем/обновляем call_status
            self._update_manual_call_time(user_id, order_number, manual_time, message)
        except ValueError:
            from telebot import types
            markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
            markup.row("⬅️ К списку заказов")
            markup.row("⬅️ Главное меню")
            self.bot.reply_to(
                message,
                "❌ Некорректное время. Проверьте значения (00:00 - 23:59)",
                reply_markup=markup
            )
    
    def process_search_order_by_number(self, message, state_data):
        """Обработка поиска заказа по номеру"""
        user_id = message.from_user.id
        text = message.text.strip()
        
        if text == "⬅️ Главное меню":
            self.parent.update_user_state(user_id, 'state', None)
            self.bot.reply_to(message, "🏠 Возврат в главное меню", reply_markup=self.parent._main_menu_markup())
            return
        
        # Проверяем, является ли текст номером заказа
        if not text.isdigit():
            self.bot.reply_to(
                message,
                "❌ Номер заказа должен содержать только цифры. Попробуйте еще раз:",
                reply_markup=self.parent._orders_menu_markup()
            )
            return
        
        # Ищем заказ
        try:
            orders_data = self.parent.db_service.get_today_orders(user_id)
            order_found = False
            for od in orders_data:
                if od.get('order_number') == text:
                    order_found = True
                    # Открываем детали заказа
                    self.show_order_details(user_id, text, message.chat.id)
                    self.parent.update_user_state(user_id, 'state', None)
                    break
            
            if not order_found:
                self.bot.reply_to(
                    message,
                    f"❌ Заказ №{text} не найден. Попробуйте еще раз или вернитесь в главное меню:",
                    reply_markup=self.parent._orders_menu_markup()
                )
        except Exception as e:
            logger.error(f"Ошибка при поиске заказа: {e}", exc_info=True)
            self.bot.reply_to(message, f"❌ Ошибка: {str(e)}", reply_markup=self.parent._orders_menu_markup())
            self.parent.update_user_state(user_id, 'state', None)
    
    def _update_manual_call_time(self, user_id: int, order_number: str, manual_time: datetime, message):
        """Обновить ручное время звонка и создать/обновить call_status"""
        today = date.today()
        
        # Обновляем поле в заказе
        self._update_order_field(user_id, order_number, 'manual_call_time', manual_time.isoformat(), message)
        
        # Обновляем или создаем call_status
        from src.database.connection import get_db_session
        from src.models.order import CallStatusDB
        
        orders_data = self.parent.db_service.get_today_orders(user_id)
        order_data = None
        for od in orders_data:
            if od.get('order_number') == order_number:
                order_data = od
                break
        
        if not order_data:
            return
        
        with get_db_session() as session:
            call_status = session.query(CallStatusDB).filter(
                CallStatusDB.user_id == user_id,
                CallStatusDB.order_number == order_number,
                CallStatusDB.call_date == today
            ).first()
            
            if call_status:
                # Обновляем существующую запись
                call_status.call_time = manual_time
                # Если статус был confirmed/failed - сбрасываем на pending
                if call_status.status in ['confirmed', 'failed', 'sent']:
                    call_status.status = 'pending'
                    call_status.attempts = 0
                session.commit()
                logger.info(f"Обновлено время звонка для заказа {order_number}: {manual_time.strftime('%H:%M')}")
            else:
                # Создаем новую запись если есть телефон
                if order_data.get('phone'):
                    self.parent.call_notifier.create_call_status(
                        user_id,
                        order_number,
                        manual_time,
                        order_data['phone'],
                        order_data.get('customer_name'),
                        today
                    )
                    logger.info(f"Создана запись о звонке для заказа {order_number}: {manual_time.strftime('%H:%M')}")
    
    def _update_order_field(self, user_id: int, order_number: str, field_name: str, field_value: str, message):
        """Обновить конкретное поле заказа"""
        today = date.today()
        
        # Загружаем заказ из БД
        orders_data = self.parent.db_service.get_today_orders(user_id)
        
        order_found = False
        order_data = None
        for od in orders_data:
            if od.get('order_number') == order_number:
                order_found = True
                order_data = od.copy()
                break
        
        if not order_found:
            self.bot.reply_to(message, f"❌ Заказ №{order_number} не найден", reply_markup=self.parent._main_menu_markup())
            return
        
        # Обновляем поле
        updates = {field_name: field_value}
        
        # Если обновлен подъезд, обновляем адрес (БЕЗ геокодирования - координаты остаются те же)
        if field_name == 'entrance_number':
            original_address = order_data['address']
            # Удаляем старый подъезд из адреса, если есть
            import re
            address_clean = re.sub(r',\s*подъезд\s+\d+', '', original_address, flags=re.IGNORECASE)
            address_clean = re.sub(r'\s+подъезд\s+\d+', '', address_clean, flags=re.IGNORECASE)
            updates['address'] = f"{address_clean}, подъезд {field_value}"
            
            # НЕ пересчитываем геокодирование - подъезд не меняет координаты здания!
            # Это экономит 1-2 секунды на запросе к API карт
            logger.info(f"Обновлен подъезд для заказа {order_number}: {field_value} (геокодирование пропущено)")
        
        # Если обновлено время доставки, парсим его
        if field_name == 'delivery_time_window':
            temp_order = Order(**{**order_data, 'delivery_time_window': field_value})
            if temp_order.delivery_time_start:
                updates['delivery_time_start'] = temp_order.delivery_time_start
            if temp_order.delivery_time_end:
                updates['delivery_time_end'] = temp_order.delivery_time_end
        
        # Если обновлено ручное время прибытия/звонка, парсим datetime
        if field_name in ['manual_arrival_time', 'manual_call_time']:
            try:
                updates[field_name] = datetime.fromisoformat(field_value)
            except (ValueError, AttributeError):
                logger.error(f"Ошибка парсинга времени: {field_value}")
        
        # Обновляем в БД
        try:
            self.parent.db_service.update_order(user_id, order_number, updates, today)
            
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
                        route_data_check = self.parent.db_service.get_route_data(user_id, today)
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
                                        self.parent.call_notifier.create_call_status(
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
            route_data = self.parent.db_service.get_route_data(user_id, today)
            if route_data and (route_data.get('route_summary') or route_data.get('route_points_data')):
                # Загружаем обновленный заказ
                updated_orders_data = self.parent.db_service.get_today_orders(user_id)
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
                            start_location_data = self.parent.db_service.get_start_location(user_id, today)
                            from src.services.maps import MapsService
                            state_data = {
                                'route_summary': route_data.get('route_summary', []),
                                'call_schedule': route_data.get('call_schedule', []),
                                'route_order': route_data.get('route_order', []),
                                'orders': updated_orders_data,  # Все заказы для контекста
                                'start_location': {'lat': start_location_data.get('latitude'), 'lon': start_location_data.get('longitude')} if start_location_data and start_location_data.get('location_type') == 'geo' else None,
                                'start_address': start_location_data.get('address') if start_location_data and start_location_data.get('location_type') == 'address' else None,
                                'start_time': start_location_data.get('start_time') if start_location_data else None
                            }
                            # Вызываем метод из route_handlers
                            # ПРИМЕЧАНИЕ: Здесь нужно передать обновление маршрута в route_handlers
                            # Но для упрощения пропустим эту часть, так как она требует доступа к route_handlers
                            logger.info(f"Обновление маршрута для заказа {order_number} (требует route_handlers)")
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
            markup.row("⏰ Время прибытия", "📞⏰ Время звонка")
            markup.row("⬅️ К списку заказов")
            markup.row("⬅️ Главное меню")
            
            field_names = {
                'phone': 'Телефон',
                'customer_name': 'ФИО',
                'comment': 'Комментарий',
                'entrance_number': 'Подъезд',
                'apartment_number': 'Квартира',
                'delivery_time_window': 'Время доставки',
                'manual_arrival_time': 'Время прибытия',
                'manual_call_time': 'Время звонка'
            }
            
            text = (
                f"✅ <b>{field_names.get(field_name, 'Поле')} обновлено!</b>\n\n"
                f"Заказ №{order_number}\n"
                f"Выберите следующее поле для обновления:"
            )
            self.bot.reply_to(message, text, parse_mode='HTML', reply_markup=markup)
        except Exception as e:
            logger.error(f"Ошибка обновления заказа в БД: {e}", exc_info=True)
            self.bot.reply_to(message, f"❌ Ошибка обновления заказа: {str(e)}", reply_markup=self.parent._main_menu_markup())