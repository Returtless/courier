"""
REST API endpoints для звонков
(Будет реализовано на этапе 7)
"""
from fastapi import APIRouter

router = APIRouter()


@router.get("")
async def get_calls():
    """Получить график звонков (заглушка)"""
    return {"message": "Not implemented yet"}

