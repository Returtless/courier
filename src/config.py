import os
from typing import Optional
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Telegram
    telegram_bot_token: str = "your_bot_token_here"

    # Maps API
    yandex_maps_api_key: Optional[str] = None
    two_gis_api_key: Optional[str] = None
    google_maps_api_key: Optional[str] = None

    # Database
    database_url: str = "sqlite:///./courier_bot.db"

    # LLM
    llm_model_path: str = "models/gemma3-4b"
    llm_device: str = "cpu"
    llm_max_tokens: int = 512

    # Security
    encryption_key: Optional[str] = None  # For encrypting sensitive data (will be auto-generated if not set)

    # Route optimization
    delivery_time_per_stop: int = 10  # minutes
    parking_walking_time: int = 7  # minutes
    call_advance_time: int = 40  # minutes before delivery
    traffic_check_interval: int = 5  # minutes

    class Config:
        # Не используем env_file, так как переменные передаются напрямую из Portainer
        # env_file = "env"  # Отключено, используем только переменные окружения
        env_file_encoding = "utf-8"
        case_sensitive = False
        extra = "allow"  # Allow extra fields from .env
        # Pydantic BaseSettings автоматически читает из переменных окружения
        # которые передаются через docker-compose environment: секцию


settings = Settings()

# Диагностика при загрузке модуля (только если logging настроен)
import logging
logger = logging.getLogger(__name__)
# Логируем только если encryption_key не установлен (чтобы не спамить)
if not settings.encryption_key:
    logger.info(f"🔍 Config загружен (encryption_key не найден):")
    logger.info(f"   - settings.encryption_key: {settings.encryption_key}")
    logger.info(f"   - settings.yandex_maps_api_key: {settings.yandex_maps_api_key[:10] if settings.yandex_maps_api_key else None}...")
    logger.info(f"   - settings.two_gis_api_key: {settings.two_gis_api_key[:10] if settings.two_gis_api_key else None}...")
    logger.info(f"   - settings.telegram_bot_token: {settings.telegram_bot_token[:10] if settings.telegram_bot_token else None}...")
    # Проверяем, что Pydantic видит из переменных окружения
    import os
    logger.info(f"   - os.getenv('ENCRYPTION_KEY'): {os.getenv('ENCRYPTION_KEY')}")
    logger.info(f"   - os.getenv('encryption_key'): {os.getenv('encryption_key')}")
    logger.info(f"   - Проверка всех переменных с 'ENCRYPTION' или 'encryption': {[k for k in os.environ.keys() if 'encryption' in k.lower()]}")
