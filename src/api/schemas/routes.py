"""
Pydantic схемы для API маршрутов
"""
from datetime import date, datetime
from typing import Optional, List, Tuple
from pydantic import BaseModel, Field


class RoutePointResponse(BaseModel):
    """Схема ответа для точки маршрута"""
    order_number: str
    address: str
    latitude: float
    longitude: float
    estimated_arrival: datetime
    call_time: datetime
    distance_from_previous: float
    time_from_previous: float
    customer_name: Optional[str] = None
    phone: Optional[str] = None
    comment: Optional[str] = None
    delivery_time_window: Optional[str] = None
    status: str = "pending"
    
    class Config:
        from_attributes = True


class RouteResponse(BaseModel):
    """Схема ответа для маршрута"""
    route_date: date
    route_points: List[RoutePointResponse]
    route_order: List[str]
    total_distance: float
    total_time: float
    estimated_completion: datetime


class StartLocationRequest(BaseModel):
    """Схема запроса для точки старта"""
    location_type: str = Field(..., description="Тип: 'geo' или 'address'")
    address: Optional[str] = Field(None, description="Адрес (если location_type='address')")
    latitude: Optional[float] = Field(None, description="Широта (если location_type='geo')")
    longitude: Optional[float] = Field(None, description="Долгота (если location_type='geo')")
    start_time: Optional[datetime] = Field(None, description="Время старта")


class StartLocationResponse(BaseModel):
    """Схема ответа для точки старта"""
    location_type: str
    address: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    start_time: Optional[datetime] = None


class RouteOptimizeRequest(BaseModel):
    """Схема запроса для оптимизации маршрута"""
    order_date: Optional[date] = Field(None, description="Дата заказов (по умолчанию сегодня)")
    start_location: Optional[StartLocationRequest] = Field(None, description="Точка старта (если не установлена)")
    recalculate_without_manual: bool = Field(False, description="Пересчитать без учета ручных времен")


class RouteOptimizeResponse(BaseModel):
    """Схема ответа для оптимизации маршрута"""
    success: bool
    route: Optional[RouteResponse] = None
    message: Optional[str] = None
    error_message: Optional[str] = None

