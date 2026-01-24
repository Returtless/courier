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
        cluster_radius_km: float = 3.0
    ) -> OptimizedRoute:
        """
        ГИБРИДНАЯ оптимизация маршрута:
        1. Кластеризация по географии (БЕЗ учёта времени!)
        2. Упорядочивание кластеров по временным окнам
        3. OR-Tools оптимизация внутри каждого кластера
        4. Сборка итогового маршрута
        
        Args:
            orders: Список заказов
            start_location: Точка старта (lat, lon)
            start_time: Время старта
            user_id: ID пользователя
            cluster_radius_km: Радиус кластера (км)
            
        Returns:
            Оптимизированный маршрут
        """
        if not orders:
            return OptimizedRoute(points=[], total_distance=0, total_time=0, estimated_completion=start_time)
        
        logger.info(f"🎯 ГИБРИДНАЯ ОПТИМИЗАЦИЯ: {len(orders)} заказов, радиус кластера {cluster_radius_km} км")
        
        # Определяем реальное время старта - начало самого раннего окна
        earliest_window = None
        for order in orders:
            if order.delivery_time_start:
                order_date = start_time.date()
                window_start = datetime.combine(order_date, order.delivery_time_start)
                if earliest_window is None or window_start < earliest_window:
                    earliest_window = window_start
        
        if earliest_window and earliest_window > start_time:
            start_time = earliest_window
            logger.info(f"⏰ Устанавливаю время старта на начало первого окна: {start_time.strftime('%H:%M')}")
        
        # Шаг 1: Кластеризация по географии (БЕЗ учёта времени!)
        all_clusters = self._cluster_orders_by_location(orders, cluster_radius_km)
        logger.info(f"📊 Создано {len(all_clusters)} географических кластеров")
        
        # Шаг 2: Упорядочивание кластеров по временным окнам
        ordered_clusters = self._order_clusters_by_time_windows(all_clusters, start_time)
        logger.info(f"📅 Кластеры упорядочены по временным окнам")
        
        # Шаг 3: Оптимизация каждого кластера OR-Tools
        all_route_points = []
        total_distance = 0.0
        total_time = 0.0
        current_location = start_location
        current_time = start_time
        
        for cluster_idx, cluster in enumerate(ordered_clusters, 1):
            logger.info(f"🔧 Обрабатываю кластер {cluster_idx}/{len(ordered_clusters)} ({len(cluster)} заказов)")
            
            # НЕ ждем до начала окна кластера - начинаем сразу
            # Каждый заказ будет проверен индивидуально внутри OR-Tools или при добавлении
            
            if len(cluster) == 1:
                # Один заказ - просто добавляем
                order = cluster[0]
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
                logger.info(f"   🔍 OR-Tools оптимизация {len(cluster)} заказов в кластере")
                
                # Оптимизируем кластер от текущей позиции
                cluster_route = self.route_optimizer.optimize_route_sync(
                    orders=cluster,
                    start_location=current_location,
                    start_time=current_time,
                    user_id=user_id,
                    use_fallback=True
                )
                
                if cluster_route and cluster_route.points:
                    # Добавляем точки из кластера
                    for point in cluster_route.points:
                        all_route_points.append(point)
                    
                    # Обновляем текущие параметры
                    last_point = cluster_route.points[-1]
                    current_location = (last_point.order.latitude, last_point.order.longitude)
                    current_time = cluster_route.estimated_completion
                    
                    # Добавляем расстояние и время кластера
                    total_distance += cluster_route.total_distance
                    total_time += cluster_route.total_time
                    
                    logger.info(f"   ✅ Кластер обработан: {len(cluster_route.points)} точек")
                else:
                    logger.warning(f"   ⚠️ OR-Tools не смог оптимизировать кластер, пропускаем")
        
        logger.info(f"✅ ГИБРИДНАЯ ОПТИМИЗАЦИЯ ЗАВЕРШЕНА: {len(all_route_points)} точек, {total_distance:.1f} км, {total_time:.0f} мин")
        
        return OptimizedRoute(
            points=all_route_points,
            total_distance=total_distance,
            total_time=total_time,
            estimated_completion=current_time
        )
    
    def _order_clusters_by_time_windows(
        self,
        clusters: List[List[Order]],
        start_time: datetime
    ) -> List[List[Order]]:
        """
        Упорядочивает географические кластеры по временным окнам.
        Кластеры с более ранними окнами идут первыми.
        
        Args:
            clusters: Список географических кластеров
            start_time: Время старта маршрута
            
        Returns:
            Отсортированные кластеры
        """
        logger.info(f"📅 Упорядочиваю {len(clusters)} кластеров по временным окнам")
        
        def get_cluster_priority(cluster: List[Order]) -> tuple:
            """
            Возвращает приоритет кластера для сортировки.
            (priority_type, earliest_time, latest_time)
            """
            earliest_start = None
            latest_end = None
            has_manual_time = False
            earliest_manual = None
            
            for order in cluster:
                # Приоритет 1: ручное время прибытия
                if order.manual_arrival_time:
                    has_manual_time = True
                    if earliest_manual is None or order.manual_arrival_time < earliest_manual:
                        earliest_manual = order.manual_arrival_time
                
                # Приоритет 2: временное окно
                if order.delivery_time_start and order.delivery_time_end:
                    order_date = start_time.date()
                    window_start = datetime.combine(order_date, order.delivery_time_start)
                    window_end = datetime.combine(order_date, order.delivery_time_end)
                    
                    if earliest_start is None or window_start < earliest_start:
                        earliest_start = window_start
                    if latest_end is None or window_end > latest_end:
                        latest_end = window_end
            
            # Формируем ключ сортировки
            if has_manual_time and earliest_manual:
                return (0, earliest_manual, earliest_manual)
            elif earliest_start:
                return (1, earliest_start, latest_end or datetime.max)
            else:
                return (2, datetime.max, datetime.max)
        
        # Сортируем кластеры
        sorted_clusters = sorted(clusters, key=get_cluster_priority)
        
        # Логируем порядок
        for i, cluster in enumerate(sorted_clusters, 1):
            priority = get_cluster_priority(cluster)
            if priority[0] == 0:
                time_info = f"ручное время {priority[1].strftime('%H:%M')}"
            elif priority[0] == 1:
                time_info = f"окно {priority[1].strftime('%H:%M')}-{priority[2].strftime('%H:%M')}"
            else:
                time_info = "без ограничений"
            
            logger.info(f"   {i}. Кластер с {len(cluster)} заказами: {time_info}")
        
        return sorted_clusters
    
    def _cluster_orders_by_location(
        self,
        orders: List[Order],
        max_distance_km: float = 3.0
    ) -> List[List[Order]]:
        """
        Кластеризация заказов по географической близости.
        Использует простой алгоритм группировки по расстоянию.
        
        Args:
            orders: Список заказов
            max_distance_km: Максимальное расстояние для одного кластера (км)
            
        Returns:
            Список кластеров (каждый кластер - список заказов)
        """
        if not orders:
            return []
        
        logger.info(f"🗂️ Начинаю кластеризацию {len(orders)} заказов (макс. радиус {max_distance_km} км)")
        
        # Фильтруем заказы с координатами
        orders_with_coords = [o for o in orders if o.latitude and o.longitude]
        orders_without_coords = [o for o in orders if not o.latitude or not o.longitude]
        
        if orders_without_coords:
            logger.warning(f"⚠️ {len(orders_without_coords)} заказов без координат будут в отдельном кластере")
        
        if not orders_with_coords:
            return [[o] for o in orders_without_coords]  # Каждый в своем кластере
        
        # Простая кластеризация: greedy approach
        clusters = []
        remaining = orders_with_coords.copy()
        
        while remaining:
            # Начинаем новый кластер с первого оставшегося заказа
            seed = remaining.pop(0)
            cluster = [seed]
            
            # Ищем близкие заказы
            i = 0
            while i < len(remaining):
                order = remaining[i]
                
                # Проверяем расстояние до ЛЮБОЙ точки в текущем кластере
                min_distance = float('inf')
                for cluster_order in cluster:
                    distance = self._haversine_distance(
                        cluster_order.latitude, cluster_order.longitude,
                        order.latitude, order.longitude
                    )
                    min_distance = min(min_distance, distance)
                
                # Если близко - добавляем в кластер
                if min_distance <= max_distance_km:
                    cluster.append(order)
                    remaining.pop(i)
                else:
                    i += 1
            
            clusters.append(cluster)
            logger.info(f"   📍 Кластер {len(clusters)}: {len(cluster)} заказов (центр: {seed.address[:50]}...)")
        
        # Добавляем заказы без координат в отдельные кластеры
        for order in orders_without_coords:
            clusters.append([order])
        
        logger.info(f"✅ Создано {len(clusters)} кластеров")
        return clusters
    
    def _haversine_distance(self, lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """Расстояние между двумя точками по формуле Haversine (км)"""
        R = 6371  # Радиус Земли в км
        dlat = radians(lat2 - lat1)
        dlon = radians(lon2 - lon1)
        
        a = sin(dlat/2)**2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon/2)**2
        c = 2 * atan2(sqrt(a), sqrt(1-a))
        
        return R * c
