import logging
from typing import List, Tuple
from datetime import datetime, time, timedelta
import numpy as np
from ortools.constraint_solver import routing_enums_pb2
from ortools.constraint_solver import pywrapcp
from src.models.order import Order, RoutePoint, OptimizedRoute
from src.services.maps_service import MapsService
from src.services.user_settings_service import UserSettingsService

logger = logging.getLogger(__name__)


class RouteOptimizer:
    def __init__(self, maps_service: MapsService):
        self.maps_service = maps_service
        self.settings_service = UserSettingsService()

    def optimize_route_sync(
        self,
        orders: List[Order],
        start_location: Tuple[float, float],  # (lat, lon)
        start_time: datetime,
        vehicle_capacity: int = 50,
        user_id: int = None,  # Добавляем user_id для получения настроек
        use_fallback: bool = False  # Использовать fallback при ошибке OR-Tools (только после подтверждения пользователя)
    ) -> OptimizedRoute:
        """
        Оптимизировать маршрут для списка заказов
        """
        if not orders:
            return OptimizedRoute(points=[], total_distance=0, total_time=0, estimated_completion=start_time)

        # Geocode addresses if needed (используем координаты из БД, если они есть)
        geocoded_orders = []
        for order in orders:
            if order.latitude is None or order.longitude is None:
                # Только если координат нет - делаем геокодирование (с кэшированием)
                # Проверяем, что адрес не пустой
                if order.address and order.address.strip():
                    lat, lon, gid = self.maps_service.geocode_address_sync(order.address)
                    order.latitude = lat
                    order.longitude = lon
                    order.gis_id = gid
                else:
                    logger.warning(f"⚠️ Заказ {order.order_number} не может быть загеокодирован: адрес отсутствует")
            geocoded_orders.append(order)

        # Calculate distance/time matrix
        # Фильтруем заказы с координатами (без координат нельзя построить маршрут)
        orders_with_coords = [o for o in geocoded_orders if o.latitude and o.longitude]
        orders_without_coords = [o for o in geocoded_orders if not o.latitude or not o.longitude]
        
        if orders_without_coords:
            logger.warning(f"⚠️ {len(orders_without_coords)} заказов без координат будут исключены из маршрута: {[o.order_number for o in orders_without_coords]}")
        
        if not orders_with_coords:
            logger.error("❌ Нет заказов с координатами для построения маршрута")
            return OptimizedRoute(points=[], total_distance=0, total_time=0, estimated_completion=start_time)
        
        locations = [start_location] + [(o.latitude, o.longitude) for o in orders_with_coords]
        distance_matrix, time_matrix = self._build_matrices(locations)

        # Create route optimization problem
        # Используем только заказы с координатами для оптимизации
        route_result = self._solve_vrp(distance_matrix, time_matrix, orders_with_coords, start_time, user_id)
        
        if not route_result:
            logger.error("❌ Не удалось найти решение задачи маршрутизации")
            # ВСЕГДА используем fallback если OR-Tools не нашел решение (даже если use_fallback=False)
            # Fallback создаст рабочий маршрут, игнорируя ручные времена и жесткие окна
            logger.warning(f"⚠️ Используем fallback: простой порядок заказов с расчетом времени для {len(orders_with_coords)} заказов")
            try:
                fallback_result = self._build_fallback_route(orders_with_coords, start_location, start_time, user_id)
                if not fallback_result or not fallback_result.points:
                    logger.error(f"❌ КРИТИЧНО: Fallback тоже не создал маршрут! Заказов с координатами: {len(orders_with_coords)}")
                    # Диагностика: проверяем координаты заказов
                    for order in orders_with_coords:
                        logger.error(f"   📦 Заказ {order.order_number}: lat={order.latitude}, lon={order.longitude}")
                    return OptimizedRoute(points=[], total_distance=0, total_time=0, estimated_completion=start_time)
                logger.info(f"✅ Fallback успешно создал маршрут с {len(fallback_result.points)} точками")
                return fallback_result
            except Exception as e:
                import traceback
                logger.error(f"❌ КРИТИЧЕСКАЯ ОШИБКА в fallback: {e}\n{traceback.format_exc()}")
                return OptimizedRoute(points=[], total_distance=0, total_time=0, estimated_completion=start_time)
        
        route_indices, solution, routing, manager, time_dimension = route_result

        # Build optimized route используя решение OR-Tools
        # Получаем настройки пользователя для времени обслуживания
        service_time_minutes = 10  # Значение по умолчанию
        if user_id:
            user_settings = self.settings_service.get_settings(user_id)
            service_time_minutes = user_settings.service_time_minutes
        
        points = []
        total_distance = 0
        total_time = 0
        last_arrival_time = start_time

        for i, order_idx in enumerate(route_indices):
            if order_idx == 0:  # depot
                continue

            order = orders_with_coords[order_idx - 1]
            
            # Получаем время прибытия ИЗ РЕШЕНИЯ OR-Tools (а не пересчитываем)
            # order_idx - это индекс в locations (0 = depot, 1+ = заказы)
            # В OR-Tools node_index для заказа = order_idx (так как depot = 0, заказы = 1..n)
            node_index = manager.NodeToIndex(order_idx)
            cumul_value = solution.Value(time_dimension.CumulVar(node_index))
            estimated_arrival = start_time + timedelta(seconds=cumul_value)
            
            # Calculate travel time and distance to this point
            prev_idx = route_indices[i-1] if i > 0 else 0
            travel_distance = distance_matrix[prev_idx][order_idx]
            travel_time = time_matrix[prev_idx][order_idx]

            # Add service time AFTER arrival (time spent at the location)
            service_completion = estimated_arrival + timedelta(minutes=service_time_minutes)
            
            # Calculate actual time spent from previous point
            if i > 0 and route_indices[i-1] != 0:
                prev_order_idx = route_indices[i-1]
                prev_node_index = manager.NodeToIndex(prev_order_idx)
                prev_cumul_value = solution.Value(time_dimension.CumulVar(prev_node_index))
                prev_arrival = start_time + timedelta(seconds=prev_cumul_value)
                prev_service_completion = prev_arrival + timedelta(minutes=service_time_minutes)
                actual_time_spent = (service_completion - prev_service_completion).total_seconds() / 60.0
            else:
                # First order: time from start
                actual_time_spent = (service_completion - start_time).total_seconds() / 60.0
            
            point = RoutePoint(
                order=order,
                estimated_arrival=estimated_arrival,
                distance_from_previous=travel_distance,
                time_from_previous=travel_time
            )
            points.append(point)

            total_distance += travel_distance
            total_time += actual_time_spent
            last_arrival_time = service_completion

        return OptimizedRoute(
            points=points,
            total_distance=total_distance,
            total_time=total_time,
            estimated_completion=last_arrival_time
        )

    def _build_matrices(self, locations: List[Tuple[float, float]]) -> Tuple[np.ndarray, np.ndarray]:
        """Build distance and time matrices between all locations"""
        n = len(locations)
        distance_matrix = np.zeros((n, n))
        time_matrix = np.zeros((n, n))

        for i in range(n):
            for j in range(n):
                if i != j:
                    dist, time_min = self.maps_service.get_route_sync(
                        locations[i][0], locations[i][1],
                        locations[j][0], locations[j][1]
                    )
                    distance_matrix[i][j] = dist
                    time_matrix[i][j] = time_min
                else:
                    distance_matrix[i][j] = 0
                    time_matrix[i][j] = 0

        return distance_matrix, time_matrix

    def _build_fallback_route(
        self,
        orders: List[Order],
        start_location: Tuple[float, float],
        start_time: datetime,
        user_id: int = None
    ) -> OptimizedRoute:
        """
        Создает простой маршрут в порядке заказов с расчетом времени (fallback).
        ВАЖНО: НЕ использует ручные времена - только автоматический расчет.
        Ручные времена должны быть уже удалены из call_status перед вызовом этого метода.
        """
        if not orders:
            return OptimizedRoute(points=[], total_distance=0, total_time=0, estimated_completion=start_time)
        
        # Получаем настройки пользователя
        service_time_minutes = 10
        if user_id:
            user_settings = self.settings_service.get_settings(user_id)
            service_time_minutes = user_settings.service_time_minutes
        
        # Сортируем заказы ТОЛЬКО по окну доставки (БЕЗ учета ручных времен)
        def sort_key(order: Order):
            if order.delivery_time_start:
                return (0, datetime.combine(start_time.date(), order.delivery_time_start))
            else:
                return (1, datetime.max)
        
        sorted_orders = sorted(orders, key=sort_key)
        
        # Строим маршрут последовательно
        route_points = []
        current_time = start_time
        current_location = start_location
        total_distance = 0.0
        total_time = 0.0
        
        logger.info(f"🔧 Fallback: начинаю построение маршрута для {len(sorted_orders)} заказов")
        logger.info(f"   📍 Точка старта: ({start_location[0]}, {start_location[1]})")
        logger.info(f"   🕐 Время старта: {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
        
        skipped_orders = []
        for idx, order in enumerate(sorted_orders):
            if not order.latitude or not order.longitude:
                logger.warning(f"⚠️ [{idx+1}/{len(sorted_orders)}] Пропускаем заказ {order.order_number}: нет координат (lat={order.latitude}, lon={order.longitude})")
                skipped_orders.append(order.order_number)
                continue
            
            logger.info(f"🔧 [{idx+1}/{len(sorted_orders)}] Fallback: обрабатываю заказ {order.order_number}, координаты: ({order.latitude}, {order.longitude})")
            
            # Рассчитываем время до заказа
            try:
                distance_km, time_min = self.maps_service.get_route_sync(
                    current_location[0], current_location[1],
                    order.latitude, order.longitude
                )
                logger.info(f"   ✅ Расстояние до {order.order_number}: {distance_km:.2f} км, время: {time_min:.1f} мин")
            except Exception as e:
                import traceback
                logger.error(f"❌ Ошибка расчета маршрута до заказа {order.order_number}: {e}")
                logger.error(f"   Traceback: {traceback.format_exc()}")
                skipped_orders.append(order.order_number)
                continue
            
            # Время прибытия: текущее время + время в пути (АВТОМАТИЧЕСКИЙ расчет)
            arrival_time = current_time + timedelta(minutes=time_min)
            
            # НЕ используем ручное время - только автоматический расчет!
            # Если есть окно доставки - проверяем, не раньше ли мы приезжаем
            if order.delivery_time_start:
                window_start = datetime.combine(start_time.date(), order.delivery_time_start)
                if arrival_time < window_start:
                    arrival_time = window_start
            
            # Время на точке
            service_time = timedelta(minutes=service_time_minutes)
            departure_time = arrival_time + service_time
            
            # Создаем точку маршрута
            route_point = RoutePoint(
                order=order,
                estimated_arrival=arrival_time,
                distance_from_previous=distance_km,
                time_from_previous=time_min
            )
            route_points.append(route_point)
            
            # Обновляем текущее состояние
            total_distance += distance_km
            total_time += time_min + service_time_minutes
            current_time = departure_time
            current_location = (order.latitude, order.longitude)
        
        estimated_completion = current_time if route_points else start_time
        
        if skipped_orders:
            logger.warning(f"⚠️ Fallback: пропущено {len(skipped_orders)} заказов без координат/с ошибками: {skipped_orders}")
        
        if not route_points:
            logger.error(f"❌ КРИТИЧНО: Fallback не создал ни одной точки маршрута!")
            logger.error(f"   - Всего заказов: {len(sorted_orders)}")
            logger.error(f"   - Пропущено: {len(skipped_orders)}")
            logger.error(f"   - Обработано успешно: {len(route_points)}")
            # Диагностика: проверяем почему все заказы пропущены
            for order in sorted_orders:
                logger.error(f"   📦 Заказ {order.order_number}: lat={order.latitude}, lon={order.longitude}, адрес='{order.address}'")
        else:
            logger.info(f"✅ Fallback маршрут создан (БЕЗ ручных времен): {len(route_points)} точек, расстояние {total_distance:.1f} км, время {total_time:.0f} мин")
            logger.info(f"   🕐 Завершение маршрута: {estimated_completion.strftime('%H:%M:%S')}")
        
        return OptimizedRoute(
            points=route_points,
            total_distance=total_distance,
            total_time=total_time,
            estimated_completion=estimated_completion
        )

    def _solve_vrp(
        self,
        distance_matrix: np.ndarray,
        time_matrix: np.ndarray,
        orders: List[Order],
        start_time: datetime,
        user_id: int = None
    ) -> tuple:
        """Solve Vehicle Routing Problem using OR-Tools with advanced optimization"""
        try:
            manager = pywrapcp.RoutingIndexManager(len(distance_matrix), 1, 0)  # 1 vehicle, depot at 0
            routing = pywrapcp.RoutingModel(manager)

            def distance_callback(from_index, to_index):
                from_node = manager.IndexToNode(from_index)
                to_node = manager.IndexToNode(to_index)
                return int(distance_matrix[from_node][to_node] * 1000)  # Convert to meters

            transit_callback_index = routing.RegisterTransitCallback(distance_callback)
            routing.SetArcCostEvaluatorOfAllVehicles(transit_callback_index)

            # Add delivery time constraints (используем настройку пользователя)
            service_time_minutes = 10  # Значение по умолчанию
            if user_id:
                user_settings = self.settings_service.get_settings(user_id)
                service_time_minutes = user_settings.service_time_minutes
            
            def delivery_time_callback(from_index, to_index):
                from_node = manager.IndexToNode(from_index)
                to_node = manager.IndexToNode(to_index)
                # Travel time + delivery time (except for depot)
                travel_time = int(time_matrix[from_node][to_node] * 60)  # seconds
                delivery_time = service_time_minutes * 60 if to_node > 0 else 0  # minutes -> seconds
                return travel_time + delivery_time

            delivery_callback_index = routing.RegisterTransitCallback(delivery_time_callback)

            # Временная размерность: время считается в секундах ОТ МОМЕНТА СТАРТА маршрута.
            # Стартовая точка (депо) фиксируется в 0, все окна/ручные времена считаются как offset от start_time.
            routing.AddDimension(
                delivery_callback_index,
                0,  # no slack
                24 * 60 * 60,  # max time in seconds (24 hours)
                True,  # fix start cumul to zero (t=0 на старте маршрута)
                "Time"
            )
            time_dimension = routing.GetDimensionOrDie("Time")

            # Логируем время старта для диагностики
            logger.info(f"🕐 Время старта маршрута: {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
            
            # Add time window constraints for each order
            for i, order in enumerate(orders):
                node_index = manager.NodeToIndex(i + 1)
                
                # DEBUG: Логируем manual_arrival_time для всех заказов
                logger.info(f"📝 Заказ №{order.order_number}: manual_arrival_time = {order.manual_arrival_time}")
                
                # Вычисляем ограничения для окна доставки (если есть)
                window_start_seconds = None
                window_end_seconds = None
                if order.delivery_time_start and order.delivery_time_end:
                    order_date = start_time.date()
                    window_start_dt = datetime.combine(order_date, order.delivery_time_start)
                    window_end_dt = datetime.combine(order_date, order.delivery_time_end)
                    window_start_seconds = max(0, int((window_start_dt - start_time).total_seconds()))
                    window_end_seconds = max(window_start_seconds, int((window_end_dt - start_time).total_seconds()))
                    # Добавляем буфер ±5 минут для гибкости
                    buffer_seconds = 5 * 60
                    window_start_seconds = max(0, window_start_seconds - buffer_seconds)
                    window_end_seconds = window_end_seconds + buffer_seconds
                
                # Приоритет 1: Ручное время прибытия (жесткое ограничение)
                if order.manual_arrival_time:
                    # Если установлено ручное время прибытия - это фиксированная точка
                    # Вычисляем секунды ОТ МОМЕНТА СТАРТА маршрута до manual_arrival_time
                    time_diff = (order.manual_arrival_time - start_time).total_seconds()
                    if time_diff < 0:
                        # Если ручное время раньше старта маршрута - фиксируем на старте
                        logger.warning(
                            f"⚠️ Ручное время прибытия для заказа {order.order_number} ({order.manual_arrival_time}) "
                            f"раньше времени старта маршрута ({start_time}) – фиксируем на t=0"
                        )
                        time_diff = 0

                    # Увеличиваем tolerance до ±30 минут для возможности решения
                    tolerance_seconds = 30 * 60
                    arrival_seconds_min = max(0, int(time_diff - tolerance_seconds))
                    arrival_seconds_max = max(arrival_seconds_min, int(time_diff + tolerance_seconds))
                    
                    # Если есть окно доставки - используем пересечение ограничений
                    if window_start_seconds is not None and window_end_seconds is not None:
                        # Пересечение: ручное время должно быть в пределах окна (с учетом tolerance)
                        arrival_seconds_min = max(arrival_seconds_min, window_start_seconds)
                        arrival_seconds_max = min(arrival_seconds_max, window_end_seconds)
                        
                        if arrival_seconds_min > arrival_seconds_max:
                            # Конфликт: ручное время вне окна доставки
                            logger.warning(
                                f"⚠️ Конфликт: ручное время {order.manual_arrival_time.strftime('%H:%M')} "
                                f"не попадает в окно доставки {order.delivery_time_start.strftime('%H:%M')}-{order.delivery_time_end.strftime('%H:%M')}. "
                                f"Расширяем диапазон для поиска решения."
                            )
                            # Расширяем диапазон, чтобы включить оба ограничения
                            arrival_seconds_min = min(int(time_diff - tolerance_seconds), window_start_seconds)
                            arrival_seconds_max = max(int(time_diff + tolerance_seconds), window_end_seconds)

                    # Используем вычисленный диапазон
                    time_dimension.CumulVar(node_index).SetRange(arrival_seconds_min, arrival_seconds_max)
                    
                    # Добавляем мягкое ограничение с большим штрафом за отклонение
                    soft_penalty = 10000  # Большой штраф за отклонение от целевого времени
                    time_dimension.SetCumulVarSoftLowerBound(
                        node_index,
                        int(time_diff),
                        soft_penalty
                    )
                    time_dimension.SetCumulVarSoftUpperBound(
                        node_index,
                        int(time_diff),
                        soft_penalty
                    )
                    logger.info(
                        f"🔒 Заказ №{order.order_number}: фиксированное время прибытия "
                        f"{order.manual_arrival_time.strftime('%H:%M')} (диапазон ±30 мин, "
                        f"от {arrival_seconds_min}s до {arrival_seconds_max}s от старта, "
                        f"время старта: {start_time.strftime('%H:%M')})"
                    )
                
                # Приоритет 2: Временное окно доставки (если нет ручного времени)
                elif window_start_seconds is not None and window_end_seconds is not None:
                    # Используем уже вычисленные значения window_start_seconds и window_end_seconds
                    time_dimension.CumulVar(node_index).SetRange(window_start_seconds, window_end_seconds)
                    
                    # Мягкая цель: стремимся к началу окна (чтобы минимизировать ожидание)
                    # Но с большим штрафом за выход за пределы основного окна
                    order_date = start_time.date()
                    window_start_dt = datetime.combine(order_date, order.delivery_time_start)
                    window_end_dt = datetime.combine(order_date, order.delivery_time_end)
                    start_seconds = max(0, int((window_start_dt - start_time).total_seconds()))
                    end_seconds = max(start_seconds, int((window_end_dt - start_time).total_seconds()))
                    
                    early_penalty_per_minute = 1000  # небольшой штраф за раннее прибытие
                    early_penalty_per_second = early_penalty_per_minute / 60.0
                    time_dimension.SetCumulVarSoftLowerBound(
                        node_index,
                        int(start_seconds),
                        int(early_penalty_per_second)
                    )
                    
                    # Штраф за выход за верхнюю границу окна
                    late_penalty_per_minute = 2000  # больший штраф за опоздание
                    late_penalty_per_second = late_penalty_per_minute / 60.0
                    time_dimension.SetCumulVarSoftUpperBound(
                        node_index,
                        int(end_seconds),
                        int(late_penalty_per_second)
                    )
                    
                    logger.info(
                        f"📅 Заказ №{order.order_number}: ЖЕСТКОЕ окно доставки "
                        f"{order.delivery_time_start.strftime('%H:%M')}-{order.delivery_time_end.strftime('%H:%M')} "
                        f"(от {window_start_seconds}s до {window_end_seconds}s от старта, "
                        f"основное окно: {start_seconds}s-{end_seconds}s)"
                    )

            # Set advanced search parameters
            search_parameters = pywrapcp.DefaultRoutingSearchParameters()

            # First solution strategy - try different approaches
            search_parameters.first_solution_strategy = (
                routing_enums_pb2.FirstSolutionStrategy.AUTOMATIC
            )

            # Local search metaheuristic for optimization
            search_parameters.local_search_metaheuristic = (
                routing_enums_pb2.LocalSearchMetaheuristic.AUTOMATIC
            )

            # Time limit for solving (60 seconds) - увеличиваем для сложных задач
            search_parameters.time_limit.seconds = 60

            # Solution limit - увеличиваем для поиска большего количества решений
            search_parameters.solution_limit = 500
            
            # Добавляем больше стратегий поиска для сложных задач
            search_parameters.use_full_propagation = True

            # Solve the problem
            logger.info(f"🔍 Начинаем решение задачи маршрутизации для {len(orders)} заказов...")
            logger.debug(f"   - Матрица расстояний: {len(distance_matrix)}x{len(distance_matrix)}")
            logger.debug(f"   - Матрица времени: {len(time_matrix)}x{len(time_matrix)}")
            logger.debug(f"   - Лимит времени решения: {search_parameters.time_limit.seconds} сек")
            
            solution = routing.SolveWithParameters(search_parameters)

            if solution:
                logger.info("✅ OR-Tools нашел оптимальное решение")
                
                # Проверяем качество решения и соблюдение ограничений
                time_dimension = routing.GetDimensionOrDie("Time")
                violations = []
                for i, order in enumerate(orders):
                    node_index = manager.NodeToIndex(i + 1)
                    cumul_value = solution.Value(time_dimension.CumulVar(node_index))
                    arrival_time = start_time + timedelta(seconds=cumul_value)
                    
                    # Проверяем окна доставки
                    if order.delivery_time_start and order.delivery_time_end:
                        order_date = start_time.date()
                        window_start = datetime.combine(order_date, order.delivery_time_start)
                        window_end = datetime.combine(order_date, order.delivery_time_end)
                        
                        if arrival_time < window_start:
                            wait_minutes = (window_start - arrival_time).total_seconds() / 60.0
                            logger.info(
                                f"⏳ Заказ {order.order_number}: прибытие {arrival_time.strftime('%H:%M')} "
                                f"раньше окна {window_start.strftime('%H:%M')} (ожидание {wait_minutes:.1f} мин)"
                            )
                        elif arrival_time > window_end:
                            late_minutes = (arrival_time - window_end).total_seconds() / 60.0
                            violations.append(f"Заказ {order.order_number}: опоздание на {late_minutes:.1f} мин")
                            logger.error(
                                f"🚨 КРИТИЧНО: Заказ {order.order_number}: прибытие {arrival_time.strftime('%H:%M')} "
                                f"ПОЗЖЕ окна {window_end.strftime('%H:%M')} (опоздание {late_minutes:.1f} мин)"
                            )
                    
                    # Проверяем ручное время прибытия
                    if order.manual_arrival_time:
                        tolerance = timedelta(minutes=5)
                        if abs(arrival_time - order.manual_arrival_time) > tolerance:
                            diff_minutes = abs((arrival_time - order.manual_arrival_time).total_seconds() / 60.0)
                            logger.warning(
                                f"⚠️ Заказ {order.order_number}: прибытие {arrival_time.strftime('%H:%M')} "
                                f"отличается от ручного времени {order.manual_arrival_time.strftime('%H:%M')} "
                                f"на {diff_minutes:.1f} мин"
                            )
                
                if violations:
                    logger.error(f"❌ OR-Tools нарушил ограничения: {', '.join(violations)}")
                
                route = []
                index = routing.Start(0)
                while not routing.IsEnd(index):
                    route.append(manager.IndexToNode(index))
                    index = solution.Value(routing.NextVar(index))
                route.append(manager.IndexToNode(index))
                
                # Возвращаем route_indices, solution, routing, manager, time_dimension
                return (route, solution, routing, manager, time_dimension)
            else:
                logger.error("❌ OR-Tools не смог найти решение с заданными ограничениями!")
                logger.warning("⚠️ Возможен конфликт между ручными временами и окнами доставки")
                
                # Логируем все ограничения для диагностики
                logger.info("📋 Диагностика ограничений:")
                logger.info(f"   🕐 Время старта: {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
                logger.info(f"   📊 Количество заказов: {len(orders)}")
                logger.info(f"   ⏱️ Лимит времени решения: {search_parameters.time_limit.seconds} сек")
                
                try:
                    time_dimension = routing.GetDimensionOrDie("Time")
                    for i, order in enumerate(orders):
                        try:
                            node_index = manager.NodeToIndex(i + 1)
                            time_var = time_dimension.CumulVar(node_index)
                            min_seconds = time_var.Min()
                            max_seconds = time_var.Max()
                            min_time = (start_time + timedelta(seconds=min_seconds)).strftime('%H:%M')
                            max_time = (start_time + timedelta(seconds=max_seconds)).strftime('%H:%M')
                            
                            logger.info(f"   📦 Заказ #{order.order_number}:")
                            logger.info(f"      - Окно: {min_seconds}s - {max_seconds}s ({min_time} - {max_time})")
                            if order.delivery_time_start and order.delivery_time_end:
                                logger.info(f"      - Окно доставки: {order.delivery_time_start.strftime('%H:%M')} - {order.delivery_time_end.strftime('%H:%M')}")
                            if order.manual_arrival_time:
                                manual_seconds = int((order.manual_arrival_time - start_time).total_seconds())
                                logger.info(f"      - Ручное время: {order.manual_arrival_time.strftime('%H:%M')} ({manual_seconds}s от старта)")
                                if manual_seconds < min_seconds or manual_seconds > max_seconds:
                                    logger.error(f"      ⚠️ КОНФЛИКТ: Ручное время {manual_seconds}s вне допустимого окна [{min_seconds}s, {max_seconds}s]")
                        except Exception as e:
                            logger.warning(f"   ⚠️ Ошибка при проверке заказа #{order.order_number}: {e}")
                except Exception as e:
                    logger.error(f"   ❌ Ошибка при диагностике ограничений: {e}")
                
                logger.warning("⚠️ OR-Tools не нашел решение, будет использован fallback")
                # Fallback: return None (будет обработано в optimize_route_sync)
                return None

        except Exception as e:
            logger.error(f"❌ Ошибка OR-Tools: {e}", exc_info=True)
            # Fallback: return None
            return None
