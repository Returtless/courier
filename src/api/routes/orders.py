"""
REST API endpoints для заказов
"""
import logging
from datetime import date
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from src.api.auth import get_current_user, User
from src.api.schemas.orders import (
    OrderResponse, OrderCreate, OrderUpdate, OrderListResponse
)
from src.application.container import get_container
from src.application.services.order_service import OrderService
from src.application.dto.order_dto import CreateOrderDTO, UpdateOrderDTO
from src.database.connection import get_db

logger = logging.getLogger(__name__)

router = APIRouter()


def get_order_service() -> OrderService:
    """Получить OrderService из DI контейнера"""
    container = get_container()
    return container.order_service()


@router.get("", response_model=OrderListResponse)
async def get_orders(
    order_date: Optional[date] = Query(None, description="Дата заказов (по умолчанию сегодня)"),
    status: Optional[str] = Query(None, description="Фильтр по статусу"),
    current_user: User = Depends(get_current_user),
    order_service: OrderService = Depends(get_order_service),
    db: Session = Depends(get_db)
):
    """
    Получить список заказов пользователя
    
    Args:
        order_date: Дата заказов
        status: Фильтр по статусу (pending, delivered)
        current_user: Текущий пользователь
        order_service: Сервис заказов
        db: Сессия БД
        
    Returns:
        Список заказов
    """
    if order_date is None:
        order_date = date.today()
    
    try:
        orders_dto = order_service.get_orders_by_date(
            current_user.user_id, order_date, db
        )
        
        # Фильтруем по статусу если указан
        if status:
            orders_dto = [o for o in orders_dto if o.status == status]
        
        # Преобразуем DTO в Response
        orders = []
        for order_dto in orders_dto:
            order_dict = order_dto.model_dump()
            # Преобразуем time в строку
            if order_dto.delivery_time_start:
                order_dict['delivery_time_start'] = order_dto.delivery_time_start.strftime('%H:%M')
            if order_dto.delivery_time_end:
                order_dict['delivery_time_end'] = order_dto.delivery_time_end.strftime('%H:%M')
            orders.append(OrderResponse(**order_dict))
        
        return OrderListResponse(
            orders=orders,
            total=len(orders),
            date=order_date
        )
    
    except Exception as e:
        logger.error(f"Ошибка получения заказов: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{order_number}", response_model=OrderResponse)
async def get_order(
    order_number: str,
    order_date: Optional[date] = Query(None, description="Дата заказа (по умолчанию сегодня)"),
    current_user: User = Depends(get_current_user),
    order_service: OrderService = Depends(get_order_service),
    db: Session = Depends(get_db)
):
    """
    Получить заказ по номеру
    
    Args:
        order_number: Номер заказа
        order_date: Дата заказа
        current_user: Текущий пользователь
        order_service: Сервис заказов
        db: Сессия БД
        
    Returns:
        Заказ
    """
    if order_date is None:
        order_date = date.today()
    
    try:
        order_dto = order_service.get_order_by_number(
            current_user.user_id, order_number, order_date, db
        )
        
        if not order_dto:
            raise HTTPException(status_code=404, detail="Заказ не найден")
        
        order_dict = order_dto.model_dump()
        # Преобразуем time в строку
        if order_dto.delivery_time_start:
            order_dict['delivery_time_start'] = order_dto.delivery_time_start.strftime('%H:%M')
        if order_dto.delivery_time_end:
            order_dict['delivery_time_end'] = order_dto.delivery_time_end.strftime('%H:%M')
        
        return OrderResponse(**order_dict)
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Ошибка получения заказа: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("", response_model=OrderResponse, status_code=201)
async def create_order(
    order_data: OrderCreate,
    current_user: User = Depends(get_current_user),
    order_service: OrderService = Depends(get_order_service),
    db: Session = Depends(get_db)
):
    """
    Создать новый заказ
    
    Args:
        order_data: Данные заказа
        current_user: Текущий пользователь
        order_service: Сервис заказов
        db: Сессия БД
        
    Returns:
        Созданный заказ
    """
    try:
        create_dto = CreateOrderDTO(
            order_number=order_data.order_number,
            customer_name=order_data.customer_name,
            phone=order_data.phone,
            address=order_data.address,
            comment=order_data.comment,
            delivery_time_window=order_data.delivery_time_window,
            entrance_number=order_data.entrance_number,
            apartment_number=order_data.apartment_number
        )
        
        order_dto = order_service.create_order(
            current_user.user_id, create_dto, order_data.order_date, db
        )
        
        order_dict = order_dto.model_dump()
        # Преобразуем time в строку
        if order_dto.delivery_time_start:
            order_dict['delivery_time_start'] = order_dto.delivery_time_start.strftime('%H:%M')
        if order_dto.delivery_time_end:
            order_dict['delivery_time_end'] = order_dto.delivery_time_end.strftime('%H:%M')
        
        return OrderResponse(**order_dict)
    
    except Exception as e:
        logger.error(f"Ошибка создания заказа: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/{order_number}", response_model=OrderResponse)
async def update_order(
    order_number: str,
    order_data: OrderUpdate,
    order_date: Optional[date] = Query(None, description="Дата заказа (по умолчанию сегодня)"),
    current_user: User = Depends(get_current_user),
    order_service: OrderService = Depends(get_order_service),
    db: Session = Depends(get_db)
):
    """
    Обновить заказ
    
    Args:
        order_number: Номер заказа
        order_data: Данные для обновления
        order_date: Дата заказа
        current_user: Текущий пользователь
        order_service: Сервис заказов
        db: Сессия БД
        
    Returns:
        Обновленный заказ
    """
    if order_date is None:
        order_date = date.today()
    
    try:
        # Проверяем существование заказа
        existing_order = order_service.get_order_by_number(
            current_user.user_id, order_number, order_date, db
        )
        
        if not existing_order:
            raise HTTPException(status_code=404, detail="Заказ не найден")
        
        update_dto = UpdateOrderDTO(**order_data.model_dump(exclude_unset=True))
        order_dto = order_service.update_order(
            current_user.user_id, order_number, update_dto, order_date, db
        )
        
        order_dict = order_dto.model_dump()
        # Преобразуем time в строку
        if order_dto.delivery_time_start:
            order_dict['delivery_time_start'] = order_dto.delivery_time_start.strftime('%H:%M')
        if order_dto.delivery_time_end:
            order_dict['delivery_time_end'] = order_dto.delivery_time_end.strftime('%H:%M')
        
        return OrderResponse(**order_dict)
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Ошибка обновления заказа: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{order_number}/delivered", response_model=OrderResponse)
async def mark_order_delivered(
    order_number: str,
    order_date: Optional[date] = Query(None, description="Дата заказа (по умолчанию сегодня)"),
    current_user: User = Depends(get_current_user),
    order_service: OrderService = Depends(get_order_service),
    db: Session = Depends(get_db)
):
    """
    Отметить заказ как доставленный
    
    Args:
        order_number: Номер заказа
        order_date: Дата заказа
        current_user: Текущий пользователь
        order_service: Сервис заказов
        db: Сессия БД
        
    Returns:
        Обновленный заказ
    """
    if order_date is None:
        order_date = date.today()
    
    try:
        order_dto = order_service.mark_delivered(
            current_user.user_id, order_number, order_date, db
        )
        
        if not order_dto:
            raise HTTPException(status_code=404, detail="Заказ не найден")
        
        order_dict = order_dto.model_dump()
        # Преобразуем time в строку
        if order_dto.delivery_time_start:
            order_dict['delivery_time_start'] = order_dto.delivery_time_start.strftime('%H:%M')
        if order_dto.delivery_time_end:
            order_dict['delivery_time_end'] = order_dto.delivery_time_end.strftime('%H:%M')
        
        return OrderResponse(**order_dict)
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Ошибка отметки заказа как доставленного: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

