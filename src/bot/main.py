import telebot
import logging
from src.config import settings
from src.database.connection import engine, Base
# from src.services.llm_service import LLMService  # Пока отключено
from src.bot.handlers import CourierBot


def main():
    # Configure logging
    logging.basicConfig(level=logging.INFO)

    # Create database tables
    Base.metadata.create_all(bind=engine)

    # Initialize bot
    if not settings.telegram_bot_token or settings.telegram_bot_token == "your_bot_token_here":
        print("❌ Установите TELEGRAM_BOT_TOKEN в файле env")
        return

    bot = telebot.TeleBot(settings.telegram_bot_token)

    # Initialize services
    # llm_service = LLMService()  # Пока отключено
    llm_service = None

    # Initialize bot handler
    courier_bot = CourierBot(bot, llm_service)

    # Register handlers
    courier_bot.register_handlers()

    # Start polling
    print("🤖 Courier Bot started!")
    bot.polling(none_stop=True)


if __name__ == "__main__":
    main()
