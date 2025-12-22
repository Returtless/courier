"""
Сервис для работы с маршрутами
Содержит бизнес-логику оптимизации и управления маршрутами
"""
import logging
from datetime import date, datetime, time
from typing import Optional, List, Tuple, Dict
from sqlalchemy.orm import Session

from src.application.dto.route_dto import (
    RouteDTO, RoutePointDTO, StartLocationDTO, 
    RouteOptimizationRequest, RouteOptimizationResult
)
from src.application.services.order_service import OrderService
from src.repositories.route_repository import RouteRepository
from src.repositories.call_status_repository import CallStatusRepository
from src.services.route_optimizer import RouteOptimizer
from src.services.maps_service import MapsService
from src.services.user_settings_service import UserSettingsService
from src.models.order import Order

logger = logging.getLogger(__name__)


class RouteService:
    """Сервис для работы с маршрутами"""
    
    def __init__(
        self,
        route_repository: RouteRepository,
        order_service: OrderService,
        call_status_repository: CallStatusRepository,
        maps_service: MapsService
    ):
        """
        Args:
            route_repository: Репозиторий для работы с маршрутами
            order_service: Сервис для работы с заказами
            call_status_repository: Репозиторий для работы со статусами звонков
            maps_service: Сервис для работы с картами
        """
        self.route_repository = route_repository
        self.order_service = order_service
        self.call_status_repository = call_status_repository
        self.maps_service = maps_service
        self.route_optimizer = RouteOptimizer(maps_service)
        self.settings_service = UserSettingsService()
    
    def optimize_route(
        self,
        user_id: int,
        order_date: date = None,
        request: Optional[RouteOptimizationRequest] = None,
        session: Session = None
    ) -> RouteOptimizationResult:
        """
        Оптимизировать маршрут для пользователя
        
        Args:
            user_id: ID пользователя
            order_date: Дата заказов (по умолчанию сегодня)
            request: Параметры оптимизации (опционально)
            session: Сессия БД (опционально)
            
        Returns:
            Результат оптимизации маршрута
        """
        if order_date is None:
            order_date = date.today()
        
        try:
            # Получаем заказы
            orders_dto = self.order_service.get_orders_by_date(user_id, order_date, session)
            
            # Фильтруем только активные (не доставленные) заказы
            active_orders_dto = [o for o in orders_dto if o.status != "delivered"]
            
            if not active_orders_dto:
                return RouteOptimizationResult(
                    success=False,
                    error_message="Нет активных заказов для оптимизации"
                )
            
            # Преобразуем DTO в Order для RouteOptimizer
            orders = []
            for order_dto in active_orders_dto:
                order = Order(
                    order_number=order_dto.order_number,
                    customer_name=order_dto.customer_name,
                    phone=order_dto.phone,
                    address=order_dto.address,
                    latitude=order_dto.latitude,
                    longitude=order_dto.longitude,
                    comment=order_dto.comment,
                    delivery_time_start=order_dto.delivery_time_start,
                    delivery_time_end=order_dto.delivery_time_end,
                    delivery_time_window=order_dto.delivery_time_window,
                    entrance_number=order_dto.entrance_number,
                    apartment_number=order_dto.apartment_number,
                    gis_id=order_dto.gis_id,
                    status=order_dto.status
                )
                # Добавляем manual_arrival_time из DTO
                if order_dto.manual_arrival_time:
                    order.manual_arrival_time = order_dto.manual_arrival_time
                orders.append(order)
            
            # Получаем точку старта
            start_location_db = self.route_repository.get_start_location(
                user_id, order_date, session
            )
            
            if not start_location_db:
                return RouteOptimizationResult(
                    success=False,
                    error_message="Точка старта не установлена. Установите точку старта перед оптимизацией."
                )
            
            # Определяем start_location и start_time
            if start_location_db.location_type == "geo":
                start_location = (start_location_db.latitude, start_location_db.longitude)
            else:
                # Геокодируем адрес
                lat, lon, _ = self.maps_service.geocode_address_sync(start_location_db.address)
                start_location = (lat, lon)
            
            start_time = start_location_db.start_time
            if not start_time:
                # Используем текущее время
                start_time = datetime.combine(order_date, time(9, 0))  # 9:00 по умолчанию
            
            # Если recalculate_without_manual, убираем manual_arrival_time из заказов
            recalculate_without_manual = False
            if request and request.recalculate_without_manual:
                recalculate_without_manual = True
                for order in orders:
                    order.manual_arrival_time = None
            
            # Оптимизируем маршрут
            optimized_route = self.route_optimizer.optimize_route_sync(
                orders=orders,
                start_location=start_location,
                start_time=start_time,
                user_id=user_id,
                use_fallback=recalculate_without_manual
            )
            
            if not optimized_route.points:
                return RouteOptimizationResult(
                    success=False,
                    error_message="Не удалось оптимизировать маршрут. Проверьте, что у всех заказов есть координаты."
                )
            
            # Преобразуем OptimizedRoute в RouteDTO
            route_dto = self._optimized_route_to_dto(optimized_route, active_orders_dto)
            
            # Сохраняем маршрут в БД
            route_data = {
                'route_summary': [self._route_point_to_dict(p) for p in optimized_route.points],
                'route_order': [p.order.order_number for p in optimized_route.points],
                'call_schedule': self._build_call_schedule(optimized_route, user_id, order_date),
                'total_distance': optimized_route.total_distance,
                'total_time': optimized_route.total_time,
                'estimated_completion': optimized_route.estimated_completion
            }
            
            self.route_repository.save_route(user_id, order_date, route_data, session)
            
            # Создаем/обновляем call_status для каждого заказа
            self._create_call_statuses(optimized_route, user_id, order_date, active_orders_dto, session)
            
            return RouteOptimizationResult(
                success=True,
                route=route_dto
            )
            
        except Exception as e:
            logger.error(f"Ошибка оптимизации маршрута: {e}", exc_info=True)
            return RouteOptimizationResult(
                success=False,
                error_message=f"Ошибка оптимизации: {str(e)}"
            )
    
    def get_route(
        self,
        user_id: int,
        order_date: date = None,
        session: Session = None
    ) -> Optional[RouteDTO]:
        """
        Получить маршрут пользователя
        
        Args:
            user_id: ID пользователя
            order_date: Дата маршрута (по умолчанию сегодня)
            session: Сессия БД (опционально)
            
        Returns:
            Маршрут в формате DTO или None
        """
        if order_date is None:
            order_date = date.today()
        
        route_db = self.route_repository.get_route(user_id, order_date, session)
        
        if not route_db:
            return None
        
        # Преобразуем RouteDataDB в RouteDTO
        route_points = []
        if route_db.route_summary:
            # route_summary может быть списком словарей (новый формат) или списком строк (старый)
            if isinstance(route_db.route_summary, list) and len(route_db.route_summary) > 0:
                if isinstance(route_db.route_summary[0], dict):
                    # Новый формат
                    for point_dict in route_db.route_summary:
                        route_points.append(RoutePointDTO(**point_dict))
        
        call_schedule = route_db.call_schedule or []
        if isinstance(call_schedule, list) and len(call_schedule) > 0:
            if isinstance(call_schedule[0], str):
                # Старый формат - преобразуем в список словарей
                call_schedule = [{"text": text} for text in call_schedule]
        
        return RouteDTO(
            route_points=route_points,
            route_order=route_db.route_order or [],
            total_distance=route_db.total_distance,
            total_time=route_db.total_time,
            estimated_completion=route_db.estimated_completion,
            call_schedule=call_schedule
        )
    
    def get_start_location(
        self,
        user_id: int,
        order_date: date = None,
        session: Session = None
    ) -> Optional[StartLocationDTO]:
        """
        Получить точку старта
        
        Args:
            user_id: ID пользователя
            order_date: Дата (по умолчанию сегодня)
            session: Сессия БД (опционально)
            
        Returns:
            Точка старта в формате DTO или None
        """
        if order_date is None:
            order_date = date.today()
        
        start_location_db = self.route_repository.get_start_location(
            user_id, order_date, session
        )
        
        if not start_location_db:
            return None
        
        return StartLocationDTO(
            location_type=start_location_db.location_type,
            address=start_location_db.address,
            latitude=start_location_db.latitude,
            longitude=start_location_db.longitude,
            start_time=start_location_db.start_time
        )
    
    def save_start_location(
        self,
        user_id: int,
        location_data: StartLocationDTO,
        order_date: date = None,
        session: Session = None
    ) -> StartLocationDTO:
        """
        Сохранить точку старта
        
        Args:
            user_id: ID пользователя
            location_data: Данные точки старта
            order_date: Дата (по умолчанию сегодня)
            session: Сессия БД (опционально)
            
        Returns:
            Сохраненная точка старта в формате DTO
        """
        if order_date is None:
            order_date = date.today()
        
        location_dict = location_data.dict(exclude_unset=True)
        start_location_db = self.route_repository.save_start_location(
            user_id, order_date, location_dict, session
        )
        
        return StartLocationDTO(
            location_type=start_location_db.location_type,
            address=start_location_db.address,
            latitude=start_location_db.latitude,
            longitude=start_location_db.longitude,
            start_time=start_location_db.start_time
        )
    
    def recalculate_without_manual_times(
        self,
        user_id: int,
        order_date: date = None,
        session: Session = None
    ) -> RouteOptimizationResult:
        """
        Пересчитать маршрут без учета ручных времен
        
        Args:
            user_id: ID пользователя
            order_date: Дата заказов (по умолчанию сегодня)
            session: Сессия БД (опционально)
            
        Returns:
            Результат оптимизации маршрута
        """
        request = RouteOptimizationRequest(recalculate_without_manual=True)
        return self.optimize_route(user_id, order_date, request, session)
    
    def _optimized_route_to_dto(
        self,
        optimized_route,
        orders_dto: List
    ) -> RouteDTO:
        """Преобразовать OptimizedRoute в RouteDTO"""
        route_points = []
        orders_dict = {o.order_number: o for o in orders_dto}
        
        for point in optimized_route.points:
            order_dto = orders_dict.get(point.order.order_number)
            if order_dto:
                route_points.append(RoutePointDTO(
                    order_number=point.order.order_number,
                    address=point.order.address or "",
                    estimated_arrival=point.estimated_arrival,
                    call_time=self._calculate_call_time(point.estimated_arrival, point.order.order_number, orders_dto),
                    distance_from_previous=point.distance_from_previous,
                    time_from_previous=point.time_from_previous,
                    customer_name=order_dto.customer_name,
                    phone=order_dto.phone,
                    comment=order_dto.comment
                ))
        
        return RouteDTO(
            route_points=route_points,
            route_order=[p.order.order_number for p in optimized_route.points],
            total_distance=optimized_route.total_distance,
            total_time=optimized_route.total_time,
            estimated_completion=optimized_route.estimated_completion,
            call_schedule=self._build_call_schedule(optimized_route, None, None)
        )
    
    def _calculate_call_time(
        self,
        arrival_time: datetime,
        order_number: str,
        orders_dto: List
    ) -> Optional[datetime]:
        """Рассчитать время звонка на основе времени прибытия"""
        # Находим заказ
        order_dto = next((o for o in orders_dto if o.order_number == order_number), None)
        if not order_dto:
            return None
        
        # Получаем настройки пользователя (нужен user_id, но его нет в контексте)
        # Используем значение по умолчанию
        call_advance_minutes = 10
        
        from datetime import timedelta
        call_time = arrival_time - timedelta(minutes=call_advance_minutes)
        return call_time
    
    def _build_call_schedule(
        self,
        optimized_route,
        user_id: Optional[int],
        order_date: Optional[date]
    ) -> List[Dict]:
        """Построить график звонков"""
        call_schedule = []
        
        for point in optimized_route.points:
            call_time = self._calculate_call_time(
                point.estimated_arrival,
                point.order.order_number,
                []
            )
            if call_time:
                call_schedule.append({
                    "order_number": point.order.order_number,
                    "call_time": call_time.isoformat(),
                    "arrival_time": point.estimated_arrival.isoformat()
                })
        
        return call_schedule
    
    def _route_point_to_dict(self, point) -> Dict:
        """Преобразовать RoutePoint в словарь"""
        return {
            "order_number": point.order.order_number,
            "estimated_arrival": point.estimated_arrival.isoformat() if point.estimated_arrival else None,
            "distance_from_previous": point.distance_from_previous,
            "time_from_previous": point.time_from_previous
        }
    
    def _create_call_statuses(
        self,
        optimized_route,
        user_id: int,
        order_date: date,
        orders_dto: List,
        session: Session = None
    ):
        """Создать/обновить статусы звонков для заказов в маршруте"""
        orders_dict = {o.order_number: o for o in orders_dto}
        
        for point in optimized_route.points:
            order_dto = orders_dict.get(point.order.order_number)
            if not order_dto:
                continue
            
            # Рассчитываем время звонка
            call_time = self._calculate_call_time(
                point.estimated_arrival,
                point.order.order_number,
                orders_dto
            )
            
            if call_time and order_dto.phone:
                # Проверяем, есть ли уже call_status
                existing_call_status = self.call_status_repository.get_by_order(
                    user_id, point.order.order_number, order_date, session
                )
                
                if not existing_call_status:
                    # Создаем новый call_status
                    self.call_status_repository.create_or_update(
                        user_id=user_id,
                        order_number=point.order.order_number,
                        call_time=call_time,
                        phone=order_dto.phone,
                        customer_name=order_dto.customer_name,
                        call_date=order_date,
                        is_manual_call=False,
                        is_manual_arrival=False,
                        arrival_time=point.estimated_arrival,
                        manual_arrival_time=None,
                        session=session
                    )

