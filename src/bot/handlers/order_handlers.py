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
        # Обработчик фотографий (скриншотов заказов)
        self.bot.register_message_handler(
            self.handle_photo,
            content_types=['photo']
        )
        # Кнопки меню заказов
        self.bot.register_message_handler(
            self.handle_add_orders,
            func=lambda m: m.text and "Добавить заказы" in m.text
        )
        self.bot.register_message_handler(
            self.handle_load_from_screenshot,
            func=lambda m: m.text and "Загрузить из скриншота" in m.text
        )
        self.bot.register_message_handler(
            self.handle_order_details_start,
            func=lambda m: m.text == "✏️ Редактирование заказов"
        )
        self.bot.register_message_handler(
            self.handle_delivered_orders,
            func=lambda m: m.text == "✅ Доставленные"
        )
        
        # Кнопки редактирования полей заказа
        self.bot.register_message_handler(
            self.handle_edit_phone,
            func=lambda m: m.text == "📞 Телефон"
        )
        self.bot.register_message_handler(
            self.handle_edit_name,
            func=lambda m: m.text == "👤 ФИО"
        )
        self.bot.register_message_handler(
            self.handle_edit_comment,
            func=lambda m: m.text == "💬 Комментарий"
        )
        self.bot.register_message_handler(
            self.handle_edit_entrance,
            func=lambda m: m.text == "🏢 Подъезд"
        )
        self.bot.register_message_handler(
            self.handle_edit_apartment,
            func=lambda m: m.text == "🚪 Квартира"
        )
        self.bot.register_message_handler(
            self.handle_edit_delivery_time,
            func=lambda m: m.text == "🕐 Время доставки"
        )
        self.bot.register_message_handler(
            self.handle_edit_arrival_time,
            func=lambda m: m.text == "⏰ Время прибытия"
        )
        self.bot.register_message_handler(
            self.handle_edit_call_time,
            func=lambda m: m.text == "📞⏰ Время звонка"
        )
        self.bot.register_message_handler(
            self.handle_back_to_orders_list,
            func=lambda m: m.text == "⬅️ К списку заказов"
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
        elif callback_data == "search_order_by_number":
            # Начать поиск заказа по номеру
            user_id = call.from_user.id
            self.parent.update_user_state(user_id, 'state', 'searching_order_by_number')
            self.bot.answer_callback_query(call.id)
            self.bot.send_message(
                call.message.chat.id,
                "🔍 Введите номер заказа:",
                reply_markup=self.parent._orders_menu_markup(user_id)
            )
        elif callback_data.startswith("mark_delivered_"):
            order_number = callback_data.replace("mark_delivered_", "")
            logger.info(f"🔄 Обработка mark_delivered_ для заказа {order_number}, user_id={call.from_user.id}")
            try:
                self.mark_order_delivered(call.from_user.id, order_number, call.message.chat.id)
                self.bot.answer_callback_query(call.id, "✅ Заказ отмечен как доставленный")
                logger.info(f"✅ Заказ {order_number} отмечен как доставленный")
            except Exception as e:
                import traceback
                logger.error(f"❌ Ошибка при отметке заказа {order_number} как доставленного: {e}\n{traceback.format_exc()}")
                self.bot.answer_callback_query(call.id, f"❌ Ошибка: {str(e)}", show_alert=True)
        elif callback_data.startswith("save_order_from_image_") or callback_data.startswith("overwrite_order_from_image_"):
            # Сохранить или перезаписать заказ из изображения
            is_overwrite = callback_data.startswith("overwrite_order_from_image_")
            user_id = call.from_user.id
            action_text = "перезаписи" if is_overwrite else "сохранения"
            logger.info(f"💾 Запрос на {action_text} заказа из изображения от user_id={user_id}")
            
            state_data = self.parent.get_user_state(user_id)
            order_data = state_data.get('pending_order_from_image')
            
            if not order_data:
                logger.warning(f"⚠️ Данные заказа не найдены во временном состоянии для user_id={user_id}")
                self.bot.answer_callback_query(call.id, "❌ Данные не найдены", show_alert=True)
                return
            
            logger.info(f"📋 {action_text.capitalize()} заказа из изображения: order_number={order_data.get('order_number')}, user_id={user_id}")
            logger.debug(f"📦 Полные данные для {action_text}: {order_data}")
            
            # Сохраняем заказ
            today = date.today()
            try:
                # Преобразуем delivery_time_window в delivery_time_start и delivery_time_end, если нужно
                if order_data.get('delivery_time_window') and not order_data.get('delivery_time_start'):
                    time_window = order_data.get('delivery_time_window')
                    if isinstance(time_window, str) and '-' in time_window:
                        try:
                            start_str, end_str = time_window.split('-', 1)
                            start_str = start_str.strip()
                            end_str = end_str.strip()
                            order_data['delivery_time_start'] = datetime.strptime(start_str, '%H:%M').time()
                            order_data['delivery_time_end'] = datetime.strptime(end_str, '%H:%M').time()
                            logger.debug(f"🕐 Преобразовано временное окно: {time_window} -> {order_data['delivery_time_start']} - {order_data['delivery_time_end']}")
                        except Exception as e:
                            logger.warning(f"⚠️ Не удалось распарсить временное окно '{time_window}': {e}")
                
                # Используем OrderService для сохранения заказа
                from src.application.dto.order_dto import CreateOrderDTO
                create_dto = CreateOrderDTO(**order_data)
                logger.info(f"💾 Вызов order_service.create_order для user_id={user_id}, order_number={create_dto.order_number}")
                self.parent.order_service.create_order(user_id, create_dto, today)
                action_result = "перезаписан" if is_overwrite else "сохранен"
                logger.info(f"✅ Заказ успешно {action_result} в БД: order_number={order.order_number}, user_id={user_id}")
                
                self.bot.answer_callback_query(call.id, f"✅ Заказ {action_result}!")
                
                # Очищаем временные данные
                self.parent.update_user_state(user_id, 'pending_order_from_image', None)
                logger.debug(f"🧹 Временные данные очищены для user_id={user_id}")
                
                # Обновляем сообщение
                result_text = "перезаписан" if is_overwrite else "сохранен"
                self.bot.edit_message_text(
                    f"✅ <b>Заказ {result_text}!</b>\n\n"
                    f"📦 Номер: {order_data.get('order_number', 'Не указан')}\n"
                    f"📍 Адрес: {order_data.get('address', 'Не указан')}\n\n"
                    f"Используйте <b>▶️ Оптимизировать</b> для построения маршрута",
                    call.message.chat.id,
                    call.message.message_id,
                    parse_mode='HTML'
                )
                logger.info(f"✅ Сообщение о {action_result} отправлено пользователю user_id={user_id}")
            except Exception as e:
                logger.error(f"❌ Ошибка {action_text} заказа из изображения для user_id={user_id}, order_number={order_data.get('order_number')}: {e}", exc_info=True)
                # Сокращаем сообщение об ошибке для Telegram API (максимум 200 символов)
                error_msg = str(e)
                if len(error_msg) > 180:
                    error_msg = error_msg[:177] + "..."
                # Убираем технические детали для пользователя
                if "duplicate key" in error_msg.lower() or "unique constraint" in error_msg.lower():
                    error_msg = "Заказ уже существует"
                elif "IntegrityError" in error_msg:
                    error_msg = "Ошибка сохранения в БД"
                self.bot.answer_callback_query(call.id, f"❌ {error_msg}", show_alert=True)
        elif callback_data == "cancel_save_order":
            user_id = call.from_user.id
            logger.info(f"❌ Отмена сохранения заказа из изображения для user_id={user_id}")
            self.parent.update_user_state(user_id, 'pending_order_from_image', None)
            logger.debug(f"🧹 Временные данные очищены для user_id={user_id}")
            self.bot.answer_callback_query(call.id, "❌ Отменено")
            self.bot.edit_message_text(
                "❌ Сохранение отменено",
                call.message.chat.id,
                call.message.message_id
            )
    
    # ==================== ОБРАБОТЧИКИ КНОПОК РЕДАКТИРОВАНИЯ ====================
    
    def handle_edit_phone(self, message):
        """Обработка кнопки 'Телефон'"""
        user_id = message.from_user.id
        state_data = self.parent.get_user_state(user_id)
        order_number = state_data.get('updating_order_number')
        
        if not order_number:
            user_id = message.from_user.id
            self.bot.reply_to(message, "❌ Заказ не выбран. Вернитесь к списку заказов.", reply_markup=self.parent._orders_menu_markup(user_id))
            return
        
        self.parent.update_user_state(user_id, 'state', 'waiting_for_order_phone')
        from telebot import types
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
        markup.row("⬅️ К списку заказов")
        markup.row("⬅️ Главное меню")
        self.bot.reply_to(message, f"📞 Введите номер телефона для заказа №{order_number}:", reply_markup=markup)
    
    def handle_edit_name(self, message):
        """Обработка кнопки 'ФИО'"""
        user_id = message.from_user.id
        state_data = self.parent.get_user_state(user_id)
        order_number = state_data.get('updating_order_number')
        
        if not order_number:
            user_id = message.from_user.id
            self.bot.reply_to(message, "❌ Заказ не выбран. Вернитесь к списку заказов.", reply_markup=self.parent._orders_menu_markup(user_id))
            return
        
        self.parent.update_user_state(user_id, 'state', 'waiting_for_order_name')
        from telebot import types
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
        markup.row("⬅️ К списку заказов")
        markup.row("⬅️ Главное меню")
        self.bot.reply_to(message, f"👤 Введите ФИО клиента для заказа №{order_number}:", reply_markup=markup)
    
    def handle_edit_comment(self, message):
        """Обработка кнопки 'Комментарий'"""
        user_id = message.from_user.id
        state_data = self.parent.get_user_state(user_id)
        order_number = state_data.get('updating_order_number')
        
        if not order_number:
            user_id = message.from_user.id
            self.bot.reply_to(message, "❌ Заказ не выбран. Вернитесь к списку заказов.", reply_markup=self.parent._orders_menu_markup(user_id))
            return
        
        self.parent.update_user_state(user_id, 'state', 'waiting_for_order_comment')
        from telebot import types
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
        markup.row("⬅️ К списку заказов")
        markup.row("⬅️ Главное меню")
        self.bot.reply_to(message, f"💬 Введите комментарий для заказа №{order_number}:", reply_markup=markup)
    
    def handle_edit_entrance(self, message):
        """Обработка кнопки 'Подъезд'"""
        user_id = message.from_user.id
        state_data = self.parent.get_user_state(user_id)
        order_number = state_data.get('updating_order_number')
        
        if not order_number:
            user_id = message.from_user.id
            self.bot.reply_to(message, "❌ Заказ не выбран. Вернитесь к списку заказов.", reply_markup=self.parent._orders_menu_markup(user_id))
            return
        
        self.parent.update_user_state(user_id, 'state', 'waiting_for_order_entrance')
        from telebot import types
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
        markup.row("⬅️ К списку заказов")
        markup.row("⬅️ Главное меню")
        self.bot.reply_to(message, f"🏢 Введите номер подъезда для заказа №{order_number}:", reply_markup=markup)
    
    def handle_edit_apartment(self, message):
        """Обработка кнопки 'Квартира'"""
        user_id = message.from_user.id
        state_data = self.parent.get_user_state(user_id)
        order_number = state_data.get('updating_order_number')
        
        if not order_number:
            user_id = message.from_user.id
            self.bot.reply_to(message, "❌ Заказ не выбран. Вернитесь к списку заказов.", reply_markup=self.parent._orders_menu_markup(user_id))
            return
        
        self.parent.update_user_state(user_id, 'state', 'waiting_for_order_apartment')
        from telebot import types
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
        markup.row("⬅️ К списку заказов")
        markup.row("⬅️ Главное меню")
        self.bot.reply_to(message, f"🚪 Введите номер квартиры для заказа №{order_number}:", reply_markup=markup)
    
    def handle_edit_delivery_time(self, message):
        """Обработка кнопки 'Время доставки'"""
        user_id = message.from_user.id
        state_data = self.parent.get_user_state(user_id)
        order_number = state_data.get('updating_order_number')
        
        if not order_number:
            user_id = message.from_user.id
            self.bot.reply_to(message, "❌ Заказ не выбран. Вернитесь к списку заказов.", reply_markup=self.parent._orders_menu_markup(user_id))
            return
        
        self.parent.update_user_state(user_id, 'state', 'waiting_for_order_delivery_time')
        from telebot import types
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
        markup.row("⬅️ К списку заказов")
        markup.row("⬅️ Главное меню")
        self.bot.reply_to(message, f"🕐 Введите время доставки для заказа №{order_number} (формат ЧЧ:ММ - ЧЧ:ММ):\nПример: 10:00 - 13:00", reply_markup=markup)
    
    def handle_edit_arrival_time(self, message):
        """Обработка кнопки 'Время прибытия'"""
        user_id = message.from_user.id
        state_data = self.parent.get_user_state(user_id)
        order_number = state_data.get('updating_order_number')
        
        if not order_number:
            user_id = message.from_user.id
            self.bot.reply_to(message, "❌ Заказ не выбран. Вернитесь к списку заказов.", reply_markup=self.parent._orders_menu_markup(user_id))
            return
        
        self.parent.update_user_state(user_id, 'state', 'waiting_for_manual_arrival_time')
        from telebot import types
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
        markup.row("⬅️ К списку заказов")
        markup.row("⬅️ Главное меню")
        self.bot.reply_to(message, f"⏰ Введите время прибытия для заказа №{order_number} (формат ЧЧ:ММ):\nПример: 14:20", reply_markup=markup)
    
    def handle_edit_call_time(self, message):
        """Обработка кнопки 'Время звонка'"""
        user_id = message.from_user.id
        state_data = self.parent.get_user_state(user_id)
        order_number = state_data.get('updating_order_number')
        
        if not order_number:
            user_id = message.from_user.id
            self.bot.reply_to(message, "❌ Заказ не выбран. Вернитесь к списку заказов.", reply_markup=self.parent._orders_menu_markup(user_id))
            return
        
        self.parent.update_user_state(user_id, 'state', 'waiting_for_manual_call_time')
        from telebot import types
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
        markup.row("⬅️ К списку заказов")
        markup.row("⬅️ Главное меню")
        self.bot.reply_to(message, f"📞⏰ Введите время звонка для заказа №{order_number} (формат ЧЧ:ММ):\nПример: 14:20", reply_markup=markup)
    
    def handle_back_to_orders_list(self, message):
        """Обработка кнопки 'К списку заказов'"""
        user_id = message.from_user.id
        self.parent.update_user_state(user_id, 'state', None)
        self.parent.update_user_state(user_id, 'updating_order_number', None)
        self.handle_order_details_start(message)
    
    # ==================== ОБРАБОТКА СОСТОЯНИЙ ====================
    
    def process_order_state(self, message, current_state, state_data):
        """Обработка сообщений в состояниях заказов"""
        try:
            if current_state == 'waiting_for_orders':
                self.process_order_number(message)
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
            elif current_state == 'waiting_for_manual_arrival_time':
                self.process_manual_arrival_time(message, state_data)
            elif current_state == 'waiting_for_manual_call_time':
                self.process_manual_call_time(message, state_data)
            elif current_state == 'searching_order_by_number':
                self.process_search_order_by_number(message, state_data)
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
            
            order_dto = self.parent.order_service.get_order_by_number(user_id, order_number)
            if not order_dto:
                self.bot.reply_to(
                    message,
                    f"❌ Заказ №{order_number} не найден",
                    reply_markup=self.parent._orders_menu_markup(user_id)
                )
                return
            # Преобразуем DTO в словарь для совместимости
            # Используем .dict() или .model_dump() в зависимости от версии Pydantic
            try:
                order = order_dto.dict() if hasattr(order_dto, 'dict') and callable(order_dto.dict) else order_dto.model_dump()
            except AttributeError:
                order = order_dto.model_dump() if hasattr(order_dto, 'model_dump') else {}
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
    
    def handle_photo(self, message):
        """Обработка фотографий (скриншотов заказов)"""
        user_id = message.from_user.id
        logger.info(f"📸 Получено изображение от user_id={user_id}, message_id={message.message_id}")
        
        # Получаем фото с максимальным разрешением
        photo = message.photo[-1] if message.photo else None
        if not photo:
            logger.error(f"❌ Не удалось получить изображение из сообщения user_id={user_id}")
            self.bot.reply_to(message, "❌ Не удалось получить изображение")
            return
        
        logger.info(f"📷 Изображение получено: file_id={photo.file_id}, размер={photo.file_size} байт")
        
        # Отправляем статус
        status_msg = self.bot.reply_to(
            message,
            "🔄 <b>Обработка изображения...</b>\n\n"
            "⏳ Извлекаю данные из скриншота...",
            parse_mode='HTML'
        )
        
        try:
            # Загружаем изображение
            logger.info(f"⬇️ Загрузка файла изображения: file_id={photo.file_id}")
            file_info = self.bot.get_file(photo.file_id)
            logger.debug(f"📁 Информация о файле: file_path={file_info.file_path}, file_size={file_info.file_size}")
            
            image_data = self.bot.download_file(file_info.file_path)
            logger.info(f"✅ Изображение загружено: {len(image_data)} байт")
            
            # Парсим изображение через OrderService (интеграция с ImageOrderParser внутри сервиса)
            logger.info(f"🔍 Начало парсинга изображения для user_id={user_id} через OrderService")
            order_dto = self.parent.order_service.parse_order_from_image(user_id, image_data)
            # Используем .dict() или .model_dump() в зависимости от версии Pydantic
            try:
                order_data = order_dto.dict() if hasattr(order_dto, 'dict') and callable(order_dto.dict) else order_dto.model_dump()
            except AttributeError:
                order_data = order_dto.model_dump() if hasattr(order_dto, 'model_dump') else {} if order_dto else None

            if not order_data:
                logger.warning(f"⚠️ Не удалось извлечь данные из изображения user_id={user_id}")
                self.bot.edit_message_text(
                    "❌ <b>Не удалось извлечь данные</b>\n\n"
                    "Возможные причины:\n"
                    "• Низкое качество изображения\n"
                    "• Нечитаемый текст\n"
                    "• Неподдерживаемый формат\n\n"
                    "Попробуйте:\n"
                    "• Отправить более четкий скриншот\n"
                    "• Убедиться, что текст хорошо виден\n"
                    "• Или введите данные вручную",
                    message.chat.id,
                    status_msg.message_id,
                    parse_mode='HTML'
                )
                return
            
            logger.info(f"✅ Данные успешно извлечены для user_id={user_id}: order_number={order_data.get('order_number')}")
            logger.debug(f"📋 Полные извлеченные данные: {order_data}")
            
            # Проверяем, существует ли уже заказ с таким номером
            order_exists = False
            if order_data.get('order_number'):
                today = date.today()
                existing_order_dto = self.parent.order_service.get_order_by_number(user_id, order_data['order_number'], today)
                # Используем .dict() или .model_dump() в зависимости от версии Pydantic
                if existing_order_dto:
                    try:
                        existing_order = existing_order_dto.dict() if hasattr(existing_order_dto, 'dict') and callable(existing_order_dto.dict) else existing_order_dto.model_dump()
                    except AttributeError:
                        existing_order = existing_order_dto.model_dump() if hasattr(existing_order_dto, 'model_dump') else {}
                else:
                    existing_order = None
                if existing_order:
                    order_exists = True
                    logger.info(f"⚠️ Заказ {order_data['order_number']} уже существует в БД для user_id={user_id}, date={today}")
            
            # Показываем извлеченные данные для подтверждения
            # Преобразуем все значения в строки, проверяя что это примитивы
            def safe_str(value):
                """Безопасное преобразование значения в строку"""
                if value is None:
                    return None
                # Проверяем что это примитивный тип
                if isinstance(value, (str, int, float, bool)):
                    return str(value)
                # Если это datetime/time объект, преобразуем в строку
                if hasattr(value, 'strftime'):
                    return value.strftime('%H:%M' if hasattr(value, 'hour') else '%Y-%m-%d %H:%M:%S')
                # Для других типов просто преобразуем в строку (но это не должно происходить)
                logger.warning(f"Неожиданный тип данных в order_data: {type(value)} = {value}")
                return str(value)
            
            preview_text = "📋 <b>Извлеченные данные:</b>\n\n"
            if order_data.get('order_number'):
                order_num = safe_str(order_data['order_number'])
                if order_num:
                    preview_text += f"📦 <b>Номер заказа:</b> {order_num}\n"
            if order_data.get('address'):
                address = safe_str(order_data['address'])
                if address:
                    preview_text += f"📍 <b>Адрес:</b> {address}\n"
            if order_data.get('customer_name'):
                name = safe_str(order_data['customer_name'])
                if name:
                    preview_text += f"👤 <b>Имя:</b> {name}\n"
            if order_data.get('phone'):
                phone = safe_str(order_data['phone'])
                if phone:
                    preview_text += f"📞 <b>Телефон:</b> {phone}\n"
            if order_data.get('delivery_time_window'):
                time_window = safe_str(order_data['delivery_time_window'])
                if time_window:
                    preview_text += f"🕐 <b>Время доставки:</b> {time_window}\n"
            if order_data.get('comment'):
                comment = safe_str(order_data['comment'])
                if comment:
                    preview_text += f"💬 <b>Комментарий:</b> {comment}\n"
            
            from telebot import types
            markup = types.InlineKeyboardMarkup()
            
            if order_exists:
                preview_text += "\n⚠️ <b>Заказ уже существует!</b>\n\n💾 Перезаписать заказ?"
                markup.add(types.InlineKeyboardButton("🔄 Перезаписать", callback_data=f"overwrite_order_from_image_{user_id}"))
            else:
                preview_text += "\n💾 Сохранить заказ?"
                markup.add(types.InlineKeyboardButton("✅ Сохранить", callback_data=f"save_order_from_image_{user_id}"))
            
            markup.add(types.InlineKeyboardButton("❌ Отмена", callback_data="cancel_save_order"))
            
            # Сохраняем данные во временное состояние
            self.parent.update_user_state(user_id, 'pending_order_from_image', order_data)
            logger.debug(f"💾 Данные сохранены во временное состояние для user_id={user_id}")
            
            self.bot.edit_message_text(
                preview_text,
                message.chat.id,
                status_msg.message_id,
                parse_mode='HTML',
                reply_markup=markup
            )
            logger.info(f"✅ Превью данных отправлено пользователю user_id={user_id}")
            
        except Exception as e:
            logger.error(f"❌ Критическая ошибка обработки изображения для user_id={user_id}: {e}", exc_info=True)
            self.bot.edit_message_text(
                f"❌ <b>Ошибка обработки</b>\n\n{str(e)}\n\n"
                "Попробуйте отправить изображение еще раз или введите данные вручную.",
                message.chat.id,
                status_msg.message_id,
                parse_mode='HTML'
            )
    
    def handle_load_from_screenshot(self, message):
        """Обработка кнопки 'Загрузить из скриншота'"""
        user_id = message.from_user.id
        logger.info(f"📸 Пользователь user_id={user_id} выбрал загрузку из скриншота")
        
        text = (
            "📸 <b>Загрузка заказа из скриншота</b>\n\n"
            "Отправьте скриншот страницы заказа, и бот автоматически извлечет данные:\n\n"
            "✅ <b>Что будет извлечено:</b>\n"
            "• Номер заказа\n"
            "• Адрес доставки\n"
            "• Имя покупателя\n"
            "• Телефон\n"
            "• Комментарий\n"
            "• Время доставки\n\n"
            "💡 <b>Советы:</b>\n"
            "• Убедитесь, что текст на скриншоте четкий и читаемый\n"
            "• Скриншот должен содержать полную информацию о заказе\n"
            "• После извлечения данных вы сможете проверить и сохранить заказ\n\n"
            "📷 <b>Отправьте скриншот сейчас</b>"
        )
        user_id = message.from_user.id
        self.bot.reply_to(message, text, parse_mode='HTML', reply_markup=self.parent._orders_menu_markup(user_id))
    
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
            "📸 <b>Формат 3 (скриншот):</b>\n"
            "Используйте кнопку <b>📸 Загрузить из скриншота</b> для автоматического извлечения данных.\n\n"
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
                user_id = message.from_user.id
                self.bot.reply_to(message, "❌ Нет добавленных заказов", reply_markup=self.parent._orders_menu_markup(user_id))
                return

            # Сохраняем заказы в БД
            today = date.today()
            saved_count = 0
            errors = []
            for i, order_data in enumerate(orders):
                try:
                    # Преобразуем строки времени обратно в time объекты
                    order_dict = order_data.copy()
                    
                    # Адрес необязателен при сохранении - можно добавить позже через редактирование
                    # Но предупреждаем пользователя
                    if not order_dict.get('address'):
                        logger.warning(f"Заказ {i+1} (№{order_dict.get('order_number', 'неизвестен')}) сохранен без адреса - добавьте адрес через редактирование")
                    
                    # Проверяем обязательность номера заказа
                    if not order_dict.get('order_number'):
                        errors.append(f"Заказ {i+1}: отсутствует номер заказа (обязательное поле)")
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
                    
                    # Сохраняем через OrderService
                    from src.application.dto.order_dto import CreateOrderDTO
                    create_dto = CreateOrderDTO(**order_dict)
                    self.parent.order_service.create_order(user_id, create_dto, today)
                    saved_count += 1
                except Exception as e:
                    error_msg = f"Заказ {i+1}: {str(e)}"
                    errors.append(error_msg)
                    # Преобразуем order_data в безопасный формат для логирования (без объектов)
                    safe_order_data = {k: str(v) if not isinstance(v, (str, int, float, bool, type(None))) else v 
                                     for k, v in order_data.items()} if isinstance(order_data, dict) else str(order_data)
                    logger.error(f"Ошибка сохранения заказа {i+1}: {e}, данные: {safe_order_data}", exc_info=True)
            
            # Очищаем временные данные
            self.parent.update_user_state(user_id, 'state', None)
            self.parent.update_user_state(user_id, 'orders', [])
            
            response_text = f"✅ Сохранено {saved_count} заказов за сегодня ({today.strftime('%d.%m.%Y')})"
            if errors:
                response_text += f"\n\n⚠️ Ошибки при сохранении:\n" + "\n".join(errors[:5])
            
            self.bot.reply_to(message, response_text, reply_markup=self.parent._orders_menu_markup(user_id))
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
                    raise ValueError("Недостаточно данных в расширенном формате. Формат: Имя|Телефон|Адрес|Комментарий")
                # Расширенный формат: Имя|Телефон|Адрес|Комментарий
                # Но номер заказа можно указать в начале: НомерЗаказа|Имя|Телефон|Адрес|Комментарий
                # Или в конце: Имя|Телефон|Адрес|Комментарий|НомерЗаказа
                order_number = None
                customer_name = None
                phone = None
                address = None
                comment = None
                
                # Проверяем, есть ли номер заказа (6+ цифр) в первой или последней части
                if len(parts) > 0:
                    first_part = parts[0].strip()
                    if re.match(r'^\d{6,}$', first_part):
                        # Номер заказа в начале
                        order_number = first_part
                        if len(parts) >= 2:
                            customer_name = parts[1].strip() if parts[1].strip() else None
                        if len(parts) >= 3:
                            phone = parts[2].strip() if parts[2].strip() else None
                        if len(parts) >= 4:
                            address = parts[3].strip()
                        if len(parts) >= 5:
                            comment = parts[4].strip() if parts[4].strip() else None
                    else:
                        # Обычный формат: Имя|Телефон|Адрес|Комментарий
                        customer_name = first_part if first_part else None
                        if len(parts) >= 2:
                            phone = parts[1].strip() if parts[1].strip() else None
                        if len(parts) >= 3:
                            address = parts[2].strip()
                        if len(parts) >= 4:
                            comment = parts[3].strip() if parts[3].strip() else None
                        # Проверяем последнюю часть на номер заказа
                        if len(parts) >= 4 and re.match(r'^\d{6,}$', parts[-1].strip()):
                            order_number = parts[-1].strip()
                            comment = parts[3].strip() if len(parts) > 4 and parts[3].strip() else None
                
                # Адрес необязателен - можно добавить позже
                if not order_number:
                    raise ValueError("Номер заказа обязателен. Укажите его в начале или конце: НомерЗаказа|Имя|Телефон|Адрес или Имя|Телефон|Адрес|НомерЗаказа")
                
                order = Order(
                    customer_name=customer_name,
                    phone=phone,
                    address=address if address else "",
                    comment=comment,
                    order_number=order_number
                )
                return order.model_dump()

            # Формат: Время НомерЗаказа Адрес
            time_pattern = r'(\d{1,2}:\d{2}\s*-\s*\d{1,2}:\d{2})'
            time_match = re.search(time_pattern, line)

            if time_match:
                time_window = time_match.group(1).strip()
                remaining_text = line.replace(time_window, '').strip()
                # Ищем номер заказа (6+ цифр) - может быть с пробелом после или без
                # Паттерн: номер заказа (6+ цифр), затем либо пробел и адрес, либо конец строки
                order_num_match = re.match(r'(\d{6,})\s*(.*)$', remaining_text)
                if order_num_match:
                    order_number = order_num_match.group(1)
                    address = order_num_match.group(2).strip()
                else:
                    # Пробуем найти номер заказа в любом месте строки (6+ цифр подряд)
                    order_num_match = re.search(r'\b(\d{6,})\b', remaining_text)
                    if order_num_match:
                        order_number = order_num_match.group(1)
                        # Адрес - это все что до и после номера заказа
                        address = remaining_text.replace(order_number, '').strip()
                    else:
                        raise ValueError("Не найден номер заказа (должно быть минимум 6 цифр)")
            else:
                # Без времени - проверяем, есть ли номер заказа в начале
                order_num_match = re.match(r'(\d{6,})\s+(.+)$', line)
                if order_num_match:
                    order_number = order_num_match.group(1)
                    address = order_num_match.group(2).strip()
                    time_window = None
                else:
                    # Пробуем найти номер заказа в любом месте
                    order_num_match = re.search(r'\b(\d{6,})\b', line)
                    if order_num_match:
                        order_number = order_num_match.group(1)
                        address = line.replace(order_number, '').strip()
                        time_window = None
                    else:
                        # Нет номера заказа - это ошибка для формата 1
                        raise ValueError("Не найден номер заказа. Формат: Время НомерЗаказа Адрес")

            # Адрес необязателен - можно добавить позже через редактирование
            # Но если адрес указан, он должен быть не слишком коротким
            if address and len(address) < 3:
                raise ValueError("Адрес слишком короткий (минимум 3 символа)")

            # Если адрес не указан, используем пустую строку (БД требует не-null значение)
            # Пользователь сможет добавить адрес позже через редактирование
            order = Order(
                address=address if address else "",
                order_number=order_number,
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

            address_short = (order_data.get('address') or 'Адрес не указан')[:50] + "..." if order_data.get('address') and len(order_data['address']) > 50 else (order_data.get('address') or 'Адрес не указан')

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
    
    def handle_view_delivered(self, call):
        """Обработчик callback для просмотра доставленных заказов"""
        user_id = call.from_user.id
        chat_id = call.message.chat.id
        self.bot.answer_callback_query(call.id)
        self.show_delivered_orders(user_id, chat_id)
    
    def show_delivered_orders(self, user_id: int, chat_id: int):
        """Показать список доставленных заказов"""
        today = date.today()
        
        # Загружаем через OrderService
        orders_data = self.parent.get_today_orders_dict(user_id, today)
        
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
        
        logger.info(f"handle_order_details_start вызван для user_id={user_id}")
        
        try:
            # Загружаем через OrderService
            orders_data = self.parent.get_today_orders_dict(user_id, today)
            logger.debug(f"Загружено заказов: {len(orders_data) if orders_data else 0}")
        except Exception as e:
            logger.error(f"Ошибка загрузки заказов для редактирования: {e}", exc_info=True)
            self.bot.reply_to(
                message,
                f"❌ Ошибка загрузки заказов: {str(e)}",
                reply_markup=self.parent._orders_menu_markup(user_id)
            )
            return
        
        if not orders_data:
            user_id = message.from_user.id
            self.bot.reply_to(
                message,
                "❌ Нет добавленных заказов",
                reply_markup=self.parent._orders_menu_markup(user_id)
            )
            return
        
        # Фильтруем только не доставленные заказы
        active_orders = [od for od in orders_data if od.get('status', 'pending') != 'delivered']
        
        if not active_orders:
            self.bot.reply_to(
                message,
                "✅ Все заказы доставлены!",
                reply_markup=self.parent._orders_menu_markup(message.from_user.id)
            )
            return
        
        # Формируем только кнопки с информацией
        from telebot import types
        
        # Сортируем по порядку в маршруте (если есть), иначе по номеру заказа
        try:
            route_data = self.parent.get_route_data_dict(user_id, today)
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
            if address:
                short_address = address
                address_parts = address.split(',')
                if len(address_parts) >= 2:
                    short_address = ','.join(address_parts[-2:]).strip()
                elif len(address_parts) == 1:
                    short_address = address_parts[0].strip()
            else:
                short_address = "Адрес не указан"
            
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
        
        # Загружаем заказ через OrderService
        try:
            order_dto = self.parent.order_service.get_order_by_number(user_id, order_number, today)
            if not order_dto:
                self.bot.send_message(chat_id, f"❌ Заказ №{order_number} не найден", reply_markup=self.parent._main_menu_markup())
                return
            # Используем .dict() или .model_dump() в зависимости от версии Pydantic
            try:
                order_data = order_dto.dict() if hasattr(order_dto, 'dict') and callable(order_dto.dict) else order_dto.model_dump()
            except AttributeError:
                order_data = order_dto.model_dump() if hasattr(order_dto, 'model_dump') else {}
        except Exception as e:
            logger.error(f"Ошибка загрузки заказа из БД: {e}", exc_info=True)
            self.bot.send_message(chat_id, f"❌ Ошибка загрузки данных: {str(e)}", reply_markup=self.parent._main_menu_markup())
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
            f"📍 <b>Адрес:</b> {order.address if order.address else 'Не указан'}",
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
        # Проверяем наличие ручных времен в call_status
        from src.database.connection import get_db_session
        from src.models.order import CallStatusDB
        
        manual_call_time_display = None
        manual_arrival_time_display = None
        
        # Загружаем call_status для заказа
        with get_db_session() as session:
            call_status = session.query(CallStatusDB).filter(
                CallStatusDB.user_id == user_id,
                CallStatusDB.order_number == order_number,
                CallStatusDB.call_date == today
            ).first()
            
            # ВАЖНО: Извлекаем данные ВНУТРИ сессии
            if call_status:
                if getattr(call_status, "is_manual_call", False) and call_status.call_time:
                    manual_call_time_display = call_status.call_time.strftime('%H:%M')
                if getattr(call_status, "is_manual_arrival", False) and call_status.manual_arrival_time:
                    manual_arrival_time_display = call_status.manual_arrival_time.strftime('%H:%M')
        
        # Отображаем РУЧНОЕ время прибытия из call_status
        if manual_arrival_time_display:
            details.append(f"⏰ <b>Время прибытия (ручное):</b> {manual_arrival_time_display}")
            logger.debug(f"Отображено ручное время прибытия из call_status: {manual_arrival_time_display}")
        else:
            details.append(f"⏰ <b>Время прибытия (ручное):</b> Не указано")
        
        # Отображаем РУЧНОЕ время звонка (из call_status.is_manual)
        if manual_call_time_display:
            details.append(f"📞⏰ <b>Время звонка (ручное):</b> {manual_call_time_display}")
            logger.debug(f"Отображено ручное время звонка из call_status: {manual_call_time_display}")
        else:
            details.append(f"📞⏰ <b>Время звонка (ручное):</b> Не указано")
        
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
        
        # Обновляем статус через OrderService
        updated = self.parent.order_service.mark_delivered(user_id, order_number, today)
        
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
                route_data = self.parent.get_route_data_dict(user_id, today)
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
                            orders_data = self.parent.get_today_orders_dict(user_id, today)
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
            
            logger.info(f"Обновление времени прибытия для заказа {order_number}: {manual_time.isoformat()}")
            
            # Обновляем в БД - вызываем специальный метод
            self._update_manual_arrival_time(user_id, order_number, manual_time, message)
            
            logger.info(f"Время прибытия успешно обновлено для заказа {order_number}")
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
            
            logger.info(f"Обновление времени звонка для заказа {order_number}: {manual_time.isoformat()}")
            
            # Обновляем в БД и создаем/обновляем call_status
            self._update_manual_call_time(user_id, order_number, manual_time, message)
            
            logger.info(f"Время звонка успешно обновлено для заказа {order_number}")
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
                reply_markup=self.parent._orders_menu_markup(user_id)
            )
            return
        
        # Ищем заказ через OrderService
        try:
            today = date.today()
            order_dto = self.parent.order_service.get_order_by_number(user_id, text, today)
            
            if order_dto:
                # Открываем детали заказа
                self.show_order_details(user_id, text, message.chat.id)
                self.parent.update_user_state(user_id, 'state', None)
            else:
                self.bot.reply_to(
                    message,
                    f"❌ Заказ №{text} не найден. Попробуйте еще раз или вернитесь в главное меню:",
                    reply_markup=self.parent._orders_menu_markup(user_id)
                )
        except Exception as e:
            logger.error(f"Ошибка при поиске заказа: {e}", exc_info=True)
            self.bot.reply_to(message, f"❌ Ошибка: {str(e)}", reply_markup=self.parent._orders_menu_markup(user_id))
            self.parent.update_user_state(user_id, 'state', None)
    
    def _update_manual_call_time(self, user_id: int, order_number: str, manual_call_time: datetime, message):
        """Обновить ручное время звонка в call_status"""
        today = date.today()
        
        # Получаем настройки пользователя для расчета arrival_time
        user_settings = self.parent.settings_service.get_settings(user_id)
        
        # Рассчитываем время прибытия из времени звонка
        from datetime import timedelta
        calculated_arrival_time = manual_call_time + timedelta(minutes=user_settings.call_advance_minutes)
        
        # Обновляем или создаем call_status
        from src.database.connection import get_db_session
        from src.models.order import CallStatusDB
        
        # Получаем заказ через OrderService
        order_dto = self.parent.order_service.get_order_by_number(user_id, order_number, today)
        if not order_dto:
            logger.error(f"Заказ {order_number} не найден при установке времени звонка")
            return
        
        order_data = order_dto.model_dump()
        
        # Проверяем наличие телефона
        if not order_data.get('phone'):
            logger.warning(f"У заказа {order_number} нет телефона, но устанавливается время звонка")
        
        # Проверяем, установлено ли уже ручное время прибытия
        # Если да, используем его вместо рассчитанного
        manual_arrival = order_data.get('manual_arrival_time')
        if manual_arrival:
            if isinstance(manual_arrival, str):
                from datetime import datetime as dt
                manual_arrival = dt.fromisoformat(manual_arrival)
            arrival_time_to_use = manual_arrival
            logger.info(f"⚠️ Время прибытия для заказа {order_number} уже установлено вручную ({manual_arrival.strftime('%H:%M')}), используем его")
        else:
            arrival_time_to_use = calculated_arrival_time
        
        with get_db_session() as session:
            call_status = session.query(CallStatusDB).filter(
                CallStatusDB.user_id == user_id,
                CallStatusDB.order_number == order_number,
                CallStatusDB.call_date == today
            ).first()
            
            if call_status:
                # Обновляем существующую запись
                call_status.call_time = manual_call_time
                call_status.arrival_time = arrival_time_to_use
                call_status.is_manual_call = True
                # is_manual_arrival сохраняем как есть
                if call_status.status in ['confirmed', 'failed', 'sent']:
                    call_status.status = 'pending'
                    call_status.attempts = 0
                session.commit()
                logger.info(f"Обновлено ручное время звонка для заказа {order_number}: звонок {manual_call_time.strftime('%H:%M')}, прибытие {arrival_time_to_use.strftime('%H:%M')}")
            else:
                # Создаем новую запись
                # Получаем phone и customer_name из заказа, используем дефолты если отсутствуют
                phone = order_data.get('phone') or 'Не указан'
                customer_name = order_data.get('customer_name') or 'Не указано'
                
                new_call_status = CallStatusDB(
                    user_id=user_id,
                    order_number=order_number,
                    call_date=today,
                    call_time=manual_call_time,
                    arrival_time=arrival_time_to_use,
                    manual_arrival_time=manual_arrival if manual_arrival else None,
                    is_manual_call=True,
                    is_manual_arrival=bool(manual_arrival),
                    phone=phone,
                    customer_name=customer_name,
                    status='pending',
                    attempts=0
                )
                session.add(new_call_status)
                session.commit()
                logger.info(f"Создана запись о ручном звонке для заказа {order_number}: звонок {manual_call_time.strftime('%H:%M')}, прибытие {arrival_time_to_use.strftime('%H:%M')}")
        
        # Показываем подтверждение
        markup = self.parent._main_menu_markup()
        
        # Определяем метку для времени прибытия
        if manual_arrival:
            arrival_label = "Время прибытия (ручное)"
        else:
            arrival_label = "Расчетное время прибытия"
        
        text = (
            f"✅ <b>Время звонка обновлено!</b>\n\n"
            f"Заказ №{order_number}\n"
            f"<b>Время звонка:</b> {manual_call_time.strftime('%H:%M')}\n"
            f"<b>{arrival_label}:</b> {arrival_time_to_use.strftime('%H:%M')}\n\n"
            f"Выберите следующее поле для обновления:"
        )
        self.bot.reply_to(message, text, parse_mode='HTML', reply_markup=markup)
    
    def _update_manual_arrival_time(self, user_id: int, order_number: str, manual_arrival_time: datetime, message):
        """Обновить ручное время прибытия в orders и создать call_status"""
        today = date.today()
        
        # Получаем настройки пользователя для расчета call_time
        user_settings = self.parent.settings_service.get_settings(user_id)
        
        # Рассчитываем время звонка из времени прибытия
        from datetime import timedelta
        calculated_call_time = manual_arrival_time - timedelta(minutes=user_settings.call_advance_minutes)
        
        # ВАЖНО: Сначала загружаем данные заказа ДО обновления, чтобы проверить текущее состояние
        from src.database.connection import get_db_session
        from src.models.order import CallStatusDB
        
        # Получаем заказ через OrderService
        order_dto = self.parent.order_service.get_order_by_number(user_id, order_number, today)
        if not order_dto:
            logger.error(f"Заказ {order_number} не найден при установке времени прибытия")
            return
        
        order_data = order_dto.model_dump()
        
        # Проверяем наличие телефона
        if not order_data.get('phone'):
            logger.warning(f"У заказа {order_number} нет телефона, но устанавливается время прибытия")
        
        # 2. Обновляем или создаем call_status (переносим ручное прибытие в call_status)
        from src.database.connection import get_db_session
        from src.models.order import CallStatusDB
        with get_db_session() as session:
            call_status = session.query(CallStatusDB).filter(
                CallStatusDB.user_id == user_id,
                CallStatusDB.order_number == order_number,
                CallStatusDB.call_date == today
            ).first()
            
            call_time_was_manual = call_status.is_manual_call if call_status else False
            if call_time_was_manual:
                logger.info(f"⚠️ Время звонка для заказа {order_number} было установлено вручную, не изменяем его")
            
            call_time_to_set = call_status.call_time if call_time_was_manual and call_status else calculated_call_time
            
            if call_status:
                call_status.call_time = call_time_to_set
                call_status.arrival_time = manual_arrival_time
                call_status.manual_arrival_time = manual_arrival_time
                call_status.is_manual_arrival = True
                # Флаг ручного звонка сохраняем, не трогаем
                # Если статус был confirmed/failed - сбрасываем на pending
                if call_status.status in ['confirmed', 'failed', 'sent']:
                    call_status.status = 'pending'
                    call_status.attempts = 0
                session.commit()
                logger.info(
                    f"Обновлено ручное время прибытия для заказа {order_number}: "
                    f"звонок {call_status.call_time.strftime('%H:%M')} ({'ручное' if call_time_was_manual else 'авто'}), "
                    f"прибытие {manual_arrival_time.strftime('%H:%M')}"
                )
            else:
                phone = order_data.get('phone') or 'Не указан'
                customer_name = order_data.get('customer_name') or 'Не указано'
                
                new_call_status = CallStatusDB(
                    user_id=user_id,
                    order_number=order_number,
                    call_date=today,
                    call_time=calculated_call_time,
                    arrival_time=manual_arrival_time,
                    manual_arrival_time=manual_arrival_time,
                    is_manual_call=False,
                    is_manual_arrival=True,
                    phone=phone,
                    customer_name=customer_name,
                    status='pending',
                    attempts=0
                )
                session.add(new_call_status)
                session.commit()
                logger.info(
                    f"Создана запись о ручном времени прибытия для заказа {order_number}: "
                    f"звонок {calculated_call_time.strftime('%H:%M')} (авто), прибытие {manual_arrival_time.strftime('%H:%M')} (ручное)"
                )
        
        # Показываем подтверждение
        markup = self.parent._main_menu_markup()
        
        # Определяем какое время звонка показывать
        with get_db_session() as session:
            call_status = session.query(CallStatusDB).filter(
                CallStatusDB.user_id == user_id,
                CallStatusDB.order_number == order_number,
                CallStatusDB.call_date == today
            ).first()
            
            if call_status and call_status.call_time:
                actual_call_time = call_status.call_time
                # Проверяем, ручное ли это время или рассчитанное
                time_diff_minutes = (manual_arrival_time - actual_call_time).total_seconds() / 60
                if abs(time_diff_minutes - user_settings.call_advance_minutes) > 1:
                    call_time_label = "Время звонка (ручное)"
                else:
                    call_time_label = "Расчетное время звонка"
            else:
                actual_call_time = calculated_call_time
                call_time_label = "Расчетное время звонка"
        
        text = (
            f"✅ <b>Время прибытия обновлено!</b>\n\n"
            f"Заказ №{order_number}\n"
            f"<b>Время прибытия:</b> {manual_arrival_time.strftime('%H:%M')}\n"
            f"<b>{call_time_label}:</b> {actual_call_time.strftime('%H:%M')}\n\n"
            f"Выберите следующее поле для обновления:"
        )
        self.bot.reply_to(message, text, parse_mode='HTML', reply_markup=markup)
    
    def _update_order_field(self, user_id: int, order_number: str, field_name: str, field_value: str, message):
        """Обновить конкретное поле заказа"""
        today = date.today()
        
        # Загружаем заказ через OrderService
        order_dto = self.parent.order_service.get_order_by_number(user_id, order_number, today)
        if not order_dto:
            self.bot.reply_to(message, f"❌ Заказ №{order_number} не найден", reply_markup=self.parent._main_menu_markup())
            return
        
        order_data = order_dto.model_dump()
        
        # Обновляем поле
        updates = {field_name: field_value}
        
        # Если обновлен подъезд, обновляем адрес (БЕЗ геокодирования - координаты остаются те же)
        if field_name == 'entrance_number':
            original_address = order_data.get('address') or ''
            if original_address:
                # Удаляем старый подъезд из адреса, если есть
                import re
                address_clean = re.sub(r',\s*подъезд\s+\d+', '', original_address, flags=re.IGNORECASE)
                address_clean = re.sub(r'\s+подъезд\s+\d+', '', address_clean, flags=re.IGNORECASE)
                updates['address'] = f"{address_clean}, подъезд {field_value}"
            else:
                # Если адреса нет, просто добавляем подъезд
                updates['address'] = f"подъезд {field_value}"
            
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
        
        # ВАЖНО: manual_arrival_time и manual_call_time больше не хранятся в orders
        # Они обновляются через специальные методы (_update_manual_arrival_time, _update_manual_call_time)
        # и хранятся в call_status
        if field_name in ['manual_arrival_time', 'manual_call_time']:
            logger.warning(f"Попытка обновить {field_name} через _update_order_field - это поле больше не в OrderDB")
            # Удаляем из updates, чтобы не пытаться обновить в БД
            return
        
            # Обновляем через OrderService
        try:
            from src.application.dto.order_dto import UpdateOrderDTO
            update_dto = UpdateOrderDTO(**updates)
            self.parent.order_service.update_order(user_id, order_number, update_dto, today)
            
            # Обновляем call_status актуальными данными из OrderDB
            # Это нужно для того, чтобы напоминания о звонках использовали актуальные данные
            from src.database.connection import get_db_session
            from src.models.order import CallStatusDB
            with get_db_session() as session:
                call_status = session.query(CallStatusDB).filter(
                    CallStatusDB.user_id == user_id,
                    CallStatusDB.order_number == order_number,
                    CallStatusDB.call_date == today
                ).first()
                
                if call_status:
                    # Получаем обновленный заказ через OrderService
                    updated_order_dto = self.parent.order_service.get_order_by_number(user_id, order_number, today)
                    if updated_order_dto:
                        # Обновляем телефон, если он изменился
                        if field_name == 'phone' or (updated_order_dto.phone and call_status.phone != updated_order_dto.phone):
                            call_status.phone = updated_order_dto.phone or call_status.phone
                            # Если статус был "sent" (уведомление уже отправлено), сбрасываем на pending для повторной отправки
                            if call_status.status == "sent":
                                call_status.status = "pending"
                                call_status.attempts = 0  # Сбрасываем счетчик попыток
                            logger.debug(f"Обновлен телефон в call_status для заказа {order_number}: {call_status.phone}")
                        
                        # Обновляем имя клиента, если оно изменилось
                        if field_name == 'customer_name' or (updated_order_dto.customer_name and call_status.customer_name != updated_order_dto.customer_name):
                            call_status.customer_name = updated_order_dto.customer_name or call_status.customer_name
                            logger.debug(f"Обновлено имя в call_status для заказа {order_number}: {call_status.customer_name}")
                        
                        session.commit()
                        logger.info(f"✅ Обновлен call_status для заказа {order_number} актуальными данными из OrderDB")
                else:
                    # Если записи нет, создаем ее (если есть маршрут)
                    route_data_check = self.parent.get_route_data_dict(user_id, today)
                    if route_data_check and route_data_check.get('route_points_data'):
                        # Находим время звонка из route_points_data
                        route_points_data_check = route_data_check.get('route_points_data', [])
                        route_order_check = route_data_check.get('route_order', [])
                        try:
                            order_index = route_order_check.index(order_number)
                            if order_index < len(route_points_data_check):
                                point_data = route_points_data_check[order_index]
                                call_time_str = point_data.get('call_time')
                                arrival_time_str = point_data.get('estimated_arrival')
                                if call_time_str:
                                    call_time = datetime.fromisoformat(call_time_str)
                                    arrival_time = datetime.fromisoformat(arrival_time_str) if arrival_time_str else None
                                    # Загружаем актуальные данные заказа через OrderService
                                    updated_order_dto = self.parent.order_service.get_order_by_number(user_id, order_number, today)
                                    
                                    if updated_order_dto:
                                        # Создаем запись о звонке (автоматическое время)
                                        self.parent.call_notifier.create_call_status(
                                            user_id,
                                            order_number,
                                            call_time,
                                            updated_order_dto.phone or "Не указан",
                                            updated_order_dto.customer_name,
                                            today,
                                            is_manual_call=False,
                                            is_manual_arrival=False,
                                            arrival_time=arrival_time,
                                            manual_arrival_time=None
                                        )
                                        logger.debug(f"Создана запись call_status для заказа {order_number} при обновлении заказа")
                        except (ValueError, KeyError, Exception) as e:
                            logger.warning(f"Не удалось создать call_status при обновлении заказа: {e}")
            
            # Обновляем маршрут если он существует
            route_data = self.parent.get_route_data_dict(user_id, today)
            if route_data and (route_data.get('route_summary') or route_data.get('route_points_data')):
                # Загружаем обновленный заказ через OrderService
                updated_order_dto = self.parent.order_service.get_order_by_number(user_id, order_number, today)
                
                if updated_order_dto:
                    # Если обновлены поля, влияющие на маршрут - пересчитываем маршрут
                    if field_name in ['address', 'entrance_number', 'apartment_number', 'delivery_time_window']:
                        # Пересчитываем маршрут через RouteService
                        from src.application.dto.route_dto import RouteOptimizationRequest
                        optimization_request = RouteOptimizationRequest(recalculate_without_manual=False)
                        result = self.parent.route_service.optimize_route(user_id, today, optimization_request)
                        
                        if result.success:
                            logger.info(f"✅ Маршрут пересчитан после обновления заказа {order_number}")
                        else:
                            logger.warning(f"⚠️ Не удалось пересчитать маршрут: {result.error_message}")
                        
                        # Маршрут пересчитан через RouteService
                        logger.info(f"✅ Маршрут пересчитан после обновления заказа {order_number}")
                    
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
            
            # Форматируем значение для отображения
            display_value = field_value
            if field_name in ['manual_arrival_time', 'manual_call_time']:
                try:
                    dt = datetime.fromisoformat(field_value)
                    display_value = dt.strftime('%H:%M')
                except:
                    display_value = field_value
            
            text = (
                f"✅ <b>{field_names.get(field_name, 'Поле')} обновлено!</b>\n\n"
                f"Заказ №{order_number}\n"
                f"<b>Новое значение:</b> {display_value}\n\n"
                f"Выберите следующее поле для обновления:"
            )
            self.bot.reply_to(message, text, parse_mode='HTML', reply_markup=markup)
        except Exception as e:
            logger.error(f"Ошибка обновления заказа в БД: {e}", exc_info=True)
            self.bot.reply_to(message, f"❌ Ошибка обновления заказа: {str(e)}", reply_markup=self.parent._main_menu_markup())