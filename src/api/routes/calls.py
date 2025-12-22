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
    
    # Получаем все call_status через CallService
    all_calls_dto = call_service.get_call_statuses_by_date(
        current_user.user_id, call_date, db
    )
    
    calls = []
    for call_dto in all_calls_dto:
        calls.append(CallScheduleItem(
            order_number=call_dto.order_number,
            call_time=call_dto.call_time,
            arrival_time=call_dto.arrival_time or call_dto.call_time,
            phone=call_dto.phone,
            customer_name=call_dto.customer_name,
            status=call_dto.status
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
    
    # Получаем статус через CallService
    call_status_dto = call_service.get_call_status_by_id(call_id, db)
    
    if not call_status_dto:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Статус звонка не найден"
        )
    
    # Проверяем принадлежность через DTO
    if call_status_dto.user_id != current_user.user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Доступ запрещен"
        )
    
    return CallStatusResponse(
        id=call_status_dto.id,
        order_number=call_status_dto.order_number,
        call_time=call_status_dto.call_time,
        arrival_time=call_status_dto.arrival_time,
        phone=call_status_dto.phone,
        customer_name=call_status_dto.customer_name,
        status=call_status_dto.status,
        attempts=call_status_dto.attempts,
        is_manual_call=call_status_dto.is_manual_call,
        is_manual_arrival=call_status_dto.is_manual_arrival,
        manual_arrival_time=call_status_dto.manual_arrival_time
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
        user_id=current_user.user_id,
        call_status_id=call_id,
        comment=request.comment,
        session=db
    )
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Статус звонка не найден или доступ запрещен"
        )
    
    # Получаем обновленный статус через CallService
    call_status_dto = call_service.get_call_status_by_id(call_id, db)
    
    if not call_status_dto:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Статус звонка не найден"
        )
    
    return CallStatusResponse(
        id=call_status_dto.id,
        order_number=call_status_dto.order_number,
        call_time=call_status_dto.call_time,
        arrival_time=call_status_dto.arrival_time,
        phone=call_status_dto.phone,
        customer_name=call_status_dto.customer_name,
        status=call_status_dto.status,
        attempts=call_status_dto.attempts,
        is_manual_call=call_status_dto.is_manual_call,
        is_manual_arrival=call_status_dto.is_manual_arrival,
        manual_arrival_time=call_status_dto.manual_arrival_time
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
        user_id=current_user.user_id,
        call_status_id=call_id,
        session=db
    )
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Статус звонка не найден или доступ запрещен"
        )
    
    # Получаем обновленный статус через CallService
    call_status_dto = call_service.get_call_status_by_id(call_id, db)
    
    if not call_status_dto:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Статус звонка не найден"
        )
    
    return CallStatusResponse(
        id=call_status_dto.id,
        order_number=call_status_dto.order_number,
        call_time=call_status_dto.call_time,
        arrival_time=call_status_dto.arrival_time,
        phone=call_status_dto.phone,
        customer_name=call_status_dto.customer_name,
        status=call_status_dto.status,
        attempts=call_status_dto.attempts,
        is_manual_call=call_status_dto.is_manual_call,
        is_manual_arrival=call_status_dto.is_manual_arrival,
        manual_arrival_time=call_status_dto.manual_arrival_time
    )
