import telebot
import logging
from src.config import settings
# Импортируем модели для использования в ORM запросах
from src.models.order import OrderDB, StartLocationDB, RouteDataDB, CallStatusDB, UserSettingsDB, UserCredentialsDB  # noqa: F401
from src.models.geocache import GeocodeCacheDB  # noqa: F401
# from src.services.llm_service import LLMService  # Пока отключено
from src.bot.handlers import CourierBot


def main():
    # Configure logging to stdout/stderr (для Docker/Portainer)
    import sys
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(sys.stdout)  # Явно указываем stdout
        ],
        force=True  # Перезаписываем существующую конфигурацию
    )
    # Отключаем буферизацию для stdout (чтобы логи появлялись сразу)
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(line_buffering=True)
    
    logger = logging.getLogger(__name__)
    logger.info("=" * 60)
    logger.info("🚀 Запуск Courier Bot")
    logger.info("=" * 60)

    # Применяем миграции (создают таблицы и изменяют схему)
    logger.info("🔄 Применение миграций базы данных...")
    try:
        # Добавляем корень проекта в путь для импорта migrate
        import sys
        from pathlib import Path
        project_root = Path(__file__).parent.parent.parent
        if str(project_root) not in sys.path:
            sys.path.insert(0, str(project_root))
        from scripts.migrate import run_migrations
        logger.info("📝 Вызов run_migrations()...")
        result = run_migrations()
        logger.info(f"📝 run_migrations() вернула: {result}")
        if not result:
            logger.error("❌ Ошибка применения миграций. Проверьте логи выше.")
            return
        logger.info("✅ База данных готова")
    except SystemExit as se:
        logger.warning(f"⚠️ SystemExit({se.code}) в main после миграций")
        if se.code != 0:
            raise
        logger.info("✅ SystemExit(0) - продолжаем работу бота")
    except Exception as e:
        logger.error(f"❌ Критическая ошибка при применении миграций: {e}", exc_info=True)
        return

    # Initialize bot
    logger.info("🔧 Инициализация бота...")
    if not settings.telegram_bot_token or settings.telegram_bot_token == "your_bot_token_here":
        logger.error("❌ Установите TELEGRAM_BOT_TOKEN в файле env")
        return

    try:
        bot = telebot.TeleBot(settings.telegram_bot_token)
        logger.info("✅ Telegram Bot инициализирован")
    except Exception as e:
        logger.error(f"❌ Ошибка инициализации Telegram Bot: {e}", exc_info=True)
        return

    # Initialize services
    # llm_service = LLMService()  # Пока отключено
    llm_service = None

    # Проверяем доступность Tesseract OCR для парсинга изображений
    logger.info("🔍 Проверка доступности Tesseract OCR...")
    try:
        from src.services.image_parser import ImageOrderParser
        test_parser = ImageOrderParser()
        logger.info("✅ Tesseract OCR доступен - парсинг изображений включен")
    except Exception as e:
        logger.warning(f"⚠️ Tesseract OCR недоступен: {e}")
        logger.warning("⚠️ Парсинг изображений будет недоступен. Установите Tesseract для использования этой функции.")
    
    # Initialize bot handler (все сервисы инициализируются внутри)
    logger.info("🔧 Инициализация обработчиков...")
    try:
        courier_bot = CourierBot(bot, llm_service)
        logger.info("✅ CourierBot инициализирован")
    except Exception as e:
        logger.error(f"❌ Ошибка инициализации CourierBot: {e}", exc_info=True)
        return

    # Register all handlers (включая import handlers)
    logger.info("🔧 Регистрация обработчиков...")
    try:
        courier_bot.register_handlers()
        logger.info("✅ Обработчики зарегистрированы")
    except Exception as e:
        logger.error(f"❌ Ошибка регистрации обработчиков: {e}", exc_info=True)
        return
    
    # Start call notifier
    logger.info("🔧 Запуск уведомлений о звонках...")
    try:
        courier_bot.call_notifier.start()
        logger.info("✅ Уведомления о звонках запущены")
    except Exception as e:
        logger.error(f"❌ Ошибка запуска уведомлений: {e}", exc_info=True)
        return

    # Start polling
    logger.info("🤖 Courier Bot started! Начинаю polling...")
    try:
        bot.polling(none_stop=True)
    except KeyboardInterrupt:
        logger.info("\n🛑 Остановка бота...")
        courier_bot.call_notifier.stop()
    except Exception as e:
        logger.error(f"❌ Критическая ошибка в polling: {e}", exc_info=True)
        raise


if __name__ == "__main__":
    main()
