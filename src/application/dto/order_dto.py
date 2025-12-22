"""
Data Transfer Objects для заказов
"""
from datetime import date, time, datetime
from typing import Optional
from pydantic import BaseModel, Field


class OrderDTO(BaseModel):
    """DTO для представления заказа"""
    id: Optional[int] = None
    order_number: Optional[str] = None
    customer_name: Optional[str] = None
    phone: Optional[str] = None
    address: str
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    comment: Optional[str] = None
    delivery_time_start: Optional[time] = None
    delivery_time_end: Optional[time] = None
    delivery_time_window: Optional[str] = None
    status: str = "pending"
    entrance_number: Optional[str] = None
    apartment_number: Optional[str] = None
    gis_id: Optional[str] = None
    manual_arrival_time: Optional[datetime] = None
    
    class Config:
        from_attributes = True


class CreateOrderDTO(BaseModel):
    """DTO для создания заказа"""
    order_number: Optional[str] = None
    customer_name: Optional[str] = None
    phone: Optional[str] = None
    address: str = Field(..., min_length=1)
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    comment: Optional[str] = None
    delivery_time_start: Optional[time] = None
    delivery_time_end: Optional[time] = None
    delivery_time_window: Optional[str] = None
    entrance_number: Optional[str] = None
    apartment_number: Optional[str] = None
    gis_id: Optional[str] = None


class UpdateOrderDTO(BaseModel):
    """DTO для обновления заказа"""
    customer_name: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    comment: Optional[str] = None
    delivery_time_start: Optional[time] = None
    delivery_time_end: Optional[time] = None
    delivery_time_window: Optional[str] = None
    entrance_number: Optional[str] = None
    apartment_number: Optional[str] = None
    gis_id: Optional[str] = None

