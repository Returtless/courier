import os
from typing import Optional
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Telegram
    telegram_bot_token: str = "your_bot_token_here"

    # Maps API
    yandex_maps_api_key: Optional[str] = None
    google_maps_api_key: Optional[str] = None

    # Database
    database_url: str = "sqlite:///./courier_bot.db"

    # LLM
    llm_model_path: str = "models/gemma3-4b"
    llm_device: str = "cpu"
    llm_max_tokens: int = 512

    # Route optimization
    delivery_time_per_stop: int = 10  # minutes
    parking_walking_time: int = 7  # minutes
    call_advance_time: int = 40  # minutes before delivery
    traffic_check_interval: int = 5  # minutes

    class Config:
        env_file = "env"
        case_sensitive = False


settings = Settings()
