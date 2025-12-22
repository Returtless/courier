"""
Data Transfer Objects для звонков
"""
from datetime import date, datetime
from typing import Optional
from pydantic import BaseModel


class CallStatusDTO(BaseModel):
    """DTO для статуса звонка"""
    id: Optional[int] = None
    order_number: str
    call_time: datetime
    arrival_time: Optional[datetime] = None
    phone: str
    customer_name: Optional[str] = None
    status: str = "pending"  # pending, confirmed, rejected, sent, failed
    attempts: int = 0
    is_manual_call: bool = False
    is_manual_arrival: bool = False
    manual_arrival_time: Optional[datetime] = None
    confirmation_comment: Optional[str] = None
    
    class Config:
        from_attributes = True


class CallNotificationDTO(BaseModel):
    """DTO для уведомления о звонке"""
    call_status_id: int
    user_id: int
    order_number: str
    call_time: datetime
    phone: str
    customer_name: Optional[str] = None
    arrival_time: Optional[datetime] = None
    message: str  # Текст уведомления
    attempts: int = 0


class CreateCallStatusDTO(BaseModel):
    """DTO для создания статуса звонка"""
    order_number: str
    call_time: datetime
    phone: str
    customer_name: Optional[str] = None
    arrival_time: Optional[datetime] = None
    is_manual_call: bool = False
    is_manual_arrival: bool = False
    manual_arrival_time: Optional[datetime] = None

