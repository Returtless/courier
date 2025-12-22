"""
REST API endpoints для импорта заказов
"""
import logging
import asyncio
from datetime import date
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from src.database.connection import get_db
from src.services.chefmarket_parser import ChefMarketParser
from src.services.credentials_service import CredentialsService
from src.application.services.order_service import OrderService
from src.application.dto.order_dto import CreateOrderDTO
from src.api.schemas.import_schemas import (
    ImportCredentialsRequest, ImportCredentialsResponse,
    ImportOrdersRequest, ImportOrdersResponse
)
from src.api.auth import get_current_user, User
from src.application.container import get_container

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/credentials", response_model=ImportCredentialsResponse)
async def get_credentials(
    site: str = "chefmarket",
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Проверить наличие сохраненных учетных данных
    
    - **site**: Название сервиса (по умолчанию "chefmarket")
    """
    credentials_service = CredentialsService()
    has_credentials = credentials_service.has_credentials(current_user.id, site)
    
    return ImportCredentialsResponse(
        site=site,
        has_credentials=has_credentials
    )


@router.post("/credentials", response_model=ImportCredentialsResponse)
async def save_credentials(
    request: ImportCredentialsRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Сохранить учетные данные для импорта
    
    - **login**: Логин
    - **password**: Пароль
    - **site**: Название сервиса (по умолчанию "chefmarket")
    """
    credentials_service = CredentialsService()
    
    success = credentials_service.save_credentials(
        user_id=current_user.id,
        login=request.login,
        password=request.password,
        site=request.site
    )
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Ошибка сохранения учетных данных"
        )
    
    return ImportCredentialsResponse(
        site=request.site,
        has_credentials=True
    )


@router.delete("/credentials", status_code=status.HTTP_204_NO_CONTENT)
async def delete_credentials(
    site: str = "chefmarket",
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Удалить сохраненные учетные данные
    
    - **site**: Название сервиса (по умолчанию "chefmarket")
    """
    credentials_service = CredentialsService()
    
    success = credentials_service.delete_credentials(current_user.id, site)
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Учетные данные не найдены"
        )
    
    return None


@router.post("/chefmarket", response_model=ImportOrdersResponse)
async def import_orders_from_chefmarket(
    request: Optional[ImportOrdersRequest] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Импортировать заказы из ШефМаркет
    
    - **order_date**: Дата заказов (опционально, по умолчанию сегодня)
    """
    credentials_service = CredentialsService()
    order_service: OrderService = get_container().order_service()
    parser = ChefMarketParser()
    
    # Проверяем наличие учетных данных
    if not credentials_service.has_credentials(current_user.id, "chefmarket"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Учетные данные не найдены. Сначала сохраните логин и пароль."
        )
    
    # Получаем учетные данные
    credentials = credentials_service.get_credentials(current_user.id, "chefmarket")
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Ошибка получения учетных данных"
        )
    
    login, password = credentials
    
    # Определяем дату заказов
    if request and request.order_date:
        try:
            target_date = date.fromisoformat(request.order_date)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Неверный формат даты. Используйте формат YYYY-MM-DD"
            )
    else:
        target_date = date.today()
    
    # Запускаем импорт
    try:
        # Импорт асинхронный, но FastAPI endpoint синхронный
        # Используем asyncio.run для запуска async функции
        orders = asyncio.run(parser.import_orders(login, password, target_date))
        
        if not orders:
            # Если заказов нет, но был сделан скриншот - можно вернуть информацию об этом
            return ImportOrdersResponse(
                success=True,
                imported_count=0,
                updated_count=0,
                message="Заказы не найдены на указанную дату"
            )
        
        # Сохраняем заказы в БД
        imported_count = 0
        updated_count = 0
        errors = []
        
        for order_data in orders:
            try:
                # Проверяем, существует ли заказ
                existing_order = order_service.get_order_by_number(
                    current_user.id,
                    order_data.get('order_number'),
                    target_date,
                    db
                )
                
                # Преобразуем delivery_time_window в delivery_time_start и delivery_time_end, если нужно
                if order_data.get('delivery_time_window') and not order_data.get('delivery_time_start'):
                    time_window = order_data.get('delivery_time_window')
                    if isinstance(time_window, str) and '-' in time_window:
                        try:
                            from datetime import datetime
                            start_str, end_str = time_window.split('-', 1)
                            start_str = start_str.strip()
                            end_str = end_str.strip()
                            order_data['delivery_time_start'] = datetime.strptime(start_str, '%H:%M').time()
                            order_data['delivery_time_end'] = datetime.strptime(end_str, '%H:%M').time()
                        except Exception as e:
                            logger.warning(f"⚠️ Не удалось распарсить временное окно '{time_window}': {e}")
                
                # Создаем DTO
                create_dto = CreateOrderDTO(
                    customer_name=order_data.get('customer_name'),
                    phone=order_data.get('phone'),
                    address=order_data.get('address', ''),
                    comment=order_data.get('comment'),
                    delivery_time_window=order_data.get('delivery_time_window'),
                    order_number=order_data.get('order_number', ''),
                    entrance_number=order_data.get('entrance_number'),
                    apartment_number=order_data.get('apartment_number')
                )
                
                if existing_order:
                    # Обновляем существующий заказ
                    from src.application.dto.order_dto import UpdateOrderDTO
                    update_dto = UpdateOrderDTO(
                        customer_name=create_dto.customer_name,
                        phone=create_dto.phone,
                        address=create_dto.address,
                        comment=create_dto.comment,
                        delivery_time_window=create_dto.delivery_time_window,
                        entrance_number=create_dto.entrance_number,
                        apartment_number=create_dto.apartment_number
                    )
                    order_service.update_order(
                        current_user.id,
                        create_dto.order_number,
                        update_dto,
                        target_date,
                        db
                    )
                    updated_count += 1
                else:
                    # Создаем новый заказ
                    order_service.create_order(
                        current_user.id,
                        create_dto,
                        target_date,
                        db
                    )
                    imported_count += 1
                    
            except Exception as e:
                error_msg = f"Ошибка сохранения заказа {order_data.get('order_number')}: {str(e)}"
                logger.error(error_msg)
                errors.append(error_msg)
        
        total_processed = imported_count + updated_count
        message = f"Импортировано: {imported_count}, обновлено: {updated_count}, всего: {total_processed}"
        
        if errors:
            message += f", ошибок: {len(errors)}"
        
        return ImportOrdersResponse(
            success=True,
            imported_count=imported_count,
            updated_count=updated_count,
            errors=errors,
            message=message
        )
        
    except Exception as e:
        logger.error(f"Ошибка импорта заказов: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка импорта: {str(e)}"
        )

