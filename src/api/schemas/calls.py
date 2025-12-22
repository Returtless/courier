"""
Pydantic схемы для API звонков
"""
from datetime import date, datetime
from typing import Optional, List
from pydantic import BaseModel, Field


class CallStatusResponse(BaseModel):
    """Схема ответа для статуса звонка"""
    id: int
    order_number: str
    call_time: datetime
    arrival_time: Optional[datetime] = None
    phone: str
    customer_name: Optional[str] = None
    status: str
    attempts: int
    is_manual_call: bool = False
    is_manual_arrival: bool = False
    manual_arrival_time: Optional[datetime] = None
    
    class Config:
        from_attributes = True


class CallScheduleItem(BaseModel):
    """Элемент графика звонков"""
    order_number: str
    call_time: datetime
    arrival_time: datetime
    phone: str
    customer_name: Optional[str] = None
    status: str = "pending"


class CallScheduleResponse(BaseModel):
    """Схема ответа для графика звонков"""
    call_date: date
    calls: List[CallScheduleItem]
    total: int


class CallConfirmRequest(BaseModel):
    """Схема запроса для подтверждения звонка"""
    comment: Optional[str] = Field(None, description="Комментарий к подтверждению")


class CallRejectRequest(BaseModel):
    """Схема запроса для отклонения звонка"""
    reason: Optional[str] = Field(None, description="Причина отклонения")

