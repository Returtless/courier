"""
Обработчики для работы со звонками
"""
import logging
from datetime import datetime, timedelta
from telebot import types
from src.database.connection import get_db_session
from src.application.services.call_service import get_local_now

logger = logging.getLogger(__name__)


class CallHandlers:
    """Обработчики звонков"""
    
    def __init__(self, bot_instance):
        self.bot = bot_instance.bot
        self.parent = bot_instance
    
    def register(self):
        """Регистрация обработчиков"""
        # Нет прямых команд/кнопок, только callback
        logger.info("✅ Call handlers зарегистрированы")
    
    def handle_callback(self, call):
        """Обработка callback запросов для звонков"""
        callback_data = call.data
        
        if callback_data.startswith("call_confirm_"):
            call_status_id = int(callback_data.replace("call_confirm_", ""))
            self.handle_call_confirm(call, call_status_id)
        elif callback_data.startswith("call_reject_"):
            call_status_id = int(callback_data.replace("call_reject_", ""))
            self.handle_call_reject(call, call_status_id)
    
    def handle_call_confirm(self, call, call_status_id: int):
        """Обработка подтверждения звонка"""
        user_id = call.from_user.id
        
        try:
            # Получаем статус звонка через CallService
            with get_db_session() as session:
                call_status_dto = self.parent.call_service.get_call_status_by_id(call_status_id, session)
            
            if not call_status_dto:
                self.bot.answer_callback_query(call.id, "❌ Запись о звонке не найдена", show_alert=True)
                return
            
            # Проверяем, что звонок принадлежит этому пользователю (через DTO)
            if call_status_dto.user_id != user_id:
                self.bot.answer_callback_query(call.id, "❌ Запись о звонке не найдена", show_alert=True)
                return
            
            # Подтверждаем звонок через CallService (без комментария пока)
            with get_db_session() as session:
                success = self.parent.call_service.confirm_call(user_id, call_status_id, None, session)
            
            if not success:
                self.bot.answer_callback_query(call.id, "❌ Ошибка подтверждения звонка", show_alert=True)
                return
            
            # Обновляем сообщение, убирая кнопки
            customer_info = call_status_dto.customer_name or "Клиент"
            order_info = f"Заказ №{call_status_dto.order_number}" if call_status_dto.order_number else "Заказ"
            
            updated_text = (
                f"📞 <b>Время звонка!</b>\n\n"
                f"👤 {customer_info}\n"
                f"📦 {order_info}\n"
                f"📱 {call_status_dto.phone}\n"
                f"🕐 Время: {call_status_dto.call_time.strftime('%H:%M')}\n\n"
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
            
            # Запрашиваем комментарий
            self.bot.answer_callback_query(call.id, "✅ Звонок подтвержден")
            self.parent.update_user_state(user_id, 'state', 'waiting_for_call_comment')
            self.parent.update_user_state(user_id, 'pending_call_status_id', call_status_id)
            
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
        user_id = call.from_user.id
        
        try:
            # Получаем статус звонка через CallService
            with get_db_session() as session:
                call_status_dto = self.parent.call_service.get_call_status_by_id(call_status_id, session)
            
            if not call_status_dto:
                self.bot.answer_callback_query(call.id, "❌ Запись о звонке не найдена", show_alert=True)
                return
            
            # Проверяем, что звонок принадлежит этому пользователю (через DTO)
            if call_status_dto.user_id != user_id:
                self.bot.answer_callback_query(call.id, "❌ Запись о звонке не найдена", show_alert=True)
                return
            
            # Получаем настройки пользователя
            user_settings = self.parent.settings_service.get_settings(user_id)
            
            customer_info = call_status_dto.customer_name or "Клиент"
            order_info = f"Заказ №{call_status_dto.order_number}" if call_status_dto.order_number else "Заказ"
            
            # Отклоняем звонок через CallService
            with get_db_session() as session:
                success = self.parent.call_service.reject_call(user_id, call_status_id, session)
            
            if not success:
                self.bot.answer_callback_query(call.id, "❌ Ошибка отклонения звонка", show_alert=True)
                return
            
            # Получаем обновленный статус для проверки количества попыток
            with get_db_session() as session:
                updated_call_status_dto = self.parent.call_service.get_call_status_by_id(call_status_id, session)
            
            if not updated_call_status_dto:
                self.bot.answer_callback_query(call.id, "❌ Ошибка получения обновленного статуса", show_alert=True)
                return
            
            # Проверяем количество попыток после отклонения
            # Если достигли максимума (например, 3 попытки = attempts достиг 3)
            if updated_call_status_dto.attempts >= user_settings.call_max_attempts:
                # Превышено максимальное количество попыток
                updated_text = (
                    f"📞 <b>Время звонка!</b>\n\n"
                    f"👤 {customer_info}\n"
                    f"📦 {order_info}\n"
                    f"📱 {call_status_dto.phone}\n"
                    f"🕐 Время: {call_status_dto.call_time.strftime('%H:%M')}\n\n"
                    f"❌ <b>Недозвон</b>\nПревышено количество попыток ({user_settings.call_max_attempts})"
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
                
                self.bot.answer_callback_query(call.id, f"❌ Превышено количество попыток ({user_settings.call_max_attempts})")
                self.bot.send_message(
                    call.message.chat.id,
                    f"❌ <b>Недозвон</b>\n\nЗаказ №{call_status_dto.order_number}\nПревышено количество попыток звонка ({user_settings.call_max_attempts})",
                    parse_mode='HTML',
                    reply_markup=self.parent._route_menu_markup()
                )
            else:
                # Планируем повторную попытку
                updated_text = (
                    f"📞 <b>Время звонка!</b>\n\n"
                    f"👤 {customer_info}\n"
                    f"📦 {order_info}\n"
                    f"📱 {call_status_dto.phone}\n"
                    f"🕐 Время: {call_status_dto.call_time.strftime('%H:%M')}\n\n"
                    f"❌ <b>Отклонено</b>\nПовтор через {user_settings.call_retry_interval_minutes} мин (попытка {updated_call_status_dto.attempts}/{user_settings.call_max_attempts})"
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
                
                self.bot.answer_callback_query(call.id, f"❌ Отклонено. Повтор через {user_settings.call_retry_interval_minutes} мин (попытка {updated_call_status_dto.attempts}/{user_settings.call_max_attempts})")
                self.bot.send_message(
                    call.message.chat.id,
                    f"⏰ <b>Повторный звонок запланирован</b>\n\nЗаказ №{call_status_dto.order_number}\nПовтор через {user_settings.call_retry_interval_minutes} мин (попытка {updated_call_status_dto.attempts}/{user_settings.call_max_attempts})",
                    parse_mode='HTML',
                    reply_markup=self.parent._route_menu_markup()
                )
        except Exception as e:
            logger.error(f"Ошибка при отклонении звонка: {e}", exc_info=True)
            self.bot.answer_callback_query(call.id, f"❌ Ошибка: {str(e)}", show_alert=True)
    
    def process_call_comment(self, message, state_data):
        """Обработка ввода комментария к звонку"""
        user_id = message.from_user.id
        text = message.text.strip()
        
        if text == "⬅️ Главное меню" or text == "⏭️ Пропустить комментарий" or text == "/skip":
            self.parent.update_user_state(user_id, 'state', None)
            self.parent.update_user_state(user_id, 'pending_call_status_id', None)
            self.bot.reply_to(message, "✅ Комментарий пропущен", reply_markup=self.parent._main_menu_markup())
            return
        
        call_status_id = state_data.get('pending_call_status_id')
        if not call_status_id:
            self.bot.reply_to(message, "❌ Ошибка: не найден ID звонка", reply_markup=self.parent._main_menu_markup())
            return
        
        try:
            # Сохраняем комментарий через CallService
            with get_db_session() as session:
                success = self.parent.call_service.confirm_call(user_id, call_status_id, text, session)
            
            if success:
                self.bot.reply_to(
                    message,
                    f"✅ <b>Комментарий сохранен</b>\n\n💬 {text}",
                    parse_mode='HTML',
                    reply_markup=self.parent._main_menu_markup()
                )
            else:
                self.bot.reply_to(message, "❌ Запись о звонке не найдена", reply_markup=self.parent._main_menu_markup())
        except Exception as e:
            logger.error(f"Ошибка при сохранении комментария: {e}", exc_info=True)
            self.bot.reply_to(message, f"❌ Ошибка: {str(e)}", reply_markup=self.parent._main_menu_markup())
        
        self.parent.update_user_state(user_id, 'state', None)
        self.parent.update_user_state(user_id, 'pending_call_status_id', None)

