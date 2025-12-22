"""
REST API endpoints для настроек пользователя
"""
import logging
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from src.database.connection import get_db
from src.services.user_settings_service import UserSettingsService
from src.api.schemas.settings import UserSettingsResponse, UserSettingsUpdate
from src.api.auth import get_current_user, User

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("", response_model=UserSettingsResponse)
async def get_settings(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Получить настройки пользователя
    """
    settings_service = UserSettingsService()
    settings = settings_service.get_settings(current_user.id)
    
    return UserSettingsResponse(
        user_id=settings.user_id,
        call_advance_minutes=settings.call_advance_minutes,
        call_retry_interval_minutes=settings.call_retry_interval_minutes,
        call_max_attempts=settings.call_max_attempts,
        service_time_minutes=settings.service_time_minutes,
        parking_time_minutes=settings.parking_time_minutes,
        traffic_check_interval_minutes=settings.traffic_check_interval_minutes,
        traffic_threshold_percent=settings.traffic_threshold_percent
    )


@router.put("", response_model=UserSettingsResponse)
async def update_settings(
    settings_update: UserSettingsUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Обновить настройки пользователя
    
    Можно обновить любое подмножество настроек
    """
    settings_service = UserSettingsService()
    
    # Подготавливаем словарь для обновления (только не-None значения)
    update_dict = {}
    for key, value in settings_update.model_dump(exclude_unset=True).items():
        if value is not None:
            update_dict[key] = value
    
    if not update_dict:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Не указаны настройки для обновления"
        )
    
    # Обновляем настройки
    success = settings_service.update_settings(current_user.id, **update_dict)
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Ошибка обновления настроек"
        )
    
    # Получаем обновленные настройки
    settings = settings_service.get_settings(current_user.id)
    
    return UserSettingsResponse(
        user_id=settings.user_id,
        call_advance_minutes=settings.call_advance_minutes,
        call_retry_interval_minutes=settings.call_retry_interval_minutes,
        call_max_attempts=settings.call_max_attempts,
        service_time_minutes=settings.service_time_minutes,
        parking_time_minutes=settings.parking_time_minutes,
        traffic_check_interval_minutes=settings.traffic_check_interval_minutes,
        traffic_threshold_percent=settings.traffic_threshold_percent
    )


@router.post("/reset", response_model=UserSettingsResponse)
async def reset_settings(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Сбросить настройки пользователя к значениям по умолчанию
    """
    settings_service = UserSettingsService()
    
    success = settings_service.reset_settings(current_user.id)
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Ошибка сброса настроек"
        )
    
    # Получаем сброшенные настройки
    settings = settings_service.get_settings(current_user.id)
    
    return UserSettingsResponse(
        user_id=settings.user_id,
        call_advance_minutes=settings.call_advance_minutes,
        call_retry_interval_minutes=settings.call_retry_interval_minutes,
        call_max_attempts=settings.call_max_attempts,
        service_time_minutes=settings.service_time_minutes,
        parking_time_minutes=settings.parking_time_minutes,
        traffic_check_interval_minutes=settings.traffic_check_interval_minutes,
        traffic_threshold_percent=settings.traffic_threshold_percent
    )
