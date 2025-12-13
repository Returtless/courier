import telebot
import logging
from src.config import settings
from src.database.connection import engine, Base
# Импортируем модели, чтобы они зарегистрировались в Base.metadata
from src.models.order import OrderDB, StartLocationDB, RouteDataDB, CallStatusDB, UserSettingsDB  # noqa: F401
from src.models.geocache import GeocodeCacheDB  # noqa: F401
# from src.services.llm_service import LLMService  # Пока отключено
from src.bot.handlers import CourierBot


def main():
    # Configure logging
    logging.basicConfig(level=logging.INFO)

    # Create database tables (модели должны быть импортированы выше)
    Base.metadata.create_all(bind=engine)
    logger = logging.getLogger(__name__)
    logger.info("✅ База данных инициализирована")

    # Initialize bot
    logger = logging.getLogger(__name__)
    if not settings.telegram_bot_token or settings.telegram_bot_token == "your_bot_token_here":
        logger.error("❌ Установите TELEGRAM_BOT_TOKEN в файле env")
        return

    bot = telebot.TeleBot(settings.telegram_bot_token)

    # Initialize services
    # llm_service = LLMService()  # Пока отключено
    llm_service = None

    # Initialize bot handler
    courier_bot = CourierBot(bot, llm_service)

    # Register handlers
    courier_bot.register_handlers()
    
    # Start call notifier
    courier_bot.call_notifier.start()

    # Start polling
    logger = logging.getLogger(__name__)
    logger.info("🤖 Courier Bot started!")
    try:
        bot.polling(none_stop=True)
    except KeyboardInterrupt:
        logger.info("\n🛑 Остановка бота...")
        courier_bot.call_notifier.stop()


if __name__ == "__main__":
    main()
