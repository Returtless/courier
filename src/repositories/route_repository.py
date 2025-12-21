"""
Репозиторий для работы с маршрутами
"""
import logging
from typing import Optional, Dict, Any
from datetime import date, datetime
from sqlalchemy.orm import Session
from sqlalchemy import and_
from src.database.connection import get_db_session
from src.models.order import RouteDataDB, StartLocationDB
from .base_repository import BaseRepository

logger = logging.getLogger(__name__)


class RouteRepository:
    """Репозиторий для работы с маршрутами"""
    
    def __init__(self):
        self.route_data_repo = BaseRepository(RouteDataDB)
        self.start_location_repo = BaseRepository(StartLocationDB)
    
    def get_route(
        self, 
        user_id: int, 
        route_date: date, 
        session: Session = None
    ) -> Optional[RouteDataDB]:
        """
        Получить данные маршрута
        
        Args:
            user_id: ID пользователя
            route_date: Дата маршрута
            session: Сессия БД (опционально)
            
        Returns:
            Данные маршрута или None
        """
        if session is None:
            with get_db_session() as session:
                return self._get_route(user_id, route_date, session)
        return self._get_route(user_id, route_date, session)
    
    def _get_route(
        self, 
        user_id: int, 
        route_date: date, 
        session: Session
    ) -> Optional[RouteDataDB]:
        """Внутренний метод получения маршрута"""
        return session.query(RouteDataDB).filter(
            and_(
                RouteDataDB.user_id == user_id,
                RouteDataDB.route_date == route_date
            )
        ).first()
    
    def save_route(
        self, 
        user_id: int, 
        route_date: date, 
        route_data: Dict[str, Any],
        session: Session = None
    ) -> RouteDataDB:
        """
        Сохранить данные маршрута
        
        Args:
            user_id: ID пользователя
            route_date: Дата маршрута
            route_data: Словарь с данными маршрута:
                - route_summary: List[Dict] или List[str]
                - call_schedule: List[Dict] или List[str]
                - route_order: List[str]
                - route_points_data: List[Dict] (опционально)
                - total_distance: float
                - total_time: float
                - estimated_completion: datetime
            session: Сессия БД (опционально)
            
        Returns:
            Сохраненные данные маршрута
        """
        if session is None:
            with get_db_session() as session:
                return self._save_route(user_id, route_date, route_data, session)
        return self._save_route(user_id, route_date, route_data, session)
    
    def _save_route(
        self, 
        user_id: int, 
        route_date: date, 
        route_data: Dict[str, Any],
        session: Session
    ) -> RouteDataDB:
        """Внутренний метод сохранения маршрута"""
        # Проверяем, существует ли маршрут
        existing_route = self._get_route(user_id, route_date, session)
        
        if existing_route:
            # Обновляем существующий маршрут
            existing_route.route_summary = route_data.get('route_summary')
            existing_route.call_schedule = route_data.get('call_schedule')
            existing_route.route_order = route_data.get('route_order')
            existing_route.total_distance = route_data.get('total_distance')
            existing_route.total_time = route_data.get('total_time')
            existing_route.estimated_completion = route_data.get('estimated_completion')
            session.commit()
            session.refresh(existing_route)
            logger.info(f"🔄 Обновлен маршрут для user_id={user_id}, date={route_date}")
            return existing_route
        else:
            # Создаем новый маршрут
            new_route = RouteDataDB(
                user_id=user_id,
                route_date=route_date,
                route_summary=route_data.get('route_summary'),
                call_schedule=route_data.get('call_schedule'),
                route_order=route_data.get('route_order'),
                total_distance=route_data.get('total_distance'),
                total_time=route_data.get('total_time'),
                estimated_completion=route_data.get('estimated_completion')
            )
            session.add(new_route)
            session.commit()
            session.refresh(new_route)
            logger.info(f"✅ Создан новый маршрут для user_id={user_id}, date={route_date}")
            return new_route
    
    def get_start_location(
        self, 
        user_id: int, 
        location_date: date, 
        session: Session = None
    ) -> Optional[StartLocationDB]:
        """
        Получить точку старта
        
        Args:
            user_id: ID пользователя
            location_date: Дата
            session: Сессия БД (опционально)
            
        Returns:
            Точка старта или None
        """
        if session is None:
            with get_db_session() as session:
                return self._get_start_location(user_id, location_date, session)
        return self._get_start_location(user_id, location_date, session)
    
    def _get_start_location(
        self, 
        user_id: int, 
        location_date: date, 
        session: Session
    ) -> Optional[StartLocationDB]:
        """Внутренний метод получения точки старта"""
        return session.query(StartLocationDB).filter(
            and_(
                StartLocationDB.user_id == user_id,
                StartLocationDB.location_date == location_date
            )
        ).first()
    
    def save_start_location(
        self, 
        user_id: int, 
        location_date: date, 
        location_data: Dict[str, Any],
        session: Session = None
    ) -> StartLocationDB:
        """
        Сохранить точку старта
        
        Args:
            user_id: ID пользователя
            location_date: Дата
            location_data: Словарь с данными:
                - location_type: str ("geo" или "address")
                - address: str (опционально)
                - latitude: float (опционально)
                - longitude: float (опционально)
                - start_time: datetime (опционально)
            session: Сессия БД (опционально)
            
        Returns:
            Сохраненная точка старта
        """
        if session is None:
            with get_db_session() as session:
                return self._save_start_location(user_id, location_date, location_data, session)
        return self._save_start_location(user_id, location_date, location_data, session)
    
    def _save_start_location(
        self, 
        user_id: int, 
        location_date: date, 
        location_data: Dict[str, Any],
        session: Session
    ) -> StartLocationDB:
        """Внутренний метод сохранения точки старта"""
        # Проверяем, существует ли точка старта
        existing_location = self._get_start_location(user_id, location_date, session)
        
        if existing_location:
            # Обновляем существующую точку
            existing_location.location_type = location_data.get('location_type', existing_location.location_type)
            existing_location.address = location_data.get('address', existing_location.address)
            existing_location.latitude = location_data.get('latitude', existing_location.latitude)
            existing_location.longitude = location_data.get('longitude', existing_location.longitude)
            existing_location.start_time = location_data.get('start_time', existing_location.start_time)
            session.commit()
            session.refresh(existing_location)
            logger.info(f"🔄 Обновлена точка старта для user_id={user_id}, date={location_date}")
            return existing_location
        else:
            # Создаем новую точку
            new_location = StartLocationDB(
                user_id=user_id,
                location_date=location_date,
                location_type=location_data.get('location_type', 'geo'),
                address=location_data.get('address'),
                latitude=location_data.get('latitude'),
                longitude=location_data.get('longitude'),
                start_time=location_data.get('start_time')
            )
            session.add(new_location)
            session.commit()
            session.refresh(new_location)
            logger.info(f"✅ Создана точка старта для user_id={user_id}, date={location_date}")
            return new_location

