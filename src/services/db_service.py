import logging
from datetime import datetime, date, time
from typing import List, Optional, Dict
from sqlalchemy.orm import Session
from sqlalchemy import and_
from src.models.order import OrderDB, StartLocationDB, RouteDataDB, Order
from src.database.connection import get_db_session

logger = logging.getLogger(__name__)


class DatabaseService:
    """Сервис для работы с базой данных"""
    
    def __init__(self):
        pass
    
    def get_today_orders(self, user_id: int, session: Session = None) -> List[Dict]:
        """Получить все заказы пользователя за сегодня"""
        today = date.today()
        return self.get_orders_by_date(user_id, today, session)
    
    def get_orders_by_date(self, user_id: int, order_date: date, session: Session = None) -> List[Dict]:
        """Получить все заказы пользователя за конкретную дату"""
        if session is None:
            with get_db_session() as session:
                return self._get_orders(user_id, order_date, session)
        return self._get_orders(user_id, order_date, session)
    
    def _get_orders(self, user_id: int, order_date: date, session: Session) -> List[Dict]:
        """Внутренний метод получения заказов"""
        orders = session.query(OrderDB).filter(
            and_(
                OrderDB.user_id == user_id,
                OrderDB.order_date == order_date
            )
        ).all()
        
        result = []
        for order_db in orders:
            # Преобразуем time объекты в строки ISO формата
            delivery_time_start_str = None
            if order_db.delivery_time_start:
                # time объект в ISO формат: HH:MM:SS
                delivery_time_start_str = order_db.delivery_time_start.strftime('%H:%M:%S')
            
            delivery_time_end_str = None
            if order_db.delivery_time_end:
                delivery_time_end_str = order_db.delivery_time_end.strftime('%H:%M:%S')
            
            order_dict = {
                'id': order_db.id,
                'customer_name': order_db.customer_name,
                'phone': order_db.phone,
                'address': order_db.address,
                'latitude': order_db.latitude,
                'longitude': order_db.longitude,
                'comment': order_db.comment,
                'delivery_time_start': delivery_time_start_str,
                'delivery_time_end': delivery_time_end_str,
                'delivery_time_window': order_db.delivery_time_window,
                'status': order_db.status,
                'order_number': order_db.order_number,
                'entrance_number': order_db.entrance_number,
                'apartment_number': order_db.apartment_number,
                'gis_id': order_db.gis_id,
            }
            result.append(order_dict)
        
        return result
    
    def save_order(self, user_id: int, order: Order, order_date: date = None, session: Session = None) -> OrderDB:
        """Сохранить заказ в БД"""
        if order_date is None:
            order_date = date.today()
        
        if session is None:
            with get_db_session() as session:
                return self._save_order(user_id, order, order_date, session)
        return self._save_order(user_id, order, order_date, session)
    
    def _save_order(self, user_id: int, order: Order, order_date: date, session: Session) -> OrderDB:
        """Внутренний метод сохранения заказа"""
        try:
            order_db = OrderDB(
                user_id=user_id,
                order_date=order_date,
                customer_name=order.customer_name,
                phone=order.phone,
                address=order.address,
                latitude=order.latitude,
                longitude=order.longitude,
                comment=order.comment,
                delivery_time_start=order.delivery_time_start,
                delivery_time_end=order.delivery_time_end,
                delivery_time_window=order.delivery_time_window,
                status=order.status,
                order_number=order.order_number,
                entrance_number=order.entrance_number,
                apartment_number=order.apartment_number,
                gis_id=order.gis_id,
            )
            session.add(order_db)
            session.commit()
            session.refresh(order_db)
            return order_db
        except Exception as e:
            session.rollback()
            logger.error(f"Ошибка сохранения заказа в БД: {e}, данные: user_id={user_id}, order_date={order_date}, address={order.address}", exc_info=True)
            import traceback
            traceback.print_exc()
            raise
    
    def update_order(self, user_id: int, order_number: str, updates: Dict, order_date: date = None, session: Session = None) -> bool:
        """Обновить заказ"""
        if order_date is None:
            order_date = date.today()
        
        if session is None:
            with get_db_session() as session:
                return self._update_order(user_id, order_number, updates, order_date, session)
        return self._update_order(user_id, order_number, updates, order_date, session)
    
    def _update_order(self, user_id: int, order_number: str, updates: Dict, order_date: date, session: Session) -> bool:
        """Внутренний метод обновления заказа"""
        order_db = session.query(OrderDB).filter(
            and_(
                OrderDB.user_id == user_id,
                OrderDB.order_number == order_number,
                OrderDB.order_date == order_date
            )
        ).first()
        
        if not order_db:
            return False
        
        for key, value in updates.items():
            if hasattr(order_db, key):
                setattr(order_db, key, value)
        
        order_db.updated_at = datetime.utcnow()
        session.commit()
        return True
    
    def delete_orders_by_date(self, user_id: int, order_date: date = None, session: Session = None) -> int:
        """Удалить все заказы пользователя за дату"""
        if order_date is None:
            order_date = date.today()
        
        if session is None:
            with get_db_session() as session:
                return self._delete_orders_by_date(user_id, order_date, session)
        return self._delete_orders_by_date(user_id, order_date, session)
    
    def _delete_orders_by_date(self, user_id: int, order_date: date, session: Session) -> int:
        """Внутренний метод удаления заказов"""
        count = session.query(OrderDB).filter(
            and_(
                OrderDB.user_id == user_id,
                OrderDB.order_date == order_date
            )
        ).delete()
        session.commit()
        return count
    
    def save_start_location(self, user_id: int, location_type: str, address: str = None, 
                          latitude: float = None, longitude: float = None, 
                          start_time: datetime = None, location_date: date = None, 
                          session: Session = None) -> StartLocationDB:
        """Сохранить точку старта"""
        if location_date is None:
            location_date = date.today()
        
        if session is None:
            with get_db_session() as session:
                return self._save_start_location(user_id, location_type, address, latitude, 
                                                longitude, start_time, location_date, session)
        return self._save_start_location(user_id, location_type, address, latitude, 
                                        longitude, start_time, location_date, session)
    
    def _save_start_location(self, user_id: int, location_type: str, address: str, 
                            latitude: float, longitude: float, start_time: datetime, 
                            location_date: date, session: Session) -> StartLocationDB:
        """Внутренний метод сохранения точки старта"""
        # Удаляем старую точку старта за эту дату
        session.query(StartLocationDB).filter(
            and_(
                StartLocationDB.user_id == user_id,
                StartLocationDB.location_date == location_date
            )
        ).delete()
        
        start_location = StartLocationDB(
            user_id=user_id,
            location_date=location_date,
            location_type=location_type,
            address=address,
            latitude=latitude,
            longitude=longitude,
            start_time=start_time
        )
        session.add(start_location)
        session.commit()
        session.refresh(start_location)
        return start_location
    
    def get_start_location(self, user_id: int, location_date: date = None, session: Session = None) -> Optional[Dict]:
        """Получить точку старта пользователя за дату"""
        if location_date is None:
            location_date = date.today()
        
        if session is None:
            with get_db_session() as session:
                return self._get_start_location(user_id, location_date, session)
        return self._get_start_location(user_id, location_date, session)
    
    def _get_start_location(self, user_id: int, location_date: date, session: Session) -> Optional[Dict]:
        """Внутренний метод получения точки старта"""
        start_location = session.query(StartLocationDB).filter(
            and_(
                StartLocationDB.user_id == user_id,
                StartLocationDB.location_date == location_date
            )
        ).first()
        
        if not start_location:
            return None
        
        return {
            'location_type': start_location.location_type,
            'address': start_location.address,
            'latitude': start_location.latitude,
            'longitude': start_location.longitude,
            'start_time': start_location.start_time.isoformat() if start_location.start_time else None,
        }
    
    def save_route_data(self, user_id: int, route_points_data: List[Dict], call_schedule: List[str], 
                       route_order: List[str], total_distance: float, total_time: float,
                       estimated_completion: datetime, route_date: date = None, 
                       session: Session = None) -> RouteDataDB:
        """Сохранить структурированные данные маршрута"""
        if route_date is None:
            route_date = date.today()
        
        if session is None:
            with get_db_session() as session:
                return self._save_route_data(user_id, route_points_data, call_schedule, route_order,
                                           total_distance, total_time, estimated_completion, 
                                           route_date, session)
        return self._save_route_data(user_id, route_points_data, call_schedule, route_order,
                                    total_distance, total_time, estimated_completion, 
                                    route_date, session)
    
    def _save_route_data(self, user_id: int, route_points_data: List[Dict], call_schedule: List[str],
                        route_order: List[str], total_distance: float, total_time: float,
                        estimated_completion: datetime, route_date: date, session: Session) -> RouteDataDB:
        """Внутренний метод сохранения маршрута"""
        # Удаляем старые данные маршрута за эту дату
        session.query(RouteDataDB).filter(
            and_(
                RouteDataDB.user_id == user_id,
                RouteDataDB.route_date == route_date
            )
        ).delete()
        
        route_data = RouteDataDB(
            user_id=user_id,
            route_date=route_date,
            route_summary=route_points_data,  # Сохраняем структурированные данные
            call_schedule=call_schedule,
            route_order=route_order,
            total_distance=total_distance,
            total_time=total_time,
            estimated_completion=estimated_completion
        )
        session.add(route_data)
        session.commit()
        session.refresh(route_data)
        return route_data
    
    def get_route_data(self, user_id: int, route_date: date = None, session: Session = None) -> Optional[Dict]:
        """Получить данные маршрута пользователя за дату"""
        if route_date is None:
            route_date = date.today()
        
        if session is None:
            with get_db_session() as session:
                return self._get_route_data(user_id, route_date, session)
        return self._get_route_data(user_id, route_date, session)
    
    def _get_route_data(self, user_id: int, route_date: date, session: Session) -> Optional[Dict]:
        """Внутренний метод получения маршрута"""
        route_data = session.query(RouteDataDB).filter(
            and_(
                RouteDataDB.user_id == user_id,
                RouteDataDB.route_date == route_date
            )
        ).first()
        
        if not route_data:
            return None
        
        # Проверяем формат данных (старый или новый)
        route_summary = route_data.route_summary
        call_schedule = route_data.call_schedule
        
        # Проверяем формат route_summary
        route_points_data = None
        if route_summary and isinstance(route_summary, list) and len(route_summary) > 0:
            if isinstance(route_summary[0], dict):
                route_points_data = route_summary  # Новый формат
        
        # Проверяем формат call_schedule
        call_schedule_data = call_schedule
        if call_schedule and isinstance(call_schedule, list) and len(call_schedule) > 0:
            if isinstance(call_schedule[0], str):
                # Старый формат call_schedule - оставляем как есть для обратной совместимости
                pass
            elif isinstance(call_schedule[0], dict):
                # Новый формат - структурированные данные
                call_schedule_data = call_schedule
        
        result = {
            'call_schedule': call_schedule_data,
            'route_order': route_data.route_order,
            'total_distance': route_data.total_distance,
            'total_time': route_data.total_time,
            'estimated_completion': route_data.estimated_completion.isoformat() if route_data.estimated_completion else None,
        }
        
        if route_points_data:
            result['route_points_data'] = route_points_data
        else:
            result['route_summary'] = route_summary  # Старый формат
        
        return result
    
    def delete_all_data_by_date(self, user_id: int, target_date: date = None, session: Session = None) -> Dict[str, int]:
        """Удалить все данные пользователя за дату (заказы, точка старта, маршрут)"""
        if target_date is None:
            target_date = date.today()
        
        if session is None:
            with get_db_session() as session:
                return self._delete_all_data_by_date(user_id, target_date, session)
        return self._delete_all_data_by_date(user_id, target_date, session)
    
    def _delete_all_data_by_date(self, user_id: int, target_date: date, session: Session) -> Dict[str, int]:
        """Внутренний метод удаления всех данных"""
        orders_count = session.query(OrderDB).filter(
            and_(
                OrderDB.user_id == user_id,
                OrderDB.order_date == target_date
            )
        ).delete()
        
        locations_count = session.query(StartLocationDB).filter(
            and_(
                StartLocationDB.user_id == user_id,
                StartLocationDB.location_date == target_date
            )
        ).delete()
        
        routes_count = session.query(RouteDataDB).filter(
            and_(
                RouteDataDB.user_id == user_id,
                RouteDataDB.route_date == target_date
            )
        ).delete()
        
        session.commit()
        
        return {
            'orders': orders_count,
            'locations': locations_count,
            'routes': routes_count
        }

