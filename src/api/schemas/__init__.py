"""
Pydantic схемы для API
"""
from .orders import (
    OrderResponse, OrderCreate, OrderUpdate, OrderListResponse
)
from .routes import (
    RouteResponse, RoutePointResponse, StartLocationRequest,
    StartLocationResponse, RouteOptimizeRequest, RouteOptimizeResponse
)
from .calls import (
    CallStatusResponse, CallScheduleResponse, CallScheduleItem,
    CallConfirmRequest, CallRejectRequest
)

__all__ = [
    # Orders
    'OrderResponse',
    'OrderCreate',
    'OrderUpdate',
    'OrderListResponse',
    # Routes
    'RouteResponse',
    'RoutePointResponse',
    'StartLocationRequest',
    'StartLocationResponse',
    'RouteOptimizeRequest',
    'RouteOptimizeResponse',
    # Calls
    'CallStatusResponse',
    'CallScheduleResponse',
    'CallScheduleItem',
    'CallConfirmRequest',
    'CallRejectRequest',
]
