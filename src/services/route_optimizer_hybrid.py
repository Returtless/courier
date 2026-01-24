"""
Гибридный оптимизатор маршрута с кластеризацией
"""
import logging
from typing import List, Tuple
from datetime import datetime, timedelta
from math import radians, sin, cos, sqrt, atan2
from collections import defaultdict

from src.models.order import Order, RoutePoint, OptimizedRoute
from src.services.maps_service import MapsService
from src.services.user_settings_service import UserSettingsService

logger = logging.getLogger(__name__)


class HybridRouteOptimizer:
    """Гибридный оптимизатор: временные окна → кластеризация → OR-Tools"""
    
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
        1. Группировка по временным окнам (ПРИОРИТЕТ!)
        2. Кластеризация по географии внутри каждой группы
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
        
        # Шаг 1: Группировка по временным окнам (ПРИОРИТЕТ!)
        time_groups = self._group_orders_by_time_windows(orders, start_time)
        logger.info(f"📅 Создано {len(time_groups)} временных групп")
        
        # Шаг 2: Внутри каждой временной группы - кластеризация по географии
        all_clusters = []
        for time_group in time_groups:
            group_clusters = self._cluster_orders_by_location(time_group, cluster_radius_km)
            all_clusters.extend(group_clusters)
        logger.info(f"📊 Создано {len(all_clusters)} географических кластеров (с учетом временных окон)")
        
        # Шаг 3: Оптимизация каждого кластера OR-Tools
        all_route_points = []
        total_distance = 0.0
        total_time = 0.0
        current_location = start_location
        current_time = start_time
        
        for cluster_idx, cluster in enumerate(all_clusters, 1):
            logger.info(f"🔧 Обрабатываю кластер {cluster_idx}/{len(all_clusters)} ({len(cluster)} заказов)")
            
            # ВАЖНО: Проверяем самое раннее временное окно в кластере и ждем до его начала
            earliest_window_start = None
            for order in cluster:
                if order.delivery_time_start:
                    order_date = start_time.date()
                    window_start = datetime.combine(order_date, order.delivery_time_start)
                    if earliest_window_start is None or window_start < earliest_window_start:
                        earliest_window_start = window_start
            
            # Если кластер имеет временное окно и мы приедем раньше - ЖДЕМ
            if earliest_window_start and current_time < earliest_window_start:
                wait_minutes = (earliest_window_start - current_time).total_seconds() / 60.0
                logger.info(f"   ⏰ Кластер начинается в {earliest_window_start.strftime('%H:%M')}, текущее время {current_time.strftime('%H:%M')}")
                logger.info(f"   ⌛ Ожидание {wait_minutes:.0f} мин до начала окна кластера")
                current_time = earliest_window_start
            
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
    
    def _group_orders_by_time_windows(
        self,
        orders: List[Order],
        start_time: datetime
    ) -> List[List[Order]]:
        """
        Группирует заказы по временным окнам.
        Заказы с одинаковыми окнами попадают в одну группу.
        ПРИОРИТЕТ ВРЕМЕНИ НАД ГЕОГРАФИЕЙ!
        
        Args:
            orders: Список заказов
            start_time: Время старта маршрута
            
        Returns:
            Список групп заказов с одинаковыми временными окнами
        """
        logger.info(f"📅 Группирую {len(orders)} заказов по временным окнам")
        
        # Группируем по временным окнам
        time_window_groups = defaultdict(list)
        no_window_orders = []
        
        for order in orders:
            if order.manual_arrival_time:
                # Заказы с ручным временем - в отдельные группы
                key = f"manual_{order.manual_arrival_time.strftime('%H:%M')}"
                time_window_groups[key].append(order)
            elif order.delivery_time_start and order.delivery_time_end:
                # Группируем по окну доставки
                key = f"{order.delivery_time_start.strftime('%H:%M')}-{order.delivery_time_end.strftime('%H:%M')}"
                time_window_groups[key].append(order)
            else:
                # Без окна - в конец
                no_window_orders.append(order)
        
        # Сортируем группы по времени начала окна
        def get_group_start_time(item):
            key, group_orders = item
            if key.startswith("manual_"):
                # Ручное время
                return datetime.combine(start_time.date(), group_orders[0].manual_arrival_time.time())
            else:
                # Временное окно
                return datetime.combine(start_time.date(), group_orders[0].delivery_time_start)
        
        sorted_groups = sorted(time_window_groups.items(), key=get_group_start_time)
        
        # Формируем результат: сначала группы с окнами, потом без окон
        result = [group for key, group in sorted_groups]
        if no_window_orders:
            result.append(no_window_orders)
        
        # Логируем группы
        for i, group in enumerate(result, 1):
            first_order = group[0]
            if first_order.manual_arrival_time:
                time_info = f"ручное время {first_order.manual_arrival_time.strftime('%H:%M')}"
            elif first_order.delivery_time_start and first_order.delivery_time_end:
                time_info = f"окно {first_order.delivery_time_start.strftime('%H:%M')}-{first_order.delivery_time_end.strftime('%H:%M')}"
            else:
                time_info = "без ограничений"
            
            logger.info(f"   {i}. Группа с {len(group)} заказами: {time_info}")
        
        return result
    
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
