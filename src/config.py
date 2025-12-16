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
        env_file = "env"
        env_file_encoding = "utf-8"
        case_sensitive = False
        extra = "allow"  # Allow extra fields from .env
        # Pydantic BaseSettings автоматически читает из переменных окружения
        # даже если они установлены через Portainer или docker-compose


settings = Settings()
