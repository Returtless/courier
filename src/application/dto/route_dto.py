"""
Data Transfer Objects для маршрутов
"""
from datetime import date, datetime
from typing import Optional, List, Dict
from pydantic import BaseModel


class StartLocationDTO(BaseModel):
    """DTO для точки старта"""
    location_type: str  # "geo" or "address"
    address: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    start_time: Optional[datetime] = None
    
    class Config:
        from_attributes = True


class RoutePointDTO(BaseModel):
    """DTO для точки маршрута"""
    order_number: str
    address: str
    estimated_arrival: Optional[datetime] = None
    call_time: Optional[datetime] = None
    distance_from_previous: Optional[float] = None
    time_from_previous: Optional[float] = None
    customer_name: Optional[str] = None
    phone: Optional[str] = None
    comment: Optional[str] = None


class RouteDTO(BaseModel):
    """DTO для маршрута"""
    route_points: List[RoutePointDTO] = []
    route_order: List[str] = []  # Порядок номеров заказов
    total_distance: Optional[float] = None
    total_time: Optional[float] = None
    estimated_completion: Optional[datetime] = None
    call_schedule: List[Dict] = []  # График звонков


class RouteOptimizationRequest(BaseModel):
    """DTO для запроса оптимизации маршрута"""
    start_location: Optional[StartLocationDTO] = None
    start_time: Optional[datetime] = None
    recalculate_without_manual: bool = False  # Пересчитать без учета ручных времен


class RouteOptimizationResult(BaseModel):
    """DTO для результата оптимизации маршрута"""
    success: bool
    route: Optional[RouteDTO] = None
    error_message: Optional[str] = None
    warnings: List[str] = []

