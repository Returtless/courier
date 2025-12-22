"""
Аутентификация для REST API
Использует Telegram user_id как простой токен
"""
import logging
from typing import Optional
from fastapi import HTTPException, Security, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import Optional
from pydantic import BaseModel

logger = logging.getLogger(__name__)

# Схема безопасности
security = HTTPBearer()


class User(BaseModel):
    """Модель пользователя"""
    user_id: int


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Security(security)
) -> User:
    """
    Получить текущего пользователя из токена
    
    Args:
        credentials: HTTP Bearer токен
        
    Returns:
        Объект пользователя
        
    Raises:
        HTTPException: Если токен невалиден
    """
    token = credentials.credentials
    
    try:
        # Простая аутентификация: токен = user_id
        # В будущем можно заменить на JWT
        user_id = int(token)
        
        if user_id <= 0:
            raise ValueError("Invalid user_id")
        
        return User(user_id=user_id)
    
    except (ValueError, TypeError) as e:
        logger.warning(f"Invalid token format: {token}")
        raise HTTPException(
            status_code=401,
            detail="Invalid authentication token",
            headers={"WWW-Authenticate": "Bearer"},
        )


def get_optional_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(lambda: None)
) -> Optional[User]:
    """
    Получить пользователя из токена (опционально)
    
    Args:
        credentials: HTTP Bearer токен (опционально)
        
    Returns:
        Объект пользователя или None
    """
    if credentials is None:
        return None
    
    try:
        token = credentials.credentials
        user_id = int(token)
        
        if user_id <= 0:
            return None
        
        return User(user_id=user_id)
    
    except (ValueError, TypeError):
        return None

