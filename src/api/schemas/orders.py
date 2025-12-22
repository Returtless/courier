"""
Pydantic схемы для API заказов
"""
from datetime import date, datetime, time
from typing import Optional, List
from pydantic import BaseModel, Field


class OrderResponse(BaseModel):
    """Схема ответа для заказа"""
    id: Optional[int] = None
    order_number: Optional[str] = None
    customer_name: Optional[str] = None
    phone: Optional[str] = None
    address: str
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    comment: Optional[str] = None
    delivery_time_start: Optional[str] = None  # Формат "HH:MM"
    delivery_time_end: Optional[str] = None  # Формат "HH:MM"
    delivery_time_window: Optional[str] = None
    status: str = "pending"
    entrance_number: Optional[str] = None
    apartment_number: Optional[str] = None
    order_date: date
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True


class OrderCreate(BaseModel):
    """Схема для создания заказа"""
    order_number: str = Field(..., description="Номер заказа")
    customer_name: Optional[str] = Field(None, description="Имя клиента")
    phone: Optional[str] = Field(None, description="Телефон клиента")
    address: str = Field(..., description="Адрес доставки")
    comment: Optional[str] = Field(None, description="Комментарий к заказу")
    delivery_time_window: Optional[str] = Field(None, description="Окно доставки (например, '09:00 - 12:00')")
    entrance_number: Optional[str] = Field(None, description="Номер подъезда")
    apartment_number: Optional[str] = Field(None, description="Номер квартиры")
    order_date: Optional[date] = Field(None, description="Дата заказа (по умолчанию сегодня)")


class OrderUpdate(BaseModel):
    """Схема для обновления заказа"""
    customer_name: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    comment: Optional[str] = None
    delivery_time_window: Optional[str] = None
    entrance_number: Optional[str] = None
    apartment_number: Optional[str] = None
    status: Optional[str] = None


class OrderListResponse(BaseModel):
    """Схема ответа для списка заказов"""
    orders: List[OrderResponse]
    total: int
    date: date

