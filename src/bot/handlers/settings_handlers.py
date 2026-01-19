"""
Обработчики для работы с настройками пользователя
"""
import logging
from telebot import types

logger = logging.getLogger(__name__)


class SettingsHandlers:
    """Обработчики настроек"""
    
    def __init__(self, bot_instance):
        self.bot = bot_instance.bot
        self.parent = bot_instance
    
    def register(self):
        """Регистрация обработчиков"""
        # Нет прямых команд - только через меню ⚙️ Настройки
        logger.info("✅ Settings handlers зарегистрированы")
    
    def handle_callback(self, call):
        """Обработка callback запросов для настроек"""
        callback_data = call.data
        
        if callback_data == "settings_back":
            self.handle_settings_back(call)
        elif callback_data == "settings_reset":
            self.handle_settings_reset(call)
        elif callback_data == "settings_reset_day":
            self.handle_reset_day_from_settings(call)
        elif callback_data == "settings_chefmarket_creds":
            self.handle_chefmarket_credentials_menu(call)
        else:
            # Обработка конкретной настройки
            setting_name = callback_data.replace("settings_", "")
            self.handle_setting_update(call, setting_name)
    
    def show_settings_menu(self, message):
        """Показать меню настроек"""
        user_id = message.from_user.id
        settings = self.parent.settings_service.get_settings(user_id)
        
        # Проверяем наличие учетных данных ШефМаркет
        has_chefmarket_creds = self.parent.credentials_service.has_credentials(user_id, "chefmarket")
        chefmarket_status = "✅ Настроено" if has_chefmarket_creds else "❌ Не настроено"
        
        # Формируем текст с текущими настройками
        text = (
            "⚙️ <b>Настройки</b>\n\n"
            f"📞 <b>Звонки:</b>\n"
            f"• Звонить за {settings.call_advance_minutes} мин до приезда\n"
            f"• Повтор через {settings.call_retry_interval_minutes} мин\n"
            f"• Максимум попыток: {settings.call_max_attempts}\n\n"
            f"⏱️ <b>Время:</b>\n"
            f"• На точке: {settings.service_time_minutes} мин\n\n"
            f"🚦 <b>Пробки:</b>\n"
            f"• Проверка каждые {settings.traffic_check_interval_minutes} мин\n"
            f"• Уведомлять при увеличении на {settings.traffic_threshold_percent}%\n\n"
            f"📲 <b>Импорт заказов:</b>\n"
            f"• ШефМаркет: {chefmarket_status}\n\n"
            "Выберите параметр для изменения:"
        )
        
        markup = types.InlineKeyboardMarkup(row_width=1)
        markup.add(
            types.InlineKeyboardButton("📲 Учетные данные ШефМаркет", callback_data="settings_chefmarket_creds"),
            types.InlineKeyboardButton("⏱️ Время звонка до приезда", callback_data="settings_call_advance"),
            types.InlineKeyboardButton("🔄 Интервал повторных звонков", callback_data="settings_call_retry"),
            types.InlineKeyboardButton("📞 Макс. попыток дозвона", callback_data="settings_call_attempts"),
            types.InlineKeyboardButton("⏰ Время на точке", callback_data="settings_service_time"),
            types.InlineKeyboardButton("🚦 Интервал проверки пробок", callback_data="settings_traffic_interval"),
            types.InlineKeyboardButton("⚠️ Порог уведомлений о пробках", callback_data="settings_traffic_threshold"),
            types.InlineKeyboardButton("🔄 Сбросить к умолчанию", callback_data="settings_reset"),
            types.InlineKeyboardButton("🗑️ Сбросить день", callback_data="settings_reset_day"),
            types.InlineKeyboardButton("⬅️ Назад", callback_data="settings_back")
        )
        
        self.bot.reply_to(message, text, parse_mode='HTML', reply_markup=markup)
    
    def handle_setting_update(self, call, setting_name: str):
        """Обработка запроса на изменение настройки"""
        user_id = call.from_user.id
        
        # Описания и текущие значения
        settings = self.parent.settings_service.get_settings(user_id)
        setting_info = {
            'call_advance': {
                'name': 'call_advance_minutes',
                'title': '⏱️ Время звонка до приезда',
                'description': 'За сколько минут до приезда звонить клиенту',
                'current': settings.call_advance_minutes,
                'min': 1,
                'max': 60,
                'unit': 'минут'
            },
            'call_retry': {
                'name': 'call_retry_interval_minutes',
                'title': '🔄 Интервал повторных звонков',
                'description': 'Через сколько минут повторить звонок после отклонения',
                'current': settings.call_retry_interval_minutes,
                'min': 1,
                'max': 15,
                'unit': 'минут'
            },
            'call_attempts': {
                'name': 'call_max_attempts',
                'title': '📞 Максимум попыток дозвона',
                'description': 'Сколько раз пытаться дозвониться',
                'current': settings.call_max_attempts,
                'min': 1,
                'max': 10,
                'unit': 'раз'
            },
            'service_time': {
                'name': 'service_time_minutes',
                'title': '⏰ Время на точке',
                'description': 'Сколько времени тратится на доставку одного заказа',
                'current': settings.service_time_minutes,
                'min': 1,
                'max': 60,
                'unit': 'минут'
            },
            'traffic_interval': {
                'name': 'traffic_check_interval_minutes',
                'title': '🚦 Интервал проверки пробок',
                'description': 'Как часто проверять изменения в пробках',
                'current': settings.traffic_check_interval_minutes,
                'min': 1,
                'max': 60,
                'unit': 'минут'
            },
            'traffic_threshold': {
                'name': 'traffic_threshold_percent',
                'title': '⚠️ Порог уведомлений о пробках',
                'description': 'При каком увеличении времени уведомлять',
                'current': settings.traffic_threshold_percent,
                'min': 10,
                'max': 200,
                'unit': '%'
            }
        }
        
        info = setting_info.get(setting_name)
        if not info:
            self.bot.answer_callback_query(call.id, "❌ Неизвестная настройка")
            return
        
        # Сохраняем информацию о текущей настройке в состоянии
        self.parent.update_user_state(user_id, 'state', 'waiting_for_setting_value')
        self.parent.update_user_state(user_id, 'pending_setting_name', info['name'])
        self.parent.update_user_state(user_id, 'pending_setting_min', info['min'])
        self.parent.update_user_state(user_id, 'pending_setting_max', info['max'])
        
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
        markup.row("❌ Отмена")
        
        self.bot.answer_callback_query(call.id)
        self.bot.send_message(
            user_id,
            f"{info['title']}\n\n"
            f"📝 {info['description']}\n"
            f"📊 Текущее значение: <b>{info['current']} {info['unit']}</b>\n"
            f"📏 Диапазон: {info['min']}-{info['max']} {info['unit']}\n\n"
            f"Введите новое значение:",
            parse_mode='HTML',
            reply_markup=markup
        )
    
    def handle_setting_value(self, message, state_data):
        """Обработка нового значения настройки"""
        user_id = message.from_user.id
        setting_name = state_data.get('pending_setting_name')
        min_val = state_data.get('pending_setting_min', 0)
        max_val = state_data.get('pending_setting_max', 100)
        
        try:
            value = int(message.text.strip())
            
            if value < min_val or value > max_val:
                self.bot.reply_to(
                    message,
                    f"❌ Значение должно быть от {min_val} до {max_val}. Попробуйте еще раз:"
                )
                return
            
            # Обновляем настройку
            success = self.parent.settings_service.update_setting(user_id, setting_name, value)
            
            if success:
                # Если изменилось время звонка, пересчитываем расписание для существующего маршрута
                if setting_name == 'call_advance_minutes':
                    from datetime import date
                    today = date.today()
                    recalc_success = self.parent.route_service.recalculate_call_times(user_id, today)
                    if recalc_success:
                        logger.info(f"✅ Пересчитаны времена звонков для user_id={user_id} после изменения настройки")
                
                self.parent.update_user_state(user_id, 'state', None)
                self.parent.update_user_state(user_id, 'pending_setting_name', None)
                
                setting_description = self.parent.settings_service.get_setting_description(setting_name)
                
                response_text = f"✅ Настройка обновлена!\n\n{setting_description}: <b>{value}</b>"
                
                # Дополнительное сообщение при изменении времени звонка
                if setting_name == 'call_advance_minutes':
                    response_text += "\n\n📅 Расписание звонков для текущего маршрута обновлено автоматически"
                
                self.bot.reply_to(
                    message,
                    response_text,
                    parse_mode='HTML',
                    reply_markup=self.parent._main_menu_markup()
                )
            else:
                self.bot.reply_to(
                    message,
                    "❌ Ошибка при обновлении настройки",
                    reply_markup=self.parent._main_menu_markup()
                )
        except ValueError:
            self.bot.reply_to(
                message,
                "❌ Пожалуйста, введите целое число:"
            )
    
    def handle_settings_reset(self, call):
        """Сброс настроек к значениям по умолчанию"""
        user_id = call.from_user.id
        
        success = self.parent.settings_service.reset_settings(user_id)
        
        if success:
            settings = self.parent.settings_service.get_settings(user_id)
            text = (
                "✅ <b>Настройки сброшены к значениям по умолчанию</b>\n\n"
                f"📞 Звонить за {settings.call_advance_minutes} мин\n"
                f"🔄 Повтор через {settings.call_retry_interval_minutes} мин\n"
                f"📞 Максимум попыток: {settings.call_max_attempts}\n"
                f"⏰ На точке: {settings.service_time_minutes} мин\n"
                f"🚦 Проверка пробок: {settings.traffic_check_interval_minutes} мин\n"
                f"⚠️ Порог пробок: {settings.traffic_threshold_percent}%"
            )
            self.bot.answer_callback_query(call.id, "✅ Настройки сброшены")
            self.bot.edit_message_text(
                text,
                call.message.chat.id,
                call.message.message_id,
                parse_mode='HTML'
            )
            self.bot.send_message(
                call.message.chat.id,
                "🏠 Главное меню",
                reply_markup=self.parent._main_menu_markup()
            )
        else:
            self.bot.answer_callback_query(call.id, "❌ Ошибка сброса настроек", show_alert=True)
    
    def handle_settings_back(self, call):
        """Возврат в главное меню из настроек"""
        self.bot.answer_callback_query(call.id)
        self.bot.edit_message_text(
            "🏠 Главное меню",
            call.message.chat.id,
            call.message.message_id
        )
        self.bot.send_message(
            call.message.chat.id,
            "Выберите действие:",
            reply_markup=self.parent._main_menu_markup()
        )
    
    def handle_chefmarket_credentials_menu(self, call):
        """Меню управления учетными данными ШефМаркет"""
        user_id = call.from_user.id
        has_creds = self.parent.credentials_service.has_credentials(user_id, "chefmarket")
        
        markup = types.InlineKeyboardMarkup(row_width=1)
        
        if has_creds:
            text = (
                "📲 <b>Учетные данные ШефМаркет</b>\n\n"
                "✅ Логин и пароль сохранены и зашифрованы\n\n"
                "Вы можете:\n"
                "• Обновить учетные данные\n"
                "• Удалить их\n"
                "• Использовать /import_orders для загрузки заказов"
            )
            markup.add(
                types.InlineKeyboardButton("🔄 Обновить данные", callback_data="chefmarket_update_creds"),
                types.InlineKeyboardButton("🗑️ Удалить данные", callback_data="chefmarket_delete_creds"),
                types.InlineKeyboardButton("⬅️ Назад к настройкам", callback_data="chefmarket_back_to_settings")
            )
        else:
            text = (
                "📲 <b>Учетные данные ШефМаркет</b>\n\n"
                "❌ Логин и пароль не настроены\n\n"
                "Чтобы использовать автоматический импорт заказов,\n"
                "нужно сохранить учетные данные от сайта deliver.chefmarket.ru\n\n"
                "🔒 <b>Безопасность:</b>\n"
                "• Данные шифруются (Fernet)\n"
                "• Хранятся только в вашей БД\n"
                "• Используются только для импорта"
            )
            markup.add(
                types.InlineKeyboardButton("➕ Добавить данные", callback_data="chefmarket_add_creds"),
                types.InlineKeyboardButton("⬅️ Назад к настройкам", callback_data="chefmarket_back_to_settings")
            )
        
        self.bot.answer_callback_query(call.id)
        self.bot.edit_message_text(
            text,
            call.message.chat.id,
            call.message.message_id,
            parse_mode='HTML',
            reply_markup=markup
        )
    
    def handle_reset_day_from_settings(self, call):
        """Обработка запроса на сброс дня из настроек"""
        # Создаем FakeMessage для вызова handle_reset_day
        class FakeMessage:
            def __init__(self, call):
                self.from_user = call.from_user
                self.chat = call.message.chat
                self.text = "🗑️ Сбросить день"
        
        fake_message = FakeMessage(call)
        # Перенаправляем в route_handlers для обработки
        self.parent.routes.handle_reset_day(fake_message)
