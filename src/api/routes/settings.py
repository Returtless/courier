"""
REST API endpoints для настроек
(Будет реализовано на этапе 7)
"""
from fastapi import APIRouter

router = APIRouter()


@router.get("")
async def get_settings():
    """Получить настройки (заглушка)"""
    return {"message": "Not implemented yet"}

