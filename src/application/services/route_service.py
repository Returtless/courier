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
            logger.info(f"🔍 Начало optimize_route для user_id={user_id}, date={order_date}")
            # Получаем заказы
            logger.debug("Загружаю заказы...")
            orders_dto = self.order_service.get_orders_by_date(user_id, order_date, session)
            logger.debug(f"Загружено заказов: {len(orders_dto)}")
            
            # Фильтруем только активные (не доставленные) заказы
            active_orders_dto = [o for o in orders_dto if o.status != "delivered"]
            logger.debug(f"Активных заказов: {len(active_orders_dto)}")
            
            if not active_orders_dto:
                logger.warning(f"Нет активных заказов для оптимизации для user_id={user_id}")
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
            logger.debug("Получаю точку старта...")
            start_location_db = self.route_repository.get_start_location(
                user_id, order_date, session
            )
            
            if not start_location_db:
                logger.warning(f"Точка старта не найдена для user_id={user_id}")
                return RouteOptimizationResult(
                    success=False,
                    error_message="Точка старта не установлена. Установите точку старта перед оптимизацией."
                )
            
            # Определяем start_location и start_time
            logger.debug("Извлекаю атрибуты точки старта...")
            # Безопасно получаем атрибуты из отсоединенного объекта через __dict__
            if hasattr(start_location_db, '__dict__'):
                db_dict = start_location_db.__dict__
                location_type = db_dict.get('location_type')
                latitude = db_dict.get('latitude')
                longitude = db_dict.get('longitude')
                address = db_dict.get('address')
                start_time = db_dict.get('start_time')
            else:
                # Fallback: пытаемся получить атрибуты напрямую
                try:
                    location_type = start_location_db.location_type
                    latitude = start_location_db.latitude
                    longitude = start_location_db.longitude
                    address = start_location_db.address
                    start_time = start_location_db.start_time
                except Exception as e:
                    logger.error(f"Ошибка получения атрибутов StartLocationDB: {e}", exc_info=True)
                    location_type = None
                    latitude = None
                    longitude = None
                    address = None
                    start_time = None
            
            logger.debug(f"Тип точки старта: {location_type}, start_time: {start_time}")
            if location_type == "geo":
                start_location = (latitude, longitude)
                logger.debug(f"Использую координаты: {start_location}")
            else:
                # Геокодируем адрес
                logger.info(f"Геокодирую адрес: {address}")
                lat, lon, _ = self.maps_service.geocode_address_sync(address)
                start_location = (lat, lon)
                logger.debug(f"Получены координаты из геокодирования: {start_location}")
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
            logger.info(f"Запускаю оптимизацию маршрута для {len(orders)} заказов...")
            optimized_route = self.route_optimizer.optimize_route_sync(
                orders=orders,
                start_location=start_location,
                start_time=start_time,
                user_id=user_id,
                use_fallback=recalculate_without_manual
            )
            logger.info(f"Оптимизация завершена, точек в маршруте: {len(optimized_route.points) if optimized_route.points else 0}")
            
            if not optimized_route.points:
                return RouteOptimizationResult(
                    success=False,
                    error_message="Не удалось оптимизировать маршрут. Проверьте, что у всех заказов есть координаты."
                )
            
            # Преобразуем OptimizedRoute в RouteDTO
            logger.debug("Преобразую оптимизированный маршрут в DTO...")
            route_dto = self._optimized_route_to_dto(optimized_route, active_orders_dto)
            
            # Сохраняем маршрут в БД
            logger.debug("Сохраняю маршрут в БД...")
            route_data = {
                'route_summary': [self._route_point_to_dict(p) for p in optimized_route.points],
                'route_order': [p.order.order_number for p in optimized_route.points],
                'call_schedule': self._build_call_schedule(optimized_route, user_id, order_date),
                'total_distance': optimized_route.total_distance,
                'total_time': optimized_route.total_time,
                'estimated_completion': optimized_route.estimated_completion
            }
            
            self.route_repository.save_route(user_id, order_date, route_data, session)
            logger.debug("Маршрут сохранен в БД")
            
            # Создаем/обновляем call_status для каждого заказа
            logger.debug("Создаю/обновляю call_status...")
            self._create_call_statuses(optimized_route, user_id, order_date, active_orders_dto, session)
            logger.debug("Call_status созданы/обновлены")
            
            return RouteOptimizationResult(
                success=True,
                route=route_dto
            )
            
        except Exception as e:
            import sys
            import traceback
            logger.error(f"Ошибка оптимизации маршрута: {e}", exc_info=True)
            logger.error(f"Полный traceback: {traceback.format_exc()}")
            sys.stdout.flush()
            return RouteOptimizationResult(
                success=False,
                error_message=f"Ошибка оптимизации: {str(e)}"
            )
    
    def set_current_order_index(
        self,
        user_id: int,
        order_date: date,
        index: int,
        session: Session = None
    ) -> bool:
        """
        Установить текущий индекс заказа в маршруте для навигации
        
        Args:
            user_id: ID пользователя
            order_date: Дата маршрута
            index: Индекс заказа в маршруте (0-based)
            session: Сессия БД (опционально)
            
        Returns:
            True если успешно, False если маршрут не найден или индекс невалиден
        """
        if order_date is None:
            order_date = date.today()
        
        route_db = self.route_repository.get_route(user_id, order_date, session)
        if not route_db:
            return False
        
        # Безопасно получаем route_order и route_summary из отсоединенного объекта через __dict__
        if hasattr(route_db, '__dict__'):
            db_dict = route_db.__dict__
            route_order = db_dict.get('route_order')
            route_summary = db_dict.get('route_summary')
        else:
            try:
                route_order = route_db.route_order
                route_summary = route_db.route_summary
            except Exception as e:
                logger.error(f"Ошибка получения атрибутов RouteDataDB в set_current_order_index: {e}", exc_info=True)
                return False
        
        # Проверяем валидность индекса
        if route_order and isinstance(route_order, list):
            if index < 0 or index >= len(route_order):
                return False
        
        # Сохраняем current_order_index в route_summary как метаданные
        # Используем специальный ключ '_current_index' в первом элементе route_summary
        # чтобы не нарушать существующую структуру
        if route_summary is None:
            route_summary = []
        
        # Если route_summary - список словарей, добавляем метаданные в первый элемент
        if isinstance(route_summary, list) and len(route_summary) > 0:
            if isinstance(route_summary[0], dict):
                # Добавляем метаданные в первый элемент, не нарушая остальные поля
                route_summary[0]['_current_index'] = index
            else:
                # Если первый элемент не словарь, создаем новый первый элемент с метаданными
                route_summary = [{'_current_index': index}] + list(route_summary)
        else:
            # Если route_summary пустой, создаем структуру с метаданными
            route_summary = [{'_current_index': index}]
        
        # Сохраняем обновленный route_summary в БД
        # Получаем текущие данные маршрута и обновляем только route_summary
        from src.database.connection import get_db_session
        if session:
            # Используем переданную сессию - получаем объект через внутренний метод репозитория
            actual_route_db = self.route_repository._get_route(user_id, order_date, session)
            if actual_route_db:
                actual_route_db.route_summary = route_summary
                from sqlalchemy.orm.attributes import flag_modified
                flag_modified(actual_route_db, 'route_summary')
                session.commit()
        else:
            # Создаем новую сессию для обновления
            with get_db_session() as sess:
                actual_route_db = self.route_repository._get_route(user_id, order_date, sess)
                if actual_route_db:
                    actual_route_db.route_summary = route_summary
                    from sqlalchemy.orm.attributes import flag_modified
                    flag_modified(actual_route_db, 'route_summary')
                    sess.commit()
        
        logger.info(f"📍 Установлен текущий индекс заказа {index} для user_id={user_id}, date={order_date}")
        return True
    
    def get_current_order_index(
        self,
        user_id: int,
        order_date: date,
        session: Session = None
    ) -> int:
        """
        Получить текущий индекс заказа в маршруте
        
        Args:
            user_id: ID пользователя
            order_date: Дата маршрута
            session: Сессия БД (опционально)
            
        Returns:
            Индекс заказа (по умолчанию 0)
        """
        route_db = self.route_repository.get_route(user_id, order_date, session)
        if not route_db:
            return 0
        
        # Безопасно получаем route_summary из отсоединенного объекта через __dict__
        if hasattr(route_db, '__dict__'):
            route_summary = route_db.__dict__.get('route_summary')
        else:
            try:
                route_summary = route_db.route_summary
            except Exception:
                route_summary = None
        
        if not route_summary:
            return 0
        
        # Извлекаем current_order_index из метаданных
        if isinstance(route_summary, list) and len(route_summary) > 0:
            first_item = route_summary[0]
            if isinstance(first_item, dict) and '_current_index' in first_item:
                return int(first_item['_current_index'])
        
        return 0
    
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
        
        # Безопасно получаем атрибуты из отсоединенного объекта через __dict__
        if hasattr(route_db, '__dict__'):
            db_dict = route_db.__dict__
            route_summary = db_dict.get('route_summary')
            route_order = db_dict.get('route_order')
            call_schedule = db_dict.get('call_schedule')
            total_distance = db_dict.get('total_distance')
            total_time = db_dict.get('total_time')
            estimated_completion = db_dict.get('estimated_completion')
        else:
            try:
                route_summary = route_db.route_summary
                route_order = route_db.route_order
                call_schedule = route_db.call_schedule
                total_distance = route_db.total_distance
                total_time = route_db.total_time
                estimated_completion = route_db.estimated_completion
            except Exception as e:
                logger.error(f"Ошибка получения атрибутов RouteDataDB: {e}", exc_info=True)
                return None
        
        # Преобразуем RouteDataDB в RouteDTO
        route_points = []
        if route_summary:
            # route_summary может быть списком словарей (новый формат) или списком строк (старый)
            if isinstance(route_summary, list) and len(route_summary) > 0:
                if isinstance(route_summary[0], dict):
                    # Новый формат
                    for point_dict in route_summary:
                        # Пропускаем метаданные (элементы с ключом _current_index)
                        if '_current_index' in point_dict and len(point_dict) == 1:
                            continue
                        # Убеждаемся, что address присутствует (может отсутствовать в старых данных)
                        if 'address' not in point_dict:
                            point_dict['address'] = ""
                        route_points.append(RoutePointDTO(**point_dict))
        
        call_schedule = route_db.call_schedule or []
        if isinstance(call_schedule, list) and len(call_schedule) > 0:
            if isinstance(call_schedule[0], str):
                # Старый формат - преобразуем в список словарей
                call_schedule = [{"text": text} for text in call_schedule]
        
        return RouteDTO(
            route_points=route_points,
            route_order=route_order or [],
            total_distance=total_distance,
            total_time=total_time,
            estimated_completion=estimated_completion,
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
        
        # Безопасно получаем атрибуты из отсоединенного объекта через __dict__
        if hasattr(start_location_db, '__dict__'):
            db_dict = start_location_db.__dict__
            attrs = {k: v for k, v in db_dict.items() if not k.startswith('_')}
        else:
            # Fallback: пытаемся получить атрибуты напрямую
            try:
                attrs = {
                    'location_type': start_location_db.location_type,
                    'address': start_location_db.address,
                    'latitude': start_location_db.latitude,
                    'longitude': start_location_db.longitude,
                    'start_time': start_location_db.start_time
                }
            except Exception as e:
                logger.error(f"Критическая ошибка преобразования StartLocationDB в StartLocationDTO: {e}", exc_info=True)
                attrs = {}
        
        return StartLocationDTO(
            location_type=attrs.get('location_type'),
            address=attrs.get('address'),
            latitude=attrs.get('latitude'),
            longitude=attrs.get('longitude'),
            start_time=attrs.get('start_time')
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
        
        # Безопасно получаем атрибуты из отсоединенного объекта через __dict__
        if hasattr(start_location_db, '__dict__'):
            db_dict = start_location_db.__dict__
            attrs = {k: v for k, v in db_dict.items() if not k.startswith('_')}
        else:
            # Fallback: пытаемся получить атрибуты напрямую
            try:
                attrs = {
                    'location_type': start_location_db.location_type,
                    'address': start_location_db.address,
                    'latitude': start_location_db.latitude,
                    'longitude': start_location_db.longitude,
                    'start_time': start_location_db.start_time
                }
            except Exception as e:
                import logging
                logger = logging.getLogger(__name__)
                logger.error(f"Критическая ошибка преобразования StartLocationDB в StartLocationDTO: {e}", exc_info=True)
                attrs = {}
        
        return StartLocationDTO(
            location_type=attrs.get('location_type'),
            address=attrs.get('address'),
            latitude=attrs.get('latitude'),
            longitude=attrs.get('longitude'),
            start_time=attrs.get('start_time')
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
            "address": point.order.address or "",  # Добавляем адрес для RoutePointDTO (может быть None)
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
    
    def delete_all_data_by_date(
        self,
        user_id: int,
        order_date: date = None,
        session: Session = None
    ) -> Dict[str, int]:
        """
        Удалить все данные пользователя за указанную дату
        
        Args:
            user_id: ID пользователя
            order_date: Дата (по умолчанию сегодня)
            session: Сессия БД (опционально)
            
        Returns:
            Словарь с количеством удаленных записей по типам
        """
        if order_date is None:
            order_date = date.today()
        
        if session is None:
            from src.database.connection import get_db_session
            with get_db_session() as session:
                return self._delete_all_data_by_date(user_id, order_date, session)
        return self._delete_all_data_by_date(user_id, order_date, session)
    
    def _delete_all_data_by_date(
        self,
        user_id: int,
        order_date: date,
        session: Session
    ) -> Dict[str, int]:
        """Внутренний метод удаления всех данных"""
        from sqlalchemy import and_
        from src.models.order import OrderDB, RouteDataDB, StartLocationDB, CallStatusDB
        
        deleted_counts = {
            'orders': 0,
            'routes': 0,
            'start_locations': 0,
            'call_statuses': 0
        }
        
        # Удаляем заказы
        orders = session.query(OrderDB).filter(
            and_(OrderDB.user_id == user_id, OrderDB.order_date == order_date)
        ).all()
        deleted_counts['orders'] = len(orders)
        for order in orders:
            session.delete(order)
        
        # Удаляем маршруты
        routes = session.query(RouteDataDB).filter(
            and_(RouteDataDB.user_id == user_id, RouteDataDB.route_date == order_date)
        ).all()
        deleted_counts['routes'] = len(routes)
        for route in routes:
            session.delete(route)
        
        # Удаляем точки старта
        start_locations = session.query(StartLocationDB).filter(
            and_(StartLocationDB.user_id == user_id, StartLocationDB.location_date == order_date)
        ).all()
        deleted_counts['start_locations'] = len(start_locations)
        for location in start_locations:
            session.delete(location)
        
        # Удаляем статусы звонков
        call_statuses = session.query(CallStatusDB).filter(
            and_(CallStatusDB.user_id == user_id, CallStatusDB.call_date == order_date)
        ).all()
        deleted_counts['call_statuses'] = len(call_statuses)
        for call_status in call_statuses:
            session.delete(call_status)
        
        session.commit()
        logger.info(f"🗑️ Удалены все данные для user_id={user_id}, date={order_date}: {deleted_counts}")
        
        return deleted_counts

