"""
Pydantic схемы для API импорта
"""
from typing import Optional, List
from pydantic import BaseModel, Field


class ImportCredentialsRequest(BaseModel):
    """Схема запроса для сохранения учетных данных"""
    login: str = Field(..., description="Логин")
    password: str = Field(..., description="Пароль")
    site: str = Field("chefmarket", description="Название сервиса")


class ImportCredentialsResponse(BaseModel):
    """Схема ответа для учетных данных"""
    site: str
    has_credentials: bool = Field(..., description="Есть ли сохраненные учетные данные")


class ImportOrdersRequest(BaseModel):
    """Схема запроса для импорта заказов"""
    order_date: Optional[str] = Field(None, description="Дата заказов (опционально)")


class ImportOrdersResponse(BaseModel):
    """Схема ответа для импорта заказов"""
    success: bool
    imported_count: int = Field(0, description="Количество импортированных заказов")
    updated_count: int = Field(0, description="Количество обновленных заказов")
    errors: List[str] = Field(default_factory=list, description="Список ошибок")
    message: str = Field(..., description="Сообщение о результате")

