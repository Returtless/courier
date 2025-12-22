"""
REST API endpoints для звонков
"""
import logging
from datetime import date
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from src.database.connection import get_db
from src.application.services.call_service import CallService
from src.application.dto.call_dto import CallStatusDTO
from src.api.schemas.calls import (
    CallStatusResponse, CallScheduleResponse, CallScheduleItem,
    CallConfirmRequest, CallRejectRequest
)
from src.api.auth import get_current_user, User
from src.application.container import get_container

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("", response_model=CallScheduleResponse)
async def get_call_schedule(
    call_date: Optional[date] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Получить график звонков для пользователя
    
    - **call_date**: Дата звонков (по умолчанию сегодня)
    """
    call_service: CallService = get_container().call_service()
    
    if call_date is None:
        call_date = date.today()
    
    # Получаем все call_status для пользователя за дату
    from src.repositories.call_status_repository import CallStatusRepository
    call_status_repo: CallStatusRepository = get_container().call_status_repository()
    
    # Получаем все звонки через репозиторий
    all_calls = call_status_repo.get_by_user_and_date(
        current_user.id, call_date, db
    )
    
    calls = []
    for call_db in all_calls:
        calls.append(CallScheduleItem(
            order_number=call_db.order_number,
            call_time=call_db.call_time,
            arrival_time=call_db.arrival_time or call_db.call_time,
            phone=call_db.phone,
            customer_name=call_db.customer_name,
            status=call_db.status
        ))
    
    # Сортируем по времени звонка
    calls.sort(key=lambda x: x.call_time)
    
    return CallScheduleResponse(
        call_date=call_date,
        calls=calls,
        total=len(calls)
    )


@router.get("/{call_id}", response_model=CallStatusResponse)
async def get_call_status(
    call_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Получить статус звонка по ID
    
    - **call_id**: ID статуса звонка
    """
    call_service: CallService = get_container().call_service()
    
    from src.repositories.call_status_repository import CallStatusRepository
    call_status_repo: CallStatusRepository = get_container().call_status_repository()
    
    call_status_db = call_status_repo.get_by_id(call_id, db)
    
    if not call_status_db:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Статус звонка не найден"
        )
    
    if call_status_db.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Доступ запрещен"
        )
    
    return CallStatusResponse(
        id=call_status_db.id,
        order_number=call_status_db.order_number,
        call_time=call_status_db.call_time,
        arrival_time=call_status_db.arrival_time,
        phone=call_status_db.phone,
        customer_name=call_status_db.customer_name,
        status=call_status_db.status,
        attempts=call_status_db.attempts,
        is_manual_call=call_status_db.is_manual_call,
        is_manual_arrival=call_status_db.is_manual_arrival,
        manual_arrival_time=call_status_db.manual_arrival_time
    )


@router.post("/{call_id}/confirm", response_model=CallStatusResponse)
async def confirm_call(
    call_id: int,
    request: CallConfirmRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Подтвердить звонок
    
    - **call_id**: ID статуса звонка
    - **comment**: Комментарий к подтверждению (опционально)
    """
    call_service: CallService = get_container().call_service()
    
    success = call_service.confirm_call(
        user_id=current_user.id,
        call_status_id=call_id,
        comment=request.comment,
        session=db
    )
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Статус звонка не найден или доступ запрещен"
        )
    
    # Получаем обновленный статус
    from src.repositories.call_status_repository import CallStatusRepository
    call_status_repo: CallStatusRepository = get_container().call_status_repository()
    call_status_db = call_status_repo.get_by_id(call_id, db)
    
    return CallStatusResponse(
        id=call_status_db.id,
        order_number=call_status_db.order_number,
        call_time=call_status_db.call_time,
        arrival_time=call_status_db.arrival_time,
        phone=call_status_db.phone,
        customer_name=call_status_db.customer_name,
        status=call_status_db.status,
        attempts=call_status_db.attempts,
        is_manual_call=call_status_db.is_manual_call,
        is_manual_arrival=call_status_db.is_manual_arrival,
        manual_arrival_time=call_status_db.manual_arrival_time
    )


@router.post("/{call_id}/reject", response_model=CallStatusResponse)
async def reject_call(
    call_id: int,
    request: CallRejectRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Отклонить звонок (повторная попытка)
    
    - **call_id**: ID статуса звонка
    - **reason**: Причина отклонения (опционально)
    """
    call_service: CallService = get_container().call_service()
    
    success = call_service.reject_call(
        user_id=current_user.id,
        call_status_id=call_id,
        session=db
    )
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Статус звонка не найден или доступ запрещен"
        )
    
    # Получаем обновленный статус
    from src.repositories.call_status_repository import CallStatusRepository
    call_status_repo: CallStatusRepository = get_container().call_status_repository()
    call_status_db = call_status_repo.get_by_id(call_id, db)
    
    return CallStatusResponse(
        id=call_status_db.id,
        order_number=call_status_db.order_number,
        call_time=call_status_db.call_time,
        arrival_time=call_status_db.arrival_time,
        phone=call_status_db.phone,
        customer_name=call_status_db.customer_name,
        status=call_status_db.status,
        attempts=call_status_db.attempts,
        is_manual_call=call_status_db.is_manual_call,
        is_manual_arrival=call_status_db.is_manual_arrival,
        manual_arrival_time=call_status_db.manual_arrival_time
    )
