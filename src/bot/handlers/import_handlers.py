"""
Обработчики для импорта заказов из внешних систем (ШефМаркет)
"""
import logging
import asyncio
from datetime import date
from telebot import types
from src.services.chefmarket_parser import ChefMarketParser

logger = logging.getLogger(__name__)


class ImportHandlers:
    """Обработчики импорта заказов"""
    
    def __init__(self, bot_instance):
        self.bot = bot_instance.bot
        self.parent = bot_instance
        self.parser = ChefMarketParser()
    
    def register(self):
        """Регистрация обработчиков"""
        # Регистрация команд
        self.bot.register_message_handler(
            self.handle_set_credentials,
            commands=['set_credentials']
        )
        self.bot.register_message_handler(
            self.handle_delete_credentials,
            commands=['delete_credentials']
        )
        self.bot.register_message_handler(
            self.handle_import_orders,
            commands=['import_orders']
        )
        
        logger.info("✅ Import handlers зарегистрированы")
    
    def handle_callback(self, call):
        """Обработка callback запросов для импорта (chefmarket_*)"""
        callback_data = call.data
        
        if callback_data == "chefmarket_add_creds" or callback_data == "chefmarket_update_creds":
            self.handle_chefmarket_add_credentials(call)
        elif callback_data == "chefmarket_delete_creds":
            self.handle_chefmarket_delete_credentials(call)
        elif callback_data == "chefmarket_back_to_settings":
            # Возврат к настройкам
            self.bot.answer_callback_query(call.id)
            # Удаляем старое сообщение и показываем меню настроек
            self.bot.delete_message(call.message.chat.id, call.message.message_id)
            from types import SimpleNamespace
            fake_msg = SimpleNamespace(from_user=call.from_user, chat=call.message.chat)
            self.parent.settings.show_settings_menu(fake_msg)
    
    # === Команды /set_credentials, /delete_credentials, /import_orders ===
    
    def handle_set_credentials(self, message):
        """Сохранение учетных данных: /set_credentials логин пароль"""
        user_id = message.from_user.id
        args = message.text.split()[1:]
        
        if len(args) < 2:
            self.bot.reply_to(
                message,
                "❌ <b>Неверный формат</b>\n\n"
                "Используйте: /set_credentials логин пароль\n\n"
                "Пример:\n"
                "<code>/set_credentials ivan@mail.ru mypassword123</code>",
                parse_mode='HTML'
            )
            return
        
        login = args[0]
        password = args[1]
        
        # Сохраняем учетные данные
        success = self.parent.credentials_service.save_credentials(user_id, login, password, "chefmarket")
        
        if success:
            # Удаляем сообщение с паролем для безопасности
            try:
                self.bot.delete_message(message.chat.id, message.message_id)
            except:
                pass
            
            self.bot.send_message(
                message.chat.id,
                "✅ <b>Учетные данные сохранены!</b>\n\n"
                "🔒 Логин и пароль зашифрованы и надежно хранятся в базе данных\n\n"
                "Теперь вы можете использовать:\n"
                "📦 /import_orders - импорт заказов из ШефМаркет",
                parse_mode='HTML'
            )
        else:
            self.bot.reply_to(
                message,
                "❌ Ошибка сохранения учетных данных. Попробуйте позже."
            )
    
    def handle_delete_credentials(self, message):
        """Удаление учетных данных: /delete_credentials"""
        user_id = message.from_user.id
        
        success = self.parent.credentials_service.delete_credentials(user_id, "chefmarket")
        
        if success:
            self.bot.reply_to(
                message,
                "✅ Учетные данные удалены из базы данных"
            )
        else:
            self.bot.reply_to(
                message,
                "ℹ️ У вас нет сохраненных учетных данных"
            )
    
    def handle_import_orders(self, message):
        """Импорт заказов из ШефМаркет: /import_orders"""
        user_id = message.from_user.id
        
        # Проверяем наличие учетных данных
        if not self.parent.credentials_service.has_credentials(user_id, "chefmarket"):
            self.bot.reply_to(
                message,
                "❌ <b>Учетные данные не найдены</b>\n\n"
                "Сначала сохраните логин и пароль от ШефМаркет:\n"
                "/set_credentials логин пароль",
                parse_mode='HTML'
            )
            return
        
        # Получаем учетные данные
        credentials = self.parent.credentials_service.get_credentials(user_id, "chefmarket")
        if not credentials:
            self.bot.reply_to(message, "❌ Ошибка получения учетных данных")
            return
        
        login, password = credentials
        
        # Отправляем статус
        status_msg = self.bot.reply_to(
            message,
            "🔄 <b>Импорт заказов...</b>\n\n"
            "⏳ Авторизация на сайте ШефМаркет...",
            parse_mode='HTML'
        )
        
        # Запускаем импорт в async контексте
        try:
            orders = asyncio.run(self._import_orders_async(user_id, login, password, status_msg))
            
            if orders:
                self.bot.edit_message_text(
                    f"✅ <b>Импорт завершен!</b>\n\n"
                    f"📦 Добавлено заказов: {len(orders)}\n"
                    f"📍 Адреса загеокодированы\n\n"
                    f"Используйте <b>▶️ Оптимизировать</b> для построения маршрута",
                    message.chat.id,
                    status_msg.message_id,
                    parse_mode='HTML'
                )
            else:
                self.bot.edit_message_text(
                    "ℹ️ Заказы не найдены или уже были импортированы",
                    message.chat.id,
                    status_msg.message_id
                )
        
        except Exception as e:
            logger.error(f"Ошибка импорта: {e}", exc_info=True)
            self.bot.edit_message_text(
                f"❌ <b>Ошибка импорта</b>\n\n"
                f"{str(e)}\n\n"
                f"Возможные причины:\n"
                f"• Неверный логин/пароль\n"
                f"• Сайт ШефМаркет недоступен\n"
                f"• Изменилась структура сайта\n\n"
                f"Попробуйте:\n"
                f"1. Проверить данные: /set_credentials\n"
                f"2. Попробовать позже",
                message.chat.id,
                status_msg.message_id,
                parse_mode='HTML'
            )
    
    async def _import_orders_async(self, user_id: int, login: str, password: str, status_msg):
        """Асинхронный импорт заказов"""
        today = date.today()
        
        # Парсим заказы
        self.bot.edit_message_text(
            "🔄 <b>Импорт заказов...</b>\n\n"
            "📋 Получение списка заказов...",
            status_msg.chat.id,
            status_msg.message_id,
            parse_mode='HTML'
        )
        
        orders = await self.parser.import_orders(login, password, today)
        
        if not orders:
            return []
        
        # Сохраняем заказы в БД
        self.bot.edit_message_text(
            f"🔄 <b>Импорт заказов...</b>\n\n"
            f"📦 Найдено: {len(orders)}\n"
            f"💾 Сохранение в базу данных...",
            status_msg.chat.id,
            status_msg.message_id,
            parse_mode='HTML'
        )
        
        imported_count = 0
        for order_data in orders:
            try:
                # Проверяем, не импортирован ли уже
                existing_orders = self.parent.db_service.get_today_orders(user_id)
                if any(o.get('order_number') == order_data['order_number'] for o in existing_orders):
                    logger.info(f"Заказ {order_data['order_number']} уже существует, пропускаем")
                    continue
                
                # Добавляем заказ
                self.parent.db_service.add_order(user_id, order_data, today)
                imported_count += 1
            except Exception as e:
                logger.error(f"Ошибка сохранения заказа {order_data.get('order_number')}: {e}")
        
        logger.info(f"Импортировано {imported_count} из {len(orders)} заказов")
        return orders[:imported_count] if imported_count > 0 else []
    
    # === Управление учетными данными через callback (из меню Настройки) ===
    
    def handle_chefmarket_add_credentials(self, call):
        """Запрос на добавление учетных данных через меню"""
        user_id = call.from_user.id
        
        # Устанавливаем состояние ожидания логина
        self.parent.update_user_state(user_id, 'state', 'waiting_for_chefmarket_login')
        
        text = (
            "📲 <b>Настройка учетных данных ШефМаркет</b>\n\n"
            "Шаг 1/2: Введите ваш логин от deliver.chefmarket.ru\n\n"
            "💡 Обычно это email или номер телефона"
        )
        
        self.bot.answer_callback_query(call.id)
        self.bot.edit_message_text(
            text,
            call.message.chat.id,
            call.message.message_id,
            parse_mode='HTML'
        )
    
    def handle_chefmarket_delete_credentials(self, call):
        """Удаление учетных данных через меню"""
        user_id = call.from_user.id
        
        success = self.parent.credentials_service.delete_credentials(user_id, "chefmarket")
        
        if success:
            text = (
                "✅ <b>Учетные данные удалены</b>\n\n"
                "Данные ШефМаркет успешно удалены из базы.\n"
                "Автоматический импорт заказов больше недоступен."
            )
            self.bot.answer_callback_query(call.id, "✅ Данные удалены")
        else:
            text = "❌ Ошибка удаления данных"
            self.bot.answer_callback_query(call.id, "❌ Ошибка", show_alert=True)
        
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("⬅️ Назад к настройкам", callback_data="chefmarket_back_to_settings"))
        
        self.bot.edit_message_text(
            text,
            call.message.chat.id,
            call.message.message_id,
            parse_mode='HTML',
            reply_markup=markup
        )
    
    # === Обработка ввода логина/пароля (вызывается из основного обработчика сообщений) ===
    
    def process_chefmarket_login(self, message, state_data):
        """Обработка ввода логина ШефМаркет"""
        user_id = message.from_user.id
        login = message.text.strip()
        
        if not login or len(login) < 3:
            self.bot.reply_to(
                message,
                "❌ Логин слишком короткий. Попробуйте еще раз:",
                parse_mode='HTML'
            )
            return
        
        # Сохраняем логин во временное состояние
        self.parent.update_user_state(user_id, 'chefmarket_login', login)
        self.parent.update_user_state(user_id, 'state', 'waiting_for_chefmarket_password')
        
        text = (
            "📲 <b>Настройка учетных данных ШефМаркет</b>\n\n"
            f"✅ Логин: <code>{login}</code>\n\n"
            "Шаг 2/2: Введите ваш пароль\n\n"
            "🔒 Пароль будет зашифрован и надежно сохранен"
        )
        
        self.bot.reply_to(message, text, parse_mode='HTML')
    
    def process_chefmarket_password(self, message, state_data):
        """Обработка ввода пароля ШефМаркет"""
        user_id = message.from_user.id
        password = message.text.strip()
        login = state_data.get('chefmarket_login')
        
        if not password or len(password) < 3:
            self.bot.reply_to(
                message,
                "❌ Пароль слишком короткий. Попробуйте еще раз:",
                parse_mode='HTML'
            )
            return
        
        if not login:
            self.bot.reply_to(
                message,
                "❌ Ошибка: логин не найден. Начните сначала через меню Настройки.",
                reply_markup=self.parent._main_menu_markup()
            )
            self.parent.clear_user_state(user_id)
            return
        
        # Удаляем сообщение с паролем для безопасности
        try:
            self.bot.delete_message(message.chat.id, message.message_id)
        except:
            pass
        
        # Сохраняем учетные данные
        success = self.parent.credentials_service.save_credentials(user_id, login, password, "chefmarket")
        
        if success:
            text = (
                "✅ <b>Учетные данные сохранены!</b>\n\n"
                f"📧 Логин: <code>{login}</code>\n"
                f"🔒 Пароль: зашифрован\n\n"
                "Теперь вы можете использовать:\n"
                "📦 /import_orders - импорт заказов\n\n"
                "Управление данными: ⚙️ Настройки → 📲 ШефМаркет"
            )
            logger.info(f"Сохранены учетные данные ШефМаркет для user_id={user_id}")
        else:
            text = (
                "❌ <b>Ошибка сохранения данных</b>\n\n"
                "Не удалось сохранить учетные данные.\n"
                "Попробуйте еще раз через меню Настройки."
            )
            logger.error(f"Ошибка сохранения учетных данных ШефМаркет для user_id={user_id}")
        
        # Очищаем состояние
        self.parent.clear_user_state(user_id)
        
        self.bot.send_message(
            message.chat.id,
            text,
            parse_mode='HTML',
            reply_markup=self.parent._main_menu_markup()
        )
