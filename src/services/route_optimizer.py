import logging
from typing import List, Tuple
from datetime import datetime, time, timedelta
import numpy as np
from ortools.constraint_solver import routing_enums_pb2
from ortools.constraint_solver import pywrapcp
from src.models.order import Order, RoutePoint, OptimizedRoute
from src.services.maps_service import MapsService

logger = logging.getLogger(__name__)


class RouteOptimizer:
    def __init__(self, maps_service: MapsService):
        self.maps_service = maps_service

    def optimize_route_sync(
        self,
        orders: List[Order],
        start_location: Tuple[float, float],  # (lat, lon)
        start_time: datetime,
        vehicle_capacity: int = 50
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
                lat, lon, gid = self.maps_service.geocode_address_sync(order.address)
                order.latitude = lat
                order.longitude = lon
                order.gis_id = gid
            geocoded_orders.append(order)

        # Calculate distance/time matrix
        locations = [start_location] + [(o.latitude, o.longitude) for o in geocoded_orders if o.latitude and o.longitude]
        distance_matrix, time_matrix = self._build_matrices(locations)

        # Create route optimization problem
        route_indices = self._solve_vrp(distance_matrix, time_matrix, geocoded_orders, start_time)

        # Build optimized route
        points = []
        current_time = start_time
        total_distance = 0
        total_time = 0

        for i, order_idx in enumerate(route_indices):
            if order_idx == 0:  # depot
                continue

            order = geocoded_orders[order_idx - 1]
            prev_location = locations[route_indices[i-1]] if i > 0 else start_location

            # Calculate travel time and distance to this point
            travel_distance = distance_matrix[route_indices[i-1]][order_idx]
            travel_time = time_matrix[route_indices[i-1]][order_idx]

            # Add delivery time
            from src.config import settings
            delivery_time = settings.delivery_time_per_stop
            estimated_arrival = current_time + timedelta(minutes=travel_time + delivery_time)

            # Check if arrival time fits within delivery time window
            if order.delivery_time_start and order.delivery_time_end:
                # Get delivery window in today's date
                today = start_time.date()
                window_start = datetime.combine(today, order.delivery_time_start)
                window_end = datetime.combine(today, order.delivery_time_end)

                # If estimated arrival is too early, adjust to start of window
                if estimated_arrival < window_start:
                    estimated_arrival = window_start
                    logger.warning(f"⚠️ Заказ №{order.order_number}: прибытие скорректировано до начала окна")

                # If estimated arrival is too late, this is a problem
                elif estimated_arrival > window_end:
                    logger.warning(f"🚨 Заказ №{order.order_number}: прибытие ({estimated_arrival.strftime('%H:%M')}) выходит за окно доставки!")

            # Update current time for next delivery
            current_time = estimated_arrival

            point = RoutePoint(
                order=order,
                estimated_arrival=estimated_arrival,
                distance_from_previous=travel_distance,
                time_from_previous=travel_time
            )
            points.append(point)

            total_distance += travel_distance
            total_time += travel_time + delivery_time

        return OptimizedRoute(
            points=points,
            total_distance=total_distance,
            total_time=total_time,
            estimated_completion=current_time
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

    def _solve_vrp(
        self,
        distance_matrix: np.ndarray,
        time_matrix: np.ndarray,
        orders: List[Order],
        start_time: datetime
    ) -> List[int]:
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

            # Add delivery time constraints (10 minutes per delivery)
            def delivery_time_callback(from_index, to_index):
                from_node = manager.IndexToNode(from_index)
                to_node = manager.IndexToNode(to_index)
                # Travel time + delivery time (except for depot)
                travel_time = int(time_matrix[from_node][to_node] * 60)  # seconds
                delivery_time = 10 * 60 if to_node > 0 else 0  # 10 minutes for deliveries
                return travel_time + delivery_time

            delivery_callback_index = routing.RegisterTransitCallback(delivery_time_callback)

            routing.AddDimension(
                delivery_callback_index,
                0,  # no slack
                24 * 60 * 60,  # max time in seconds (24 hours)
                False,  # don't fix start cumul to zero
                "Time"
            )
            time_dimension = routing.GetDimensionOrDie("Time")

            # Add time window constraints for each order
            for i, order in enumerate(orders):
                if order.delivery_time_start and order.delivery_time_end:
                    # Convert time windows to minutes from start of day
                    start_minutes = order.delivery_time_start.hour * 60 + order.delivery_time_start.minute
                    end_minutes = order.delivery_time_end.hour * 60 + order.delivery_time_end.minute

                    # Convert to seconds from start_time
                    start_seconds = start_minutes * 60
                    end_seconds = end_minutes * 60

                    # Add time window constraint for this order (node index i+1, depot is 0)
                    node_index = manager.NodeToIndex(i + 1)
                    time_dimension.CumulVar(node_index).SetRange(start_seconds, end_seconds)

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

            # Time limit for solving (30 seconds)
            search_parameters.time_limit.seconds = 30

            # Solution limit
            search_parameters.solution_limit = 100

            # Solve the problem
            solution = routing.SolveWithParameters(search_parameters)

            if solution:
                logger.info("✅ OR-Tools нашел оптимальное решение")
                route = []
                index = routing.Start(0)
                while not routing.IsEnd(index):
                    route.append(manager.IndexToNode(index))
                    index = solution.Value(routing.NextVar(index))
                route.append(manager.IndexToNode(index))
                return route
            else:
                logger.warning("⚠️ OR-Tools не нашел решение, используем fallback")
                # Fallback: return orders in original order
                return [0] + list(range(1, len(orders) + 1)) + [0]

        except Exception as e:
            logger.error(f"❌ Ошибка OR-Tools: {e}", exc_info=True)
            # Fallback: return orders in original order
            return [0] + list(range(1, len(orders) + 1)) + [0]
