"""
Обработчики для работы со звонками
"""
import logging
from datetime import datetime, timedelta
from sqlalchemy import and_
from telebot import types
from src.database.connection import get_db_session
from src.models.order import CallStatusDB
from src.services.call_notifier import get_local_now

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
                
                # Получаем настройки пользователя
                user_settings = self.parent.settings_service.get_settings(user_id)
                
                customer_info = call_status.customer_name or "Клиент"
                order_info = f"Заказ №{call_status.order_number}" if call_status.order_number else "Заказ"
                
                # Проверяем количество попыток
                if call_status.attempts >= user_settings.call_max_attempts:
                    # Превышено максимальное количество попыток
                    call_status.status = "failed"
                    call_status.next_attempt_time = None
                    session.commit()
                    
                    updated_text = (
                        f"📞 <b>Время звонка!</b>\n\n"
                        f"👤 {customer_info}\n"
                        f"📦 {order_info}\n"
                        f"📱 {call_status.phone}\n"
                        f"🕐 Время: {call_status.call_time.strftime('%H:%M')}\n\n"
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
                        f"❌ <b>Недозвон</b>\n\nЗаказ №{call_status.order_number}\nПревышено количество попыток звонка ({user_settings.call_max_attempts})",
                        parse_mode='HTML',
                        reply_markup=self.parent._route_menu_markup()
                    )
                else:
                    # Планируем повторную попытку
                    now = get_local_now()
                    if now.tzinfo is not None:
                        now = now.replace(tzinfo=None)
                    call_status.status = "rejected"
                    call_status.next_attempt_time = now + timedelta(minutes=user_settings.call_retry_interval_minutes)
                    session.commit()
                    
                    updated_text = (
                        f"📞 <b>Время звонка!</b>\n\n"
                        f"👤 {customer_info}\n"
                        f"📦 {order_info}\n"
                        f"📱 {call_status.phone}\n"
                        f"🕐 Время: {call_status.call_time.strftime('%H:%M')}\n\n"
                        f"❌ <b>Отклонено</b>\nПовтор через {user_settings.call_retry_interval_minutes} мин (попытка {call_status.attempts}/{user_settings.call_max_attempts})"
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
                    
                    self.bot.answer_callback_query(call.id, f"❌ Отклонено. Повтор через {user_settings.call_retry_interval_minutes} мин (попытка {call_status.attempts}/{user_settings.call_max_attempts})")
                    self.bot.send_message(
                        call.message.chat.id,
                        f"⏰ <b>Повторный звонок запланирован</b>\n\nЗаказ №{call_status.order_number}\nПовтор через {user_settings.call_retry_interval_minutes} мин (попытка {call_status.attempts}/{user_settings.call_max_attempts})",
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
            with get_db_session() as session:
                call_status = session.query(CallStatusDB).filter(CallStatusDB.id == call_status_id).first()
                if call_status:
                    call_status.confirmation_comment = text
                    session.commit()
                    
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

