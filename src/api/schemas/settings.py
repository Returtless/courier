"""
Pydantic схемы для API настроек
"""
from pydantic import BaseModel, Field


class UserSettingsResponse(BaseModel):
    """Схема ответа для настроек пользователя"""
    user_id: int
    call_advance_minutes: int = Field(10, description="Время звонка до приезда (минут)")
    call_retry_interval_minutes: int = Field(2, description="Интервал между повторными звонками (минут)")
    call_max_attempts: int = Field(3, description="Максимальное количество попыток дозвона")
    service_time_minutes: int = Field(10, description="Время нахождения на точке (минут)")
    parking_time_minutes: int = Field(7, description="Время на парковку и подход (минут)")
    traffic_check_interval_minutes: int = Field(5, description="Интервал проверки пробок (минут)")
    traffic_threshold_percent: int = Field(50, description="Порог уведомления о пробках (%)")
    
    class Config:
        from_attributes = True


class UserSettingsUpdate(BaseModel):
    """Схема запроса для обновления настроек"""
    call_advance_minutes: int = Field(None, description="Время звонка до приезда (минут)")
    call_retry_interval_minutes: int = Field(None, description="Интервал между повторными звонками (минут)")
    call_max_attempts: int = Field(None, description="Максимальное количество попыток дозвона")
    service_time_minutes: int = Field(None, description="Время нахождения на точке (минут)")
    parking_time_minutes: int = Field(None, description="Время на парковку и подход (минут)")
    traffic_check_interval_minutes: int = Field(None, description="Интервал проверки пробок (минут)")
    traffic_threshold_percent: int = Field(None, description="Порог уведомления о пробках (%)")

