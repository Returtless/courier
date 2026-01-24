"""
Гибридный оптимизатор маршрута с кластеризацией
"""
import logging
from typing import List, Tuple
from datetime import datetime, timedelta
from math import radians, sin, cos, sqrt, atan2

from src.models.order import Order, RoutePoint, OptimizedRoute
from src.services.maps_service import MapsService
from src.services.user_settings_service import UserSettingsService

logger = logging.getLogger(__name__)


class HybridRouteOptimizer:
    """Гибридный оптимизатор: кластеризация по географии → сортировка по времени → OR-Tools"""
    
    def __init__(self, maps_service: MapsService, route_optimizer):
        self.maps_service = maps_service
        self.route_optimizer = route_optimizer  # Оригинальный RouteOptimizer
        self.settings_service = UserSettingsService()
    
    def optimize_route_hybrid(
        self,
        orders: List[Order],
        start_location: Tuple[float, float],
        start_time: datetime,
        user_id: int = None,
        cluster_radius_km: float = 3.0,
        critical_threshold_hour: int = 13,
        medium_threshold_hour: int = 15
    ) -> OptimizedRoute:
        """
        УМНАЯ оптимизация с приоритизацией:
        1. Разделение заказов на группы ПРИОРИТЕТОВ (по критичности окна)
        2. Обработка групп последовательно (сначала критичные)
        3. Внутри каждой группы - OR-Tools с учётом географии
        4. Сборка итогового маршрута
        
        Приоритеты:
        - 0: Ручное время (жёсткая привязка)
        - 1: Критичные окна (конец до critical_threshold_hour)
        - 2: Средние окна (конец critical_threshold_hour - medium_threshold_hour)
        - 3: Гибкие окна (конец после medium_threshold_hour)
        - 4: Без ограничений
        
        Args:
            orders: Список заказов
            start_location: Точка старта (lat, lon)
            start_time: Время старта
            user_id: ID пользователя
            cluster_radius_km: Радиус кластера (км)
            critical_threshold_hour: Час для критичных окон (по умолчанию 13)
            medium_threshold_hour: Час для средних окон (по умолчанию 15)
            
        Returns:
            Оптимизированный маршрут
        """
        if not orders:
            return OptimizedRoute(points=[], total_distance=0, total_time=0, estimated_completion=start_time)
        
        logger.info(f"🎯 УМНАЯ ОПТИМИЗАЦИЯ С ПРИОРИТИЗАЦИЕЙ: {len(orders)} заказов")
        logger.info(f"⏰ Время старта от базы: {start_time.strftime('%H:%M')}")
        
        # Шаг 1: Группировка заказов по ПРИОРИТЕТАМ
        priority_groups = self._group_orders_by_priority(orders, start_time, critical_threshold_hour, medium_threshold_hour)
        logger.info(f"📊 Создано {len(priority_groups)} групп приоритетов")
        
        # Шаг 2: Обработка каждой группы приоритета
        all_route_points = []
        total_distance = 0.0
        total_time = 0.0
        current_location = start_location
        current_time = start_time
        
        for priority_idx, (priority_level, priority_orders) in enumerate(priority_groups, 1):
            logger.info(f"🔧 Обрабатываю приоритет {priority_idx}/{len(priority_groups)}: {priority_level} ({len(priority_orders)} заказов)")
            
            # Используем OR-Tools для оптимизации внутри группы приоритета
            # OR-Tools сам найдёт оптимальный маршрут с учётом географии И временных окон
            if len(priority_orders) == 1:
                # Один заказ - обрабатываем напрямую
                order = priority_orders[0]
                if order.latitude and order.longitude:
                    try:
                        distance, travel_time = self.maps_service.get_route_sync(
                            current_location[0], current_location[1],
                            order.latitude, order.longitude,
                            user_id=user_id
                        )
                        
                        current_time += timedelta(minutes=travel_time)
                        
                        # Проверяем временное окно
                        if order.delivery_time_start and order.delivery_time_end:
                            order_date = start_time.date()
                            window_start = datetime.combine(order_date, order.delivery_time_start)
                            window_end = datetime.combine(order_date, order.delivery_time_end)
                            
                            # Если приедем раньше - ждем
                            if current_time < window_start:
                                wait_time = (window_start - current_time).total_seconds() / 60.0
                                logger.info(f"   ⏰ Заказ {order.order_number}: ожидание {wait_time:.0f} мин до начала окна")
                                current_time = window_start
                            
                            # Проверяем, не опаздываем ли
                            if current_time > window_end:
                                delay = (current_time - window_end).total_seconds() / 60.0
                                logger.warning(f"   ⚠️ Заказ {order.order_number}: опоздание {delay:.0f} мин")
                        
                        point = RoutePoint(
                            order=order,
                            estimated_arrival=current_time,
                            distance_from_previous=distance,
                            time_from_previous=travel_time
                        )
                        all_route_points.append(point)
                        
                        total_distance += distance
                        total_time += travel_time
                        
                        # Добавляем время обслуживания
                        service_time_minutes = 10
                        if user_id:
                            user_settings = self.settings_service.get_settings(user_id)
                            service_time_minutes = user_settings.service_time_minutes
                        current_time += timedelta(minutes=service_time_minutes)
                        total_time += service_time_minutes
                        
                        current_location = (order.latitude, order.longitude)
                        
                    except Exception as e:
                        logger.error(f"❌ Ошибка обработки заказа {order.order_number}: {e}")
            else:
                # Несколько заказов - используем OR-Tools
                logger.info(f"   🔍 OR-Tools оптимизация {len(priority_orders)} заказов")
                
                # Оптимизируем группу от текущей позиции
                group_route = self.route_optimizer.optimize_route_sync(
                    orders=priority_orders,
                    start_location=current_location,
                    start_time=current_time,
                    user_id=user_id,
                    use_fallback=True
                )
                
                if group_route and group_route.points:
                    # КРИТИЧНО: Корректируем времена прибытия с учётом временных окон
                    corrected_points = self._correct_arrival_times(group_route.points, start_time)
                    
                    # Добавляем точки из группы
                    for point in corrected_points:
                        all_route_points.append(point)
                    
                    # Обновляем текущие параметры
                    last_point = corrected_points[-1]
                    current_location = (last_point.order.latitude, last_point.order.longitude)
                    current_time = last_point.estimated_arrival
                    
                    # Добавляем время обслуживания последней точки
                    service_time_minutes = 10
                    if user_id:
                        user_settings = self.settings_service.get_settings(user_id)
                        service_time_minutes = user_settings.service_time_minutes
                    current_time += timedelta(minutes=service_time_minutes)
                    
                    # Пересчитываем расстояние и время
                    group_distance = sum(p.distance_from_previous for p in corrected_points)
                    group_time = (corrected_points[-1].estimated_arrival - corrected_points[0].estimated_arrival).total_seconds() / 60.0
                    group_time += service_time_minutes  # Время обслуживания последней точки
                    
                    total_distance += group_distance
                    total_time += group_time
                    
                    logger.info(f"   ✅ Группа обработана: {len(corrected_points)} точек")
                else:
                    logger.warning(f"   ⚠️ OR-Tools не смог оптимизировать группу, пропускаем")
        
        logger.info(f"✅ УМНАЯ ОПТИМИЗАЦИЯ ЗАВЕРШЕНА: {len(all_route_points)} точек, {total_distance:.1f} км, {total_time:.0f} мин")
        
        return OptimizedRoute(
            points=all_route_points,
            total_distance=total_distance,
            total_time=total_time,
            estimated_completion=current_time
        )
    
    def _group_orders_by_priority(
        self,
        orders: List[Order],
        start_time: datetime,
        critical_threshold_hour: int = 13,
        medium_threshold_hour: int = 15
    ) -> List[Tuple[str, List[Order]]]:
        """
        Группирует заказы по ПРИОРИТЕТАМ (критичности временного окна).
        
        Приоритеты:
        - 0: Ручное время (жёсткая привязка)
        - 1: Критичные окна (конец до critical_threshold_hour) - САМЫЕ ВАЖНЫЕ
        - 2: Средние окна (конец critical_threshold_hour - medium_threshold_hour)
        - 3: Гибкие окна (конец после medium_threshold_hour)
        - 4: Без ограничений
        
        Args:
            orders: Список заказов
            start_time: Время старта маршрута
            critical_threshold_hour: Час для критичных окон (по умолчанию 13)
            medium_threshold_hour: Час для средних окон (по умолчанию 15)
            
        Returns:
            Список кортежей (название_приоритета, список_заказов), отсортированный по приоритету
        """
        logger.info(f"📅 Группирую {len(orders)} заказов по ПРИОРИТЕТАМ (критичные до {critical_threshold_hour}:00, средние до {medium_threshold_hour}:00)")
        
        order_date = start_time.date()
        
        # Разделяем заказы по приоритетам
        manual_orders = []  # Приоритет 0
        critical_orders = []  # Приоритет 1
        medium_orders = []  # Приоритет 2
        flexible_orders = []  # Приоритет 3
        no_window_orders = []  # Приоритет 4
        
        for order in orders:
            if order.manual_arrival_time:
                manual_orders.append(order)
            elif order.delivery_time_start and order.delivery_time_end:
                window_end = datetime.combine(order_date, order.delivery_time_end)
                critical_threshold = datetime.combine(order_date, order.delivery_time_end.replace(hour=critical_threshold_hour, minute=0, second=0))
                medium_threshold = datetime.combine(order_date, order.delivery_time_end.replace(hour=medium_threshold_hour, minute=0, second=0))
                
                if window_end <= critical_threshold:
                    critical_orders.append(order)
                elif window_end <= medium_threshold:
                    medium_orders.append(order)
                else:
                    flexible_orders.append(order)
            else:
                no_window_orders.append(order)
        
        # Сортируем заказы внутри каждой группы по началу окна
        def get_order_start_time(order):
            if order.manual_arrival_time:
                return datetime.combine(order_date, order.manual_arrival_time.time())
            elif order.delivery_time_start:
                return datetime.combine(order_date, order.delivery_time_start)
            else:
                return datetime.max
        
        manual_orders.sort(key=get_order_start_time)
        critical_orders.sort(key=get_order_start_time)
        medium_orders.sort(key=get_order_start_time)
        flexible_orders.sort(key=get_order_start_time)
        
        # Собираем результат
        result = []
        if manual_orders:
            result.append(("Приоритет 0: Ручное время", manual_orders))
            logger.info(f"   📌 Приоритет 0 (Ручное время): {len(manual_orders)} заказов")
        if critical_orders:
            result.append((f"Приоритет 1: Критичные окна (до {critical_threshold_hour}:00)", critical_orders))
            logger.info(f"   🔴 Приоритет 1 (Критичные до {critical_threshold_hour}:00): {len(critical_orders)} заказов")
        if medium_orders:
            result.append((f"Приоритет 2: Средние окна ({critical_threshold_hour}:00-{medium_threshold_hour}:00)", medium_orders))
            logger.info(f"   🟡 Приоритет 2 (Средние {critical_threshold_hour}-{medium_threshold_hour}): {len(medium_orders)} заказов")
        if flexible_orders:
            result.append((f"Приоритет 3: Гибкие окна (после {medium_threshold_hour}:00)", flexible_orders))
            logger.info(f"   🟢 Приоритет 3 (Гибкие после {medium_threshold_hour}:00): {len(flexible_orders)} заказов")
        if no_window_orders:
            result.append(("Приоритет 4: Без ограничений", no_window_orders))
            logger.info(f"   ⚪ Приоритет 4 (Без ограничений): {len(no_window_orders)} заказов")
        
        return result
    
    def _correct_arrival_times(
        self,
        points: List[RoutePoint],
        start_time: datetime
    ) -> List[RoutePoint]:
        """
        Корректирует времена прибытия, чтобы не приезжать раньше начала временного окна.
        
        Если первая точка группы имеет окно 10:00-13:00, но OR-Tools выдал прибытие 09:32,
        сдвигаем ВСЕ точки группы на +28 минут.
        
        Args:
            points: Список точек маршрута от OR-Tools
            start_time: Время старта маршрута
            
        Returns:
            Скорректированные точки
        """
        if not points:
            return points
        
        # Находим самую раннюю точку с временным окном
        earliest_window_point = None
        earliest_window_start = None
        
        for point in points:
            order = point.order
            if order.delivery_time_start and order.delivery_time_end:
                order_date = start_time.date()
                window_start = datetime.combine(order_date, order.delivery_time_start)
                
                if earliest_window_start is None or window_start < earliest_window_start:
                    earliest_window_start = window_start
                    earliest_window_point = point
        
        # Если нет окон, возвращаем как есть
        if not earliest_window_point:
            return points
        
        # Проверяем, приезжаем ли мы раньше начала окна
        first_arrival = earliest_window_point.estimated_arrival
        if first_arrival >= earliest_window_start:
            # Всё ОК, не приезжаем раньше
            return points
        
        # Вычисляем сдвиг (сколько нужно ждать)
        time_shift = earliest_window_start - first_arrival
        logger.info(f"   ⏰ Сдвигаю все времена на {time_shift.total_seconds() / 60:.0f} мин, чтобы не приехать раньше окна")
        
        # Сдвигаем ВСЕ точки
        corrected_points = []
        for point in points:
            corrected_point = RoutePoint(
                order=point.order,
                estimated_arrival=point.estimated_arrival + time_shift,
                distance_from_previous=point.distance_from_previous,
                time_from_previous=point.time_from_previous
            )
            corrected_points.append(corrected_point)
        
        return corrected_points
    
    def _haversine_distance(self, lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """Расстояние между двумя точками по формуле Haversine (км)"""
        R = 6371  # Радиус Земли в км
        dlat = radians(lat2 - lat1)
        dlon = radians(lon2 - lon1)
        
        a = sin(dlat/2)**2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon/2)**2
        c = 2 * atan2(sqrt(a), sqrt(1-a))
        
        return R * c
