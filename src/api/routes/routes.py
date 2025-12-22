"""
REST API endpoints для маршрутов
(Будет реализовано на этапе 7)
"""
from fastapi import APIRouter

router = APIRouter()


@router.get("")
async def get_route():
    """Получить маршрут (заглушка)"""
    return {"message": "Not implemented yet"}

