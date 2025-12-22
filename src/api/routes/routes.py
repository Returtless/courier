"""
REST API endpoints для маршрутов
"""
import logging
from datetime import date
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from src.database.connection import get_db
from src.application.services.route_service import RouteService
from src.application.services.order_service import OrderService
from src.application.dto.route_dto import (
    RouteDTO, StartLocationDTO, RouteOptimizationRequest, RouteOptimizationResult
)
from src.api.schemas.routes import (
    RouteResponse, RoutePointResponse, StartLocationRequest, StartLocationResponse,
    RouteOptimizeRequest, RouteOptimizeResponse
)
from src.api.auth import get_current_user, User
from src.application.container import get_container

logger = logging.getLogger(__name__)

router = APIRouter()


def _route_dto_to_response(
    route_dto: RouteDTO, 
    route_date: date,
    order_service: OrderService,
    user_id: int,
    db: Session
) -> RouteResponse:
    """Преобразовать RouteDTO в RouteResponse"""
    route_points = []
    
    # Получаем все заказы для получения координат и других данных
    orders_dto = order_service.get_orders_by_date(user_id, route_date, db)
    orders_dict = {o.order_number: o for o in orders_dto}
    
    for point in route_dto.route_points:
        # Получаем полные данные заказа
        order_dto = orders_dict.get(point.order_number)
        
        route_points.append(RoutePointResponse(
            order_number=point.order_number,
            address=point.address,
            latitude=order_dto.latitude if order_dto else None,
            longitude=order_dto.longitude if order_dto else None,
            estimated_arrival=point.estimated_arrival,
            call_time=point.call_time,
            distance_from_previous=point.distance_from_previous or 0.0,
            time_from_previous=point.time_from_previous or 0.0,
            customer_name=point.customer_name,
            phone=point.phone,
            comment=point.comment,
            delivery_time_window=order_dto.delivery_time_window if order_dto else None,
            status=order_dto.status if order_dto else 'pending'
        ))
    
    return RouteResponse(
        route_date=route_date,
        route_points=route_points,
        route_order=route_dto.route_order,
        total_distance=route_dto.total_distance or 0.0,
        total_time=route_dto.total_time or 0.0,
        estimated_completion=route_dto.estimated_completion
    )


@router.post("/optimize", response_model=RouteOptimizeResponse)
async def optimize_route(
    request: RouteOptimizeRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Оптимизировать маршрут для пользователя
    
    - **order_date**: Дата заказов (по умолчанию сегодня)
    - **start_location**: Точка старта (если не установлена ранее)
    - **recalculate_without_manual**: Пересчитать без учета ручных времен
    """
    route_service: RouteService = get_container().route_service()
    
    order_date = request.order_date or date.today()
    
    # Преобразуем StartLocationRequest в StartLocationDTO
    start_location_dto = None
    if request.start_location:
        start_location_dto = StartLocationDTO(
            location_type=request.start_location.location_type,
            address=request.start_location.address,
            latitude=request.start_location.latitude,
            longitude=request.start_location.longitude,
            start_time=request.start_location.start_time
        )
    
    # Создаем RouteOptimizationRequest
    optimization_request = RouteOptimizationRequest(
        start_location=start_location_dto,
        recalculate_without_manual=request.recalculate_without_manual
    )
    
    result: RouteOptimizationResult = route_service.optimize_route(
        user_id=current_user.id,
        order_date=order_date,
        request=optimization_request,
        session=db
    )
    
    if not result.success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=result.error_message
        )
    
    route_response = _route_dto_to_response(
        result.route, order_date, route_service.order_service, current_user.id, db
    )
    
    return RouteOptimizeResponse(
        success=True,
        route=route_response,
        message="Маршрут успешно оптимизирован"
    )


@router.get("", response_model=RouteResponse)
async def get_route(
    order_date: Optional[date] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Получить сохраненный маршрут пользователя
    
    - **order_date**: Дата маршрута (по умолчанию сегодня)
    """
    route_service: RouteService = get_container().route_service()
    
    if order_date is None:
        order_date = date.today()
    
    route_dto: Optional[RouteDTO] = route_service.get_route(
        user_id=current_user.id,
        order_date=order_date,
        session=db
    )
    
    if not route_dto:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Маршрут не найден. Сначала оптимизируйте маршрут."
        )
    
    return _route_dto_to_response(
        route_dto, order_date, route_service.order_service, current_user.id, db
    )


@router.get("/current-order", response_model=RoutePointResponse)
async def get_current_order(
    order_date: Optional[date] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Получить первый (текущий) заказ в маршруте
    
    - **order_date**: Дата маршрута (по умолчанию сегодня)
    """
    route_service: RouteService = get_container().route_service()
    
    if order_date is None:
        order_date = date.today()
    
    route_dto: Optional[RouteDTO] = route_service.get_route(
        user_id=current_user.id,
        order_date=order_date,
        session=db
    )
    
    if not route_dto or not route_dto.route_points:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Маршрут не найден или пуст"
        )
    
    # Возвращаем первый заказ в маршруте
    current_point = route_dto.route_points[0]
    
    # Получаем полные данные заказа для координат
    order_dto = route_service.order_service.get_order_by_number(
        current_user.id, current_point.order_number, order_date, db
    )
    
    return RoutePointResponse(
        order_number=current_point.order_number,
        address=current_point.address,
        latitude=order_dto.latitude if order_dto else None,
        longitude=order_dto.longitude if order_dto else None,
        estimated_arrival=current_point.estimated_arrival,
        call_time=current_point.call_time,
        distance_from_previous=current_point.distance_from_previous or 0.0,
        time_from_previous=current_point.time_from_previous or 0.0,
        customer_name=current_point.customer_name,
        phone=current_point.phone,
        comment=current_point.comment,
        delivery_time_window=order_dto.delivery_time_window if order_dto else None,
        status=order_dto.status if order_dto else 'pending'
    )


@router.get("/start-location", response_model=StartLocationResponse)
async def get_start_location(
    order_date: Optional[date] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Получить точку старта маршрута
    
    - **order_date**: Дата (по умолчанию сегодня)
    """
    route_service: RouteService = get_container().route_service()
    
    if order_date is None:
        order_date = date.today()
    
    start_location: Optional[StartLocationDTO] = route_service.get_start_location(
        user_id=current_user.id,
        order_date=order_date,
        session=db
    )
    
    if not start_location:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Точка старта не установлена"
        )
    
    return StartLocationResponse(
        location_type=start_location.location_type,
        address=start_location.address,
        latitude=start_location.latitude,
        longitude=start_location.longitude,
        start_time=start_location.start_time
    )


@router.put("/start-location", response_model=StartLocationResponse)
async def set_start_location(
    location: StartLocationRequest,
    order_date: Optional[date] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Установить точку старта маршрута
    
    - **location_type**: Тип точки ('geo' или 'address')
    - **address**: Адрес (если location_type='address')
    - **latitude/longitude**: Координаты (если location_type='geo')
    - **start_time**: Время старта
    """
    route_service: RouteService = get_container().route_service()
    
    if order_date is None:
        order_date = date.today()
    
    location_dto = StartLocationDTO(
        location_type=location.location_type,
        address=location.address,
        latitude=location.latitude,
        longitude=location.longitude,
        start_time=location.start_time
    )
    
    saved_location = route_service.save_start_location(
        user_id=current_user.id,
        location_data=location_dto,
        order_date=order_date,
        session=db
    )
    
    return StartLocationResponse(
        location_type=saved_location.location_type,
        address=saved_location.address,
        latitude=saved_location.latitude,
        longitude=saved_location.longitude,
        start_time=saved_location.start_time
    )
