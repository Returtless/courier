"""
Генетический алгоритм оптимизации маршрутов
Использует эволюционный подход для построения оптимальных маршрутов с учетом временных окон
"""
import itertools
import logging
import random
from typing import List, Tuple, Optional, Dict
from datetime import datetime, time, timedelta
from math import radians, sin, cos, sqrt, atan2

from src.models.order import Order, RoutePoint, OptimizedRoute
from src.services.maps_service import MapsService
from src.services.user_settings_service import UserSettingsService

logger = logging.getLogger(__name__)


class GeneticRouteOptimizer:
    """
    Генетический оптимизатор маршрутов с кластеризацией и синхронизацией временных окон
    """
    
    # Параметры генетического алгоритма
    POPULATION_SIZE = 80  # Увеличено для лучшего поиска
    MAX_GENERATIONS = 200  # Увеличено для лучшей сходимости
    TOURNAMENT_SIZE = 3
    CROSSOVER_RATE = 0.8
    MUTATION_RATE = 0.2  # Увеличено для большего разнообразия
    ELITISM_COUNT = 10  # Увеличено для сохранения лучших решений
    MAX_DELAY_MINUTES = 10  # Максимальное опоздание
    MANUAL_TIME_TOLERANCE = 7  # Допуск для manual_arrival_time ±7 минут
    WINDOW_END_TOLERANCE_MINUTES = 1  # Прибытие в конец окна ±1 мин считаем вовремя
    CLUSTER_RADIUS_KM = 1.0  # Радиус кластеризации
    GREEDY_EST_KM_PER_MIN = 0.5  # Оценка скорости для greedy (~30 км/ч), время = км / это

    def __init__(self, maps_service: MapsService):
        self.maps_service = maps_service
        self.settings_service = UserSettingsService()
        random.seed()  # Инициализация генератора случайных чисел
    
    def optimize_route_sync(
        self,
        orders: List[Order],
        start_location: Tuple[float, float],  # (lat, lon)
        start_time: datetime,
        vehicle_capacity: int = 50,  # Не используется, но для совместимости
        user_id: int = None,
        use_fallback: bool = False  # Не используется
    ) -> OptimizedRoute:
        """
        Оптимизировать маршрут для списка заказов с помощью генетического алгоритма
        
        Args:
            orders: Список заказов
            start_location: Точка старта (lat, lon)
            start_time: Время старта
            vehicle_capacity: Не используется (для совместимости)
            user_id: ID пользователя
            use_fallback: Не используется (для совместимости)
            
        Returns:
            Оптимизированный маршрут
        """
        if not orders:
            logger.info("📦 Нет заказов для оптимизации")
            return OptimizedRoute(points=[], total_distance=0, total_time=0, estimated_completion=start_time)
        
        logger.info(f"🧬 ГЕНЕТИЧЕСКАЯ ОПТИМИЗАЦИЯ: {len(orders)} заказов")
        logger.info(f"⏰ Время старта: {start_time.strftime('%H:%M')}")
        
        # Геокодируем заказы без координат
        logger.info(f"🗺️ Проверяю и геокодирую заказы без координат...")
        geocoded_orders = []
        for idx, order in enumerate(orders, 1):
            if order.latitude is None or order.longitude is None:
                # Только если координат нет - делаем геокодирование
                logger.info(f"🗺️ [{idx}/{len(orders)}] Заказ {order.order_number} без координат, геокодирую адрес: {order.address}")
                if order.address and order.address.strip():
                    lat, lon, gid = self.maps_service.geocode_address_sync(order.address)
                    order.latitude = lat
                    order.longitude = lon
                    order.gis_id = gid
                    if lat and lon:
                        logger.info(f"   ✅ Получены координаты: lat={lat:.6f}, lon={lon:.6f}, gis_id={gid}")
                    else:
                        logger.error(f"   ❌ Не удалось получить координаты для адреса: {order.address}")
                else:
                    logger.warning(f"⚠️ Заказ {order.order_number} не может быть загеокодирован: адрес отсутствует или пустой")
            else:
                logger.debug(f"✅ [{idx}/{len(orders)}] Заказ {order.order_number} уже имеет координаты: lat={order.latitude:.6f}, lon={order.longitude:.6f}")
            geocoded_orders.append(order)
        
        # Фильтруем заказы с координатами
        orders_with_coords = [o for o in geocoded_orders if o.latitude and o.longitude]
        orders_without_coords = [o for o in geocoded_orders if not o.latitude or not o.longitude]
        
        if orders_without_coords:
            logger.warning(f"⚠️ {len(orders_without_coords)} заказов без координат будут исключены:")
            for order in orders_without_coords:
                logger.warning(f"   ❌ Заказ {order.order_number}: адрес='{order.address}', lat={order.latitude}, lon={order.longitude}")
        
        if not orders_with_coords:
            logger.error("❌ Нет заказов с координатами для оптимизации")
            return OptimizedRoute(points=[], total_distance=0, total_time=0, estimated_completion=start_time)
        
        # Специальный случай: 1 заказ
        if len(orders_with_coords) == 1:
            logger.info("📦 Один заказ - обрабатываю напрямую")
            return self._build_single_order_route(orders_with_coords[0], start_location, start_time, user_id)
        
        # Этап 1: Кластеризация и синхронизация окон
        logger.info(f"🔗 Этап 1: Кластеризация заказов (радиус {self.CLUSTER_RADIUS_KM} км)")
        clustered_orders = self._cluster_and_synchronize_orders(orders_with_coords, start_time)
        
        # Этап 2: Генетический алгоритм
        logger.info(f"🧬 Этап 2: Генетический алгоритм ({self.POPULATION_SIZE} особей, {self.MAX_GENERATIONS} поколений)")
        best_route = self._genetic_algorithm(
            clustered_orders, start_location, start_time, user_id
        )
        
        if not best_route or not best_route.points:
            logger.error("❌ Генетический алгоритм не смог построить маршрут")
            return OptimizedRoute(points=[], total_distance=0, total_time=0, estimated_completion=start_time)
        
        logger.info(f"✅ Оптимизация завершена: {len(best_route.points)} точек, "
                   f"{best_route.total_distance:.1f} км, {best_route.total_time:.0f} мин")
        
        return best_route
    
    def _cluster_and_synchronize_orders(
        self,
        orders: List[Order],
        start_time: datetime
    ) -> List[Order]:
        """
        Кластеризация заказов по расстоянию и синхронизация временных окон внутри кластеров
        
        Args:
            orders: Список заказов
            start_time: Время старта (для определения даты)
            
        Returns:
            Список заказов с синхронизированными окнами
        """
        if len(orders) <= 1:
            return orders
        
        order_date = start_time.date()
        orders_with_coords = [o for o in orders if o.latitude and o.longitude]
        
        if not orders_with_coords:
            return orders
        
        # Greedy кластеризация
        clusters = []
        remaining = orders_with_coords.copy()
        
        while remaining:
            seed = remaining.pop(0)
            cluster = [seed]
            
            # Ищем близкие заказы
            i = 0
            while i < len(remaining):
                order = remaining[i]
                distance = self._haversine_distance(
                    seed.latitude, seed.longitude,
                    order.latitude, order.longitude
                )
                
                if distance <= self.CLUSTER_RADIUS_KM:
                    cluster.append(order)
                    remaining.pop(i)
                else:
                    i += 1
            
            clusters.append(cluster)
        
        logger.info(f"   📊 Создано {len(clusters)} кластеров")
        for idx, cluster in enumerate(clusters, 1):
            logger.info(f"   Кластер {idx}: {len(cluster)} заказов")
        
        # Синхронизация окон внутри кластеров
        synchronized_orders = []
        for cluster in clusters:
            if len(cluster) > 1:
                # Синхронизируем окна
                synchronized_cluster = self._synchronize_time_windows(cluster, order_date)
                synchronized_orders.extend(synchronized_cluster)
            else:
                synchronized_orders.extend(cluster)
        
        return synchronized_orders
    
    def _synchronize_time_windows(
        self,
        cluster: List[Order],
        order_date
    ) -> List[Order]:
        """
        Синхронизировать временные окна для заказов в кластере
        
        Args:
            cluster: Список заказов в кластере
            order_date: Дата заказов
            
        Returns:
            Список заказов с синхронизированными окнами
        """
        
        # Фильтруем заказы с временными окнами
        orders_with_windows = [o for o in cluster if o.delivery_time_start and o.delivery_time_end]
        
        if not orders_with_windows:
            # Нет окон - возвращаем как есть
            return cluster
        
        if len(orders_with_windows) == 1:
            # Один заказ с окном - возвращаем как есть
            return cluster
        
        # Находим пересечение всех окон
        common_start = None
        common_end = None
        
        for order in orders_with_windows:
            window_start = datetime.combine(order_date, order.delivery_time_start)
            window_end = datetime.combine(order_date, order.delivery_time_end)
            
            if common_start is None:
                common_start = window_start
                common_end = window_end
            else:
                common_start = max(common_start, window_start)
                common_end = min(common_end, window_end)
        
        # Проверяем, есть ли пересечение
        if common_start < common_end:
            # Есть пересечение!
            duration_min = (common_end - common_start).total_seconds() / 60.0
            order_nums = ", ".join(o.order_number or "?" for o in cluster)
            
            if duration_min >= 30:
                # Пересечение >= 30 минут - используем его
                logger.info(
                    f"   ✅ Синхронизация: {common_start.strftime('%H:%M')}-{common_end.strftime('%H:%M')} "
                    f"({duration_min:.0f} мин) для заказов {order_nums}"
                )
                
                for order in cluster:
                    if order.delivery_time_start and order.delivery_time_end:
                        order.delivery_time_start = common_start.time()
                        order.delivery_time_end = common_end.time()
                
                return cluster
            else:
                # Пересечение < 30 минут - используем самое узкое окно
                narrowest_order = min(orders_with_windows, key=lambda o: (
                    datetime.combine(order_date, o.delivery_time_end) -
                    datetime.combine(order_date, o.delivery_time_start)
                ).total_seconds())
                
                target_start = narrowest_order.delivery_time_start
                target_end = narrowest_order.delivery_time_end
                
                logger.info(
                    f"   ⚠️ Пересечение < 30 мин, узкое окно: "
                    f"{target_start.strftime('%H:%M')}-{target_end.strftime('%H:%M')} "
                    f"для заказов {order_nums}"
                )
                
                for order in cluster:
                    if order.delivery_time_start and order.delivery_time_end:
                        order.delivery_time_start = target_start
                        order.delivery_time_end = target_end
                
                return cluster
        else:
            # Пересечения нет - используем самое узкое окно
            narrowest_order = min(orders_with_windows, key=lambda o: (
                datetime.combine(order_date, o.delivery_time_end) -
                datetime.combine(order_date, o.delivery_time_start)
            ).total_seconds())
            
            target_start = narrowest_order.delivery_time_start
            target_end = narrowest_order.delivery_time_end
            order_nums = ", ".join(o.order_number or "?" for o in cluster)
            
            logger.info(
                f"   ⚠️ Нет пересечения, узкое окно: "
                f"{target_start.strftime('%H:%M')}-{target_end.strftime('%H:%M')} "
                f"для заказов {order_nums}"
            )
            
            for order in cluster:
                if order.delivery_time_start and order.delivery_time_end:
                    order.delivery_time_start = target_start
                    order.delivery_time_end = target_end
            
            return cluster
    
    def _haversine_distance(self, lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """
        Расстояние между двумя точками по формуле Haversine (км)
        
        Args:
            lat1, lon1: Координаты первой точки
            lat2, lon2: Координаты второй точки
            
        Returns:
            Расстояние в километрах
        """
        R = 6371  # Радиус Земли в км
        
        dlat = radians(lat2 - lat1)
        dlon = radians(lon2 - lon1)
        
        a = sin(dlat / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon / 2) ** 2
        c = 2 * atan2(sqrt(a), sqrt(1 - a))
        
        return R * c
    
    def _build_single_order_route(
        self,
        order: Order,
        start_location: Tuple[float, float],
        start_time: datetime,
        user_id: int = None
    ) -> OptimizedRoute:
        """
        Построить маршрут для одного заказа
        
        Args:
            order: Заказ
            start_location: Точка старта
            start_time: Время старта
            user_id: ID пользователя
            
        Returns:
            Оптимизированный маршрут
        """
        try:
            distance, travel_time = self.maps_service.get_route_sync(
                start_location[0], start_location[1],
                order.latitude, order.longitude,
                user_id=user_id
            )
            
            arrival_time = start_time + timedelta(minutes=travel_time)
            
            # Проверяем временное окно
            if order.delivery_time_start and order.delivery_time_end:
                order_date = start_time.date()
                window_start = datetime.combine(order_date, order.delivery_time_start)
                window_end = datetime.combine(order_date, order.delivery_time_end)
                
                if arrival_time < window_start:
                    wait_time = (window_start - arrival_time).total_seconds() / 60.0
                    logger.info(f"   ⏰ Ожидание {wait_time:.0f} мин до начала окна")
                    arrival_time = window_start
                
                if arrival_time > window_end:
                    delay = (arrival_time - window_end).total_seconds() / 60.0
                    if delay > self.MAX_DELAY_MINUTES:
                        logger.warning(f"   ⚠️ Опоздание {delay:.0f} мин (превышает максимум {self.MAX_DELAY_MINUTES} мин)")
                    else:
                        logger.warning(f"   ⚠️ Опоздание {delay:.0f} мин")
            
            # Время обслуживания
            service_time_minutes = 10
            if user_id:
                user_settings = self.settings_service.get_settings(user_id)
                service_time_minutes = user_settings.service_time_minutes
            
            point = RoutePoint(
                order=order,
                estimated_arrival=arrival_time,
                distance_from_previous=distance,
                time_from_previous=travel_time
            )
            
            completion_time = arrival_time + timedelta(minutes=service_time_minutes)
            
            return OptimizedRoute(
                points=[point],
                total_distance=distance,
                total_time=travel_time + service_time_minutes,
                estimated_completion=completion_time
            )
            
        except Exception as e:
            logger.error(f"❌ Ошибка обработки заказа {order.order_number}: {e}")
            return OptimizedRoute(points=[], total_distance=0, total_time=0, estimated_completion=start_time)
    
    def _genetic_algorithm(
        self,
        orders: List[Order],
        start_location: Tuple[float, float],
        start_time: datetime,
        user_id: int = None
    ) -> Optional[OptimizedRoute]:
        """
        Основной цикл генетического алгоритма
        
        Args:
            orders: Список заказов
            start_location: Точка старта
            start_time: Время старта
            user_id: ID пользователя
            
        Returns:
            Лучший найденный маршрут
        """
        num_orders = len(orders)
        if num_orders == 0:
            return None
        
        # Генерация начальной популяции
        logger.info(f"   🧬 Генерирую начальную популяцию из {self.POPULATION_SIZE} особей...")
        population = self._generate_initial_population(orders, start_location, start_time, user_id)
        
        if not population:
            logger.error("❌ Не удалось создать начальную популяцию")
            return None
        
        # Оценка фитнеса для начальной популяции
        fitness_scores = []
        for chromosome in population:
            fitness = self._calculate_fitness(chromosome, orders, start_location, start_time, user_id)
            fitness_scores.append(fitness)
        
        # Находим лучшую особь
        best_idx = min(range(len(population)), key=lambda i: fitness_scores[i])
        best_fitness = fitness_scores[best_idx]
        best_chromosome = population[best_idx]
        
        logger.info(f"   📊 Начальная популяция: лучший фитнес = {best_fitness:.2f}")
        
        # Основной цикл эволюции
        generation = 0
        stagnation_count = 0
        last_best_fitness = best_fitness
        
        while generation < self.MAX_GENERATIONS:
            # Создание нового поколения
            new_population = []
            
            # Элитизм: сохраняем лучших особей
            elite_indices = sorted(range(len(population)), key=lambda i: fitness_scores[i])[:self.ELITISM_COUNT]
            for idx in elite_indices:
                new_population.append(population[idx].copy())
            
            # Генерация потомков
            while len(new_population) < self.POPULATION_SIZE:
                # Селекция родителей
                parent1 = self._tournament_selection(population, fitness_scores)
                parent2 = self._tournament_selection(population, fitness_scores)
                
                # Кроссовер
                if random.random() < self.CROSSOVER_RATE:
                    child = self._order_crossover(parent1, parent2)
                else:
                    child = parent1.copy() if random.random() < 0.5 else parent2.copy()
                
                # Мутация
                if random.random() < self.MUTATION_RATE:
                    child = self._mutate(child, orders, start_time)

                # Ремонт порядка по концу окна: не допускаем «10–13 после 12–15/13–16»
                self._repair_window_order(child, orders, start_time)

                # Проверка валидности
                if self._is_valid_chromosome(child, num_orders):
                    new_population.append(child)
            
            # Оценка фитнеса нового поколения
            population = new_population
            fitness_scores = []
            for chromosome in population:
                fitness = self._calculate_fitness(chromosome, orders, start_location, start_time, user_id)
                fitness_scores.append(fitness)
            
            # Обновление лучшей особи
            current_best_idx = min(range(len(population)), key=lambda i: fitness_scores[i])
            current_best_fitness = fitness_scores[current_best_idx]
            
            if current_best_fitness < best_fitness:
                best_fitness = current_best_fitness
                best_chromosome = population[current_best_idx].copy()
                stagnation_count = 0
            else:
                stagnation_count += 1
            
            generation += 1
            
            # Логирование прогресса
            if generation % 10 == 0:
                logger.info(f"   Поколение {generation}/{self.MAX_GENERATIONS}: лучший фитнес = {best_fitness:.2f}")
            
            # Ранняя остановка при стагнации
            if stagnation_count >= 30:
                logger.info(f"   ⏹️ Ранняя остановка: нет улучшений {stagnation_count} поколений")
                break
        
        logger.info(f"   ✅ Генетический алгоритм завершен: поколение {generation}, лучший фитнес = {best_fitness:.2f}")
        
        # Построение финального маршрута
        return self._build_route_from_chromosome(best_chromosome, orders, start_location, start_time, user_id)
    
    def _generate_initial_population(
        self,
        orders: List[Order],
        start_location: Tuple[float, float],
        start_time: datetime,
        user_id: int = None
    ) -> List[List[int]]:
        """
        Генерация начальной популяции маршрутов
        
        Args:
            orders: Список заказов
            start_location: Точка старта
            start_time: Время старта
            user_id: ID пользователя
            
        Returns:
            Список хромосом (каждая хромосома - список индексов заказов)
        """
        num_orders = len(orders)
        population = []
        
        # Стратегия 1: Случайные перестановки (меньше доля — чтобы не плодить «10–13 после 12–15»)
        for _ in range(self.POPULATION_SIZE // 4):
            chromosome = list(range(num_orders))
            random.shuffle(chromosome)
            population.append(chromosome)

        # Стратегия 1b: Группа по концу окна — внутри группы случайный порядок (10–13 всегда перед 12–15/13–16)
        order_date = start_time.date()
        def _window_end_key(i):
            o = orders[i]
            if not o.delivery_time_end:
                return (float('inf'), 0)
            return (datetime.combine(order_date, o.delivery_time_end).timestamp(), i)
        indices_by_end: Dict[float, List[int]] = {}
        for i in range(num_orders):
            k = _window_end_key(i)[0]
            if k not in indices_by_end:
                indices_by_end[k] = []
            indices_by_end[k].append(i)
        for _ in range(self.POPULATION_SIZE // 4):
            chromosome = []
            for end_ts in sorted(indices_by_end.keys()):
                group = indices_by_end[end_ts].copy()
                random.shuffle(group)
                chromosome.extend(group)
            population.append(chromosome)

        # Стратегия 2: Сортировка по началу временного окна
        for _ in range(self.POPULATION_SIZE // 8):
            order_date = start_time.date()
            sorted_indices = sorted(
                range(num_orders),
                key=lambda i: (
                    datetime.combine(order_date, orders[i].delivery_time_start).timestamp()
                    if orders[i].delivery_time_start else float('inf')
                )
            )
            # Добавляем небольшую случайность
            chromosome = sorted_indices.copy()
            for _ in range(random.randint(0, num_orders // 3)):
                i, j = random.sample(range(num_orders), 2)
                chromosome[i], chromosome[j] = chromosome[j], chromosome[i]
            population.append(chromosome)
        
        # Стратегия 3: По концу окна и ширине (раньше конец, уже окно — раньше в маршруте) (12.5%)
        order_date = start_time.date()
        def _end_and_width(i):
            o = orders[i]
            if not o.delivery_time_end:
                return (float('inf'), 0)
            end_ts = datetime.combine(order_date, o.delivery_time_end).timestamp()
            if not o.delivery_time_start:
                return (end_ts, 0)
            start_dt = datetime.combine(order_date, o.delivery_time_start)
            end_dt = datetime.combine(order_date, o.delivery_time_end)
            duration_min = (end_dt - start_dt).total_seconds() / 60.0
            return (end_ts, -duration_min)
        for _ in range(self.POPULATION_SIZE // 8):
            sorted_indices = sorted(range(num_orders), key=_end_and_width)
            chromosome = sorted_indices.copy()
            for _ in range(random.randint(0, num_orders // 4)):
                i, j = random.sample(range(num_orders), 2)
                chromosome[i], chromosome[j] = chromosome[j], chromosome[i]
            population.append(chromosome)
        
        # Стратегия 3b: Строго по ужесточению окна (тот же ключ, без перемешивания)
        strict_by_window = sorted(range(num_orders), key=_end_and_width)
        for _ in range(min(12, self.POPULATION_SIZE // 4)):
            population.append(strict_by_window.copy())
        
        # Стратегия 4: Greedy nearest neighbor с учетом временных окон
        remaining_count = self.POPULATION_SIZE - len(population)
        for _ in range(remaining_count):
            chromosome = self._greedy_nearest_neighbor(orders, start_location, start_time, user_id)
            population.append(chromosome)
        
        return population
    
    def _greedy_nearest_neighbor(
        self,
        orders: List[Order],
        start_location: Tuple[float, float],
        start_time: datetime = None,
        user_id: int = None
    ) -> List[int]:
        """
        Greedy алгоритм ближайшего соседа: расстояние + оценка времени прибытия.
        Кандидаты, при поезде к которым «сейчас» приедем после конца окна, сильно штрафуются.
        
        Args:
            orders: Список заказов
            start_location: Точка старта
            start_time: Время старта
            user_id: ID пользователя (для service_time_minutes)
            
        Returns:
            Хромосома (список индексов)
        """
        num_orders = len(orders)
        if num_orders == 0:
            return []
        
        service_time_minutes = 10
        if user_id is not None:
            try:
                user_settings = self.settings_service.get_settings(user_id)
                service_time_minutes = user_settings.service_time_minutes
            except Exception:
                pass
        
        chromosome = []
        remaining = set(range(num_orders))
        current_location = start_location
        current_time = start_time if start_time else datetime.now()
        order_date = current_time.date()
        
        while remaining:
            # Сначала обслуживаем заказы с самым ранним концом окна — никогда не ставим 10–13 после 12–15/13–16
            min_window_end_ts = float('inf')
            for idx in remaining:
                o = orders[idx]
                if o.delivery_time_end:
                    ts = datetime.combine(order_date, o.delivery_time_end).timestamp()
                    if ts < min_window_end_ts:
                        min_window_end_ts = ts
            candidates = [
                idx for idx in remaining
                if not orders[idx].delivery_time_end
                or datetime.combine(order_date, orders[idx].delivery_time_end).timestamp() <= min_window_end_ts
            ]
            if not candidates:
                candidates = list(remaining)

            best_idx = None
            best_score = (float('inf'), float('inf'))
            best_distance = 0.0

            for idx in candidates:
                order = orders[idx]
                distance = self._haversine_distance(
                    current_location[0], current_location[1],
                    order.latitude, order.longitude
                )
                travel_est_min = distance / self.GREEDY_EST_KM_PER_MIN
                arrival_est = current_time + timedelta(minutes=travel_est_min)

                late_penalty = 0.0
                if order.delivery_time_end:
                    window_end = datetime.combine(order_date, order.delivery_time_end)
                    if arrival_est > window_end:
                        late_penalty = 1e6

                end_ts = (
                    datetime.combine(order_date, order.delivery_time_end).timestamp()
                    if order.delivery_time_end else float('inf')
                )
                score = (late_penalty + distance, end_ts)

                if score < best_score:
                    best_score = score
                    best_idx = idx
                    best_distance = distance

            if best_idx is not None:
                order = orders[best_idx]
                chromosome.append(best_idx)
                remaining.remove(best_idx)
                current_location = (order.latitude, order.longitude)
                travel_est_min = best_distance / self.GREEDY_EST_KM_PER_MIN
                arrival_est = current_time + timedelta(minutes=travel_est_min)
                if order.delivery_time_start and order.delivery_time_end:
                    window_start = datetime.combine(order_date, order.delivery_time_start)
                    if arrival_est < window_start:
                        arrival_est = window_start
                current_time = arrival_est + timedelta(minutes=service_time_minutes)
        
        return chromosome
    
    def _calculate_fitness(
        self,
        chromosome: List[int],
        orders: List[Order],
        start_location: Tuple[float, float],
        start_time: datetime,
        user_id: int = None
    ) -> float:
        """
        Вычисление фитнеса маршрута (чем меньше, тем лучше)
        
        Args:
            chromosome: Хромосома (список индексов заказов)
            orders: Список заказов
            start_location: Точка старта
            start_time: Время старта
            user_id: ID пользователя
            
        Returns:
            Значение фитнеса
        """
        if not chromosome:
            return float('inf')
        
        total_distance = 0.0
        total_time = 0.0
        violations = 0  # Количество нарушений временных окон
        total_delay = 0.0  # Общее опоздание (минуты)
        critical_delays = 0  # Количество критических опозданий (>10 мин)
        critical_delay_minutes = 0.0  # Сумма минут критических опозданий
        early_arrivals = 0  # Количество ранних прибытий (для статистики)
        manual_time_violations = 0  # Нарушения manual_arrival_time
        
        current_location = start_location
        current_time = start_time
        order_date = start_time.date()
        
        # Время обслуживания
        service_time_minutes = 10
        if user_id:
            user_settings = self.settings_service.get_settings(user_id)
            service_time_minutes = user_settings.service_time_minutes
        
        for order_idx in chromosome:
            if order_idx >= len(orders):
                return float('inf')
            
            order = orders[order_idx]
            
            # Получаем расстояние и время (используем кэш maps_service)
            try:
                distance, travel_time = self.maps_service.get_route_sync(
                    current_location[0], current_location[1],
                    order.latitude, order.longitude,
                    user_id=user_id
                )
            except Exception as e:
                logger.warning(f"⚠️ Ошибка получения маршрута для заказа {order.order_number}: {e}")
                return float('inf')
            
            # Время прибытия
            arrival_time = current_time + timedelta(minutes=travel_time)
            
            # Проверка временного окна
            if order.delivery_time_start and order.delivery_time_end:
                window_start = datetime.combine(order_date, order.delivery_time_start)
                window_end = datetime.combine(order_date, order.delivery_time_end)
                
                # Раннее прибытие: считаем как ожидание (увеличивает total_time),
                # но больше не считаем это жёстким нарушением
                if arrival_time < window_start:
                    early_arrivals += 1
                    wait_time = (window_start - arrival_time).total_seconds() / 60.0
                    arrival_time = window_start
                    total_time += wait_time
                
                # Позднее прибытие
                if arrival_time > window_end:
                    violations += 1
                    delay = (arrival_time - window_end).total_seconds() / 60.0
                    # Критическое опоздание > 10 минут
                    if delay > self.MAX_DELAY_MINUTES:
                        critical_delays += 1
                        critical_delay_minutes += delay
                        total_delay += delay
                    else:
                        # Обычное опоздание
                        total_delay += delay
            
            # Проверка manual_arrival_time
            if order.manual_arrival_time:
                tolerance_minutes = self.MANUAL_TIME_TOLERANCE
                time_diff = abs((arrival_time - order.manual_arrival_time).total_seconds() / 60.0)
                if time_diff > tolerance_minutes:
                    manual_time_violations += 1
            
            # Обновляем метрики
            total_distance += distance
            total_time += travel_time + service_time_minutes
            
            # Переходим к следующей точке
            current_location = (order.latitude, order.longitude)
            current_time = arrival_time + timedelta(minutes=service_time_minutes)
        
        # Фитнес: маршруты без опозданий всегда лучше любых с опозданиями (явный ярус)
        FEASIBLE_TIER = 0.0           # нет опозданий
        INFEASIBLE_TIER = 1_000_000_000.0  # хотя бы одно опоздание
        tier = INFEASIBLE_TIER if (violations > 0 or total_delay > 0) else FEASIBLE_TIER
        
        # 1) Штрафы за нарушения окон (внутри яруса)
        K_VIOL = 1_000_000.0      # любое нарушение окна очень дорого
        K_DELAY = 5_000.0         # минуты опоздания важнее километража
        K_CRIT_COUNT = 200_000.0  # за каждый заказ с критическим опозданием
        K_CRIT_MIN = 10_000.0     # за минуты критического опоздания
        
        # 2) Мягкие ограничения
        K_MANUAL = 2_000.0        # нарушения manual_arrival_time
        
        # 3) Качество маршрута при равных окнах
        K_DIST = 10.0             # вклад расстояния
        K_TIME = 5.0              # вклад общего времени
        
        fitness = (
            tier +
            violations * K_VIOL +
            total_delay * K_DELAY +
            critical_delays * K_CRIT_COUNT +
            critical_delay_minutes * K_CRIT_MIN +
            manual_time_violations * K_MANUAL +
            total_distance * K_DIST +
            total_time * K_TIME
        )
        
        return fitness
    
    def _tournament_selection(
        self,
        population: List[List[int]],
        fitness_scores: List[float]
    ) -> List[int]:
        """
        Турнирная селекция родителей
        
        Args:
            population: Популяция
            fitness_scores: Оценки фитнеса
            
        Returns:
            Выбранная хромосома
        """
        tournament_indices = random.sample(range(len(population)), self.TOURNAMENT_SIZE)
        tournament_fitness = [fitness_scores[i] for i in tournament_indices]
        winner_idx = tournament_indices[min(range(len(tournament_fitness)), key=lambda i: tournament_fitness[i])]
        return population[winner_idx].copy()
    
    def _repair_window_order(
        self,
        chromosome: List[int],
        orders: List[Order],
        start_time: datetime
    ) -> None:
        """
        Исправляем порядок по концу окна: заказ с более ранним концом окна
        не должен стоять после заказа с более поздним (не «10–13 после 12–15/13–16»).
        Повторяем проходы по соседним парам до отсутствия нарушений. Меняет chromosome in-place.
        """
        if len(chromosome) < 2:
            return
        order_date = start_time.date()
        n = len(chromosome)
        while True:
            swapped = False
            for i in range(n - 1):
                o_i = orders[chromosome[i]]
                o_j = orders[chromosome[i + 1]]
                if not o_i.delivery_time_end or not o_j.delivery_time_end:
                    continue
                we_i = datetime.combine(order_date, o_i.delivery_time_end)
                we_j = datetime.combine(order_date, o_j.delivery_time_end)
                if we_i > we_j:
                    chromosome[i], chromosome[i + 1] = chromosome[i + 1], chromosome[i]
                    swapped = True
            if not swapped:
                break

    def _order_crossover(
        self,
        parent1: List[int],
        parent2: List[int]
    ) -> List[int]:
        """
        Order Crossover (OX) для создания потомка
        
        Args:
            parent1: Первый родитель
            parent2: Второй родитель
            
        Returns:
            Потомок
        """
        if len(parent1) != len(parent2):
            return parent1.copy()
        
        n = len(parent1)
        if n <= 2:
            return parent1.copy()
        
        # Выбираем случайный сегмент
        start = random.randint(0, n - 2)
        end = random.randint(start + 1, n - 1)
        
        # Копируем сегмент из parent1
        child = [None] * n
        segment = parent1[start:end+1]
        child[start:end+1] = segment
        
        # Заполняем остальное из parent2
        used = set(segment)
        idx = (end + 1) % n
        for val in parent2:
            if val not in used:
                child[idx] = val
                idx = (idx + 1) % n
                if idx == start:
                    idx = (idx + 1) % n
        
        return child
    
    def _mutate(
        self,
        chromosome: List[int],
        orders: List[Order] = None,
        start_time: datetime = None
    ) -> List[int]:
        """
        Мутация хромосомы
        
        Args:
            chromosome: Хромосома для мутации
            orders: Список заказов (для умной мутации)
            start_time: Время старта (для умной мутации)
            
        Returns:
            Мутированная хромосома
        """
        if len(chromosome) <= 1:
            return chromosome.copy()
        
        mutation_type = random.random()
        
        # Умная мутация для исправления опозданий (10%) - уменьшено
        if mutation_type < 0.1 and orders and start_time:
            return self._smart_mutation_for_delays(chromosome, orders, start_time)
        
        elif mutation_type < 0.5:
            # Swap Mutation (40%)
            i, j = random.sample(range(len(chromosome)), 2)
            mutated = chromosome.copy()
            mutated[i], mutated[j] = mutated[j], mutated[i]
            return mutated
        
        elif mutation_type < 0.8:
            # Inversion Mutation (30%)
            if len(chromosome) >= 2:
                start = random.randint(0, len(chromosome) - 2)
                end = random.randint(start + 1, len(chromosome) - 1)
                mutated = chromosome.copy()
                mutated[start:end+1] = reversed(mutated[start:end+1])
                return mutated
        
        else:
            # Insertion Mutation (20%)
            if len(chromosome) >= 2:
                mutated = chromosome.copy()
                idx = random.randint(0, len(mutated) - 1)
                val = mutated.pop(idx)
                new_idx = random.randint(0, len(mutated))
                mutated.insert(new_idx, val)
                return mutated
        
        return chromosome.copy()
    
    def _smart_mutation_for_delays(
        self,
        chromosome: List[int],
        orders: List[Order],
        start_time: datetime
    ) -> List[int]:
        """
        Умная мутация: перемещает заказы с опозданиями ближе к началу маршрута
        
        Args:
            chromosome: Хромосома
            orders: Список заказов
            start_time: Время старта
            
        Returns:
            Мутированная хромосома
        """
        if len(chromosome) <= 1:
            return chromosome.copy()
        
        mutated = chromosome.copy()
        order_date = start_time.date()
        
        # Заказы во второй половине маршрута (все окна равны, без приоритета по часу)
        late_route_orders = []
        half = len(chromosome) / 2
        for pos, idx in enumerate(chromosome):
            if idx < len(orders) and pos > half:
                order = orders[idx]
                if order.delivery_time_end:
                    window_end = datetime.combine(order_date, order.delivery_time_end)
                    late_route_orders.append((idx, window_end, pos))
        
        if late_route_orders:
            # Сортируем: дальние в маршруте первыми, при равной позиции — раньше кончающиеся окна
            late_route_orders.sort(key=lambda x: (x[2], -x[1].timestamp()), reverse=True)
            
            for order_idx, _, _ in late_route_orders[:min(2, len(late_route_orders))]:
                if order_idx in mutated:
                    # Удаляем из текущей позиции
                    mutated_pos = mutated.index(order_idx)
                    mutated.pop(mutated_pos)
                    # Вставляем ближе к началу, но не в самое начало (более консервативно)
                    # Перемещаем в первую треть маршрута, но не в первые 2 позиции
                    if len(mutated) > 2:
                        new_pos = random.randint(2, max(3, len(chromosome) // 3))
                    else:
                        new_pos = random.randint(0, len(mutated))
                    mutated.insert(new_pos, order_idx)
        
        return mutated
    
    def _is_valid_chromosome(self, chromosome: List[int], num_orders: int) -> bool:
        """
        Проверка валидности хромосомы
        
        Args:
            chromosome: Хромосома
            num_orders: Количество заказов
            
        Returns:
            True если хромосома валидна
        """
        if len(chromosome) != num_orders:
            return False
        
        if set(chromosome) != set(range(num_orders)):
            return False
        
        return True
    
    def _build_route_from_chromosome(
        self,
        chromosome: List[int],
        orders: List[Order],
        start_location: Tuple[float, float],
        start_time: datetime,
        user_id: int = None
    ) -> OptimizedRoute:
        """
        Построение OptimizedRoute из хромосомы
        
        Args:
            chromosome: Хромосома (список индексов заказов)
            orders: Список заказов
            start_location: Точка старта
            start_time: Время старта
            user_id: ID пользователя
            
        Returns:
            Оптимизированный маршрут
        """
        if not chromosome:
            return OptimizedRoute(points=[], total_distance=0, total_time=0, estimated_completion=start_time)
        
        points = []
        total_distance = 0.0
        total_time = 0.0
        current_location = start_location
        current_time = start_time
        order_date = start_time.date()
        
        # Время обслуживания
        service_time_minutes = 10
        if user_id:
            user_settings = self.settings_service.get_settings(user_id)
            service_time_minutes = user_settings.service_time_minutes
        
        for order_idx in chromosome:
            if order_idx >= len(orders):
                continue
            
            order = orders[order_idx]
            
            try:
                # Получаем расстояние и время
                distance, travel_time = self.maps_service.get_route_sync(
                    current_location[0], current_location[1],
                    order.latitude, order.longitude,
                    user_id=user_id
                )
                
                # Время прибытия
                arrival_time = current_time + timedelta(minutes=travel_time)
                
                # Проверяем manual_arrival_time (приоритет над временным окном)
                if order.manual_arrival_time:
                    tolerance_minutes = self.MANUAL_TIME_TOLERANCE
                    time_diff = (arrival_time - order.manual_arrival_time).total_seconds() / 60.0
                    
                    # Если разница больше допуска, корректируем (но не более чем на допуск)
                    if abs(time_diff) > tolerance_minutes:
                        if time_diff > 0:
                            # Приедем позже - можем немного подождать, но не более чем на допуск
                            if time_diff > tolerance_minutes * 2:
                                # Слишком большое опоздание - оставляем как есть
                                logger.debug(f"   ⚠️ Заказ {order.order_number}: большое отклонение от manual_arrival_time ({time_diff:.0f} мин)")
                            else:
                                # Небольшое опоздание - корректируем
                                arrival_time = order.manual_arrival_time + timedelta(minutes=tolerance_minutes)
                        else:
                            # Приедем раньше - ждем до manual_arrival_time (с учетом допуска)
                            arrival_time = order.manual_arrival_time - timedelta(minutes=tolerance_minutes)
                            if arrival_time < current_time:
                                arrival_time = current_time
                
                # Проверяем временное окно
                if order.delivery_time_start and order.delivery_time_end:
                    window_start = datetime.combine(order_date, order.delivery_time_start)
                    window_end = datetime.combine(order_date, order.delivery_time_end)
                    
                    # Если приедем раньше - ждем
                    if arrival_time < window_start:
                        wait_time = (window_start - arrival_time).total_seconds() / 60.0
                        logger.debug(f"   ⏰ Заказ {order.order_number}: ожидание {wait_time:.0f} мин до начала окна")
                        arrival_time = window_start
                    
                    # Проверяем опоздание
                    if arrival_time > window_end:
                        delay = (arrival_time - window_end).total_seconds() / 60.0
                        if delay > self.MAX_DELAY_MINUTES:
                            logger.error(f"   🚨 КРИТИЧЕСКОЕ ОПОЗДАНИЕ: Заказ {order.order_number}: опоздание {delay:.0f} мин (превышает максимум {self.MAX_DELAY_MINUTES} мин)")
                        elif delay > 0:
                            logger.warning(f"   ⚠️ Заказ {order.order_number}: опоздание {delay:.0f} мин")
                
                # Создаем точку маршрута
                point = RoutePoint(
                    order=order,
                    estimated_arrival=arrival_time,
                    distance_from_previous=distance,
                    time_from_previous=travel_time
                )
                points.append(point)
                
                # Обновляем метрики
                total_distance += distance
                total_time += travel_time + service_time_minutes
                
                # Переходим к следующей точке
                current_location = (order.latitude, order.longitude)
                current_time = arrival_time + timedelta(minutes=service_time_minutes)
                
            except Exception as e:
                logger.error(f"❌ Ошибка обработки заказа {order.order_number}: {e}")
                continue
        
        if not points:
            return OptimizedRoute(points=[], total_distance=0, total_time=0, estimated_completion=start_time)
        
        # Финальная проверка опозданий
        critical_delays = 0
        total_delays = 0
        for point in points:
            order = point.order
            if order.delivery_time_start and order.delivery_time_end:
                order_date = start_time.date()
                window_end = datetime.combine(order_date, order.delivery_time_end)
                if point.estimated_arrival > window_end:
                    delay = (point.estimated_arrival - window_end).total_seconds() / 60.0
                    total_delays += delay
                    if delay > self.MAX_DELAY_MINUTES:
                        critical_delays += 1
        
        if critical_delays > 0:
            logger.error(f"🚨 КРИТИЧНО: В маршруте {critical_delays} заказов с опозданием > {self.MAX_DELAY_MINUTES} мин")
        elif total_delays > 0:
            logger.warning(f"⚠️ В маршруте есть опоздания (общее: {total_delays:.1f} мин)")
        else:
            logger.info(f"✅ Все заказы в пределах временных окон")
        
        route = OptimizedRoute(
            points=points,
            total_distance=total_distance,
            total_time=total_time,
            estimated_completion=current_time
        )
        
        # Постобработка: исправление любых опозданий (не только критических),
        # чтобы порядок по ужесточению окон мог быть найден локальным поиском
        route_after_fix = route
        if total_delays > 0:
            logger.info(
                f"🔧 Запускаю постобработку (опозданий: total {total_delays:.0f} мин, критических {critical_delays})..."
            )
            fixed_route = self._fix_delays_in_route(route, orders, start_location, start_time, user_id)
            if fixed_route and fixed_route.points:
                route_after_fix = fixed_route
        
        # Фаза спасения достижимости: если всё ещё есть опоздания, пытаемся
        # перестроить небольшой подмаршрут вокруг проблемных заказов
        rescued_route = self._rescue_feasibility(route_after_fix, orders, start_location, start_time, user_id)
        if rescued_route and rescued_route.points:
            # После спасения можно слегка подправить хвост тем же локальным поиском
            final_fixed = self._fix_delays_in_route(rescued_route, orders, start_location, start_time, user_id)
            if final_fixed and final_fixed.points:
                return final_fixed
            return rescued_route
        
        return route_after_fix

    def _tail_indices(self, n: int, K: int) -> List[int]:
        """Индексы последних K точек: [n-K, ..., n-1]."""
        K = min(K, n)
        return list(range(n - K, n))

    def _try_efp_for_delayed(
        self,
        points_list: List[RoutePoint],
        orders: List[Order],
        start_location: Tuple[float, float],
        start_time: datetime,
        user_id: Optional[int],
        order_date,
    ) -> Tuple[Optional[List[RoutePoint]], bool]:
        """
        Earliest feasible position: для каждого опаздывающего ищем самую раннюю
        позицию k, куда можно перенести заказ без новых критических опозданий
        и без увеличения числа опаздывающих. Применяем первый найденный ход.
        Возвращает (updated_points_list, True) при успехе, (None, False) иначе.
        """
        route = self._recalculate_route_times(points_list, orders, start_location, start_time, user_id)
        if not route:
            return (None, False)
        total_now, count_now, _ = self._route_delay_stats(route, order_date)
        if count_now == 0:
            return (None, False)

        tol = timedelta(minutes=self.WINDOW_END_TOLERANCE_MINUTES)
        delayed: List[Tuple[int, RoutePoint, float]] = []
        for idx, point in enumerate(route.points):
            o = point.order
            if o.delivery_time_start and o.delivery_time_end:
                we = datetime.combine(order_date, o.delivery_time_end)
                if point.estimated_arrival > we + tol:
                    d = (point.estimated_arrival - we).total_seconds() / 60.0
                    if d > self.WINDOW_END_TOLERANCE_MINUTES:
                        delayed.append((idx, point, d))
        delayed.sort(key=lambda x: x[2], reverse=True)

        n = len(points_list)
        for idx, delayed_point, _ in delayed:
            for k in range(0, idx):
                base = list(points_list)
                removed = base.pop(idx)
                base.insert(k, removed)
                trial = self._recalculate_route_times(base, orders, start_location, start_time, user_id)
                if not trial:
                    continue
                t_total, t_count, t_critical = self._route_delay_stats(trial, order_date)
                if t_critical or t_count > count_now:
                    continue
                moved_order_num = delayed_point.order.order_number
                moved_on_time = True
                for p in trial.points:
                    if p.order.order_number != moved_order_num:
                        continue
                    if p.order.delivery_time_start and p.order.delivery_time_end:
                        we = datetime.combine(order_date, p.order.delivery_time_end)
                        if p.estimated_arrival > we + tol:
                            moved_on_time = False
                            break
                    break
                if not moved_on_time:
                    continue
                return (base, True)
        return (None, False)

    def _try_swap_with_later_window(
        self,
        points_list: List[RoutePoint],
        orders: List[Order],
        start_location: Tuple[float, float],
        start_time: datetime,
        user_id: Optional[int],
        order_date,
        total_now: float,
        count_now: int,
    ) -> Tuple[Optional[List[RoutePoint]], bool]:
        """
        Обмен опаздывающего заказа (узкое/раннее окно) с более ранним заказом,
        у которого окно заканчивается позже — чтобы узкое окно попало в ранний слот.
        """
        route = self._recalculate_route_times(points_list, orders, start_location, start_time, user_id)
        if not route:
            return (None, False)
        delayed: List[Tuple[int, RoutePoint, float]] = []
        tol = timedelta(minutes=self.WINDOW_END_TOLERANCE_MINUTES)
        for idx, point in enumerate(route.points):
            o = point.order
            if o.delivery_time_start and o.delivery_time_end:
                we = datetime.combine(order_date, o.delivery_time_end)
                if point.estimated_arrival > we + tol:
                    d = (point.estimated_arrival - we).total_seconds() / 60.0
                    if d > self.WINDOW_END_TOLERANCE_MINUTES:
                        delayed.append((idx, point, d))
        if not delayed:
            return (None, False)
        n = len(points_list)
        delayed.sort(key=lambda x: x[2], reverse=True)
        for idx, delayed_point, _ in delayed:
            o_late = delayed_point.order
            we_late = datetime.combine(order_date, o_late.delivery_time_end) if o_late.delivery_time_end else None
            if we_late is None:
                continue
            for k in range(0, idx):
                o_early = points_list[k].order
                we_early = datetime.combine(order_date, o_early.delivery_time_end) if o_early.delivery_time_end else None
                if we_early is None or we_early <= we_late:
                    continue
                swap_points = list(points_list)
                swap_points[idx], swap_points[k] = swap_points[k], swap_points[idx]
                trial = self._recalculate_route_times(swap_points, orders, start_location, start_time, user_id)
                if not trial:
                    continue
                t_total, t_count, t_critical = self._route_delay_stats(trial, order_date)
                if t_critical or t_count > count_now:
                    continue
                if t_total < total_now or (t_total == total_now and t_count < count_now):
                    return (swap_points, True)
        return (None, False)

    def _try_tail_permutation(
        self,
        points_list: List[RoutePoint],
        orders: List[Order],
        start_location: Tuple[float, float],
        start_time: datetime,
        user_id: Optional[int],
        order_date,
        total_now: float,
        count_now: int,
    ) -> Tuple[Optional[List[RoutePoint]], bool]:
        """
        Перебор перестановок последних K точек. Возвращает (best_candidate, True)
        при улучшении, (None, False) иначе.
        """
        n = len(points_list)
        K = min(6, n)
        tail_idx = self._tail_indices(n, K)
        prefix = [points_list[i] for i in range(n - K)]
        best_points = None
        best_total = total_now
        best_count = count_now

        for perm in itertools.permutations(tail_idx):
            candidate = prefix + [points_list[i] for i in perm]
            trial = self._recalculate_route_times(candidate, orders, start_location, start_time, user_id)
            if not trial:
                continue
            t_total, t_count, t_critical = self._route_delay_stats(trial, order_date)
            if t_critical or t_count > count_now:
                continue
            if (t_total, -t_count) < (best_total, -best_count):
                best_total = t_total
                best_count = t_count
                best_points = candidate

        if best_points is None or not (best_total < total_now or (best_total == total_now and best_count < count_now)):
            return (None, False)
        return (best_points, True)

    def _try_block_move(
        self,
        points_list: List[RoutePoint],
        orders: List[Order],
        start_location: Tuple[float, float],
        start_time: datetime,
        user_id: Optional[int],
        order_date,
        total_now: float,
        count_now: int,
        delayed_points: List[Tuple[int, RoutePoint, float]],
    ) -> Tuple[Optional[List[RoutePoint]], bool]:
        """
        Блочные ходы: перенос блоков 2–3 подряд идущих заказов (включая опаздывающего)
        в более раннюю позицию. Возвращает (best_candidate, True) при улучшении.
        """
        n = len(points_list)
        best_points = None
        best_total = total_now
        best_count = count_now
        delayed_idx = {idx for idx, _, _ in delayed_points}

        def blocks_for(idx: int):
            out = []
            for start, end in [
                (idx - 1, idx),
                (idx, idx + 1),
                (idx - 2, idx),
                (idx - 1, idx + 1),
                (idx, idx + 2),
            ]:
                if start < 0 or end >= n or end <= start:
                    continue
                block = list(range(start, end + 1))
                if any(i in delayed_idx for i in block):
                    out.append(block)
            return out

        for idx, _, _ in delayed_points:
            for block in blocks_for(idx):
                insert_max = min(block)
                for pos in range(0, insert_max):
                    base = list(points_list)
                    removed = [base[i] for i in block]
                    for i in sorted(block, reverse=True):
                        base.pop(i)
                    for i, pt in enumerate(removed):
                        base.insert(pos + i, pt)
                    trial = self._recalculate_route_times(base, orders, start_location, start_time, user_id)
                    if not trial:
                        continue
                    t_total, t_count, t_critical = self._route_delay_stats(trial, order_date)
                    if t_critical or t_count > count_now:
                        continue
                    if (t_total, -t_count) < (best_total, -best_count):
                        best_total = t_total
                        best_count = t_count
                        best_points = base

        if best_points is None or not (best_total < total_now or (best_total == total_now and best_count < count_now)):
            return (None, False)
        return (best_points, True)

    def _route_delay_stats(
        self,
        route: OptimizedRoute,
        order_date
    ) -> Tuple[float, int, bool]:
        """
        (total_delay_min, count_delayed, has_critical) по маршруту.
        Прибытие в конец окна в пределах WINDOW_END_TOLERANCE_MINUTES считаем вовремя.
        """
        total = 0.0
        count = 0
        has_critical = False
        tol = timedelta(minutes=self.WINDOW_END_TOLERANCE_MINUTES)
        for p in route.points:
            o = p.order
            if not (o.delivery_time_start and o.delivery_time_end):
                continue
            we = datetime.combine(order_date, o.delivery_time_end)
            if p.estimated_arrival <= we + tol:
                continue
            d = (p.estimated_arrival - we).total_seconds() / 60.0
            total += d
            count += 1
            if d > self.MAX_DELAY_MINUTES:
                has_critical = True
        return (total, count, has_critical)
    
    def _fix_delays_in_route(
        self,
        route: OptimizedRoute,
        orders: List[Order],
        start_location: Tuple[float, float],
        start_time: datetime,
        user_id: int = None
    ) -> Optional[OptimizedRoute]:
        """
        Постобработка: EFP → tail permutation → move/swap → block move.
        Принимаем ход только при улучшении (total_delay, count_delayed) и без новых
        критических опозданий / роста числа опаздывающих.
        """
        if not route or not route.points:
            return None

        order_date = start_time.date()
        points_list = list(route.points)
        moves_done = 0
        max_moves = 8

        while moves_done < max_moves:
            current_route = self._recalculate_route_times(points_list, orders, start_location, start_time, user_id)
            if not current_route:
                break

            total_now, count_now, _ = self._route_delay_stats(current_route, order_date)
            if count_now == 0:
                return current_route

            delayed_points: List[Tuple[int, RoutePoint, float]] = []
            tol = timedelta(minutes=self.WINDOW_END_TOLERANCE_MINUTES)
            for idx, point in enumerate(current_route.points):
                o = point.order
                if o.delivery_time_start and o.delivery_time_end:
                    we = datetime.combine(order_date, o.delivery_time_end)
                    if point.estimated_arrival > we + tol:
                        d = (point.estimated_arrival - we).total_seconds() / 60.0
                        if d > self.WINDOW_END_TOLERANCE_MINUTES:
                            delayed_points.append((idx, point, d))

            improved = False

            efp_points, efp_ok = self._try_efp_for_delayed(
                points_list, orders, start_location, start_time, user_id, order_date
            )
            if efp_ok and efp_points is not None:
                logger.info("✅ EFP: перенесли опаздывающего в раннюю feasible-позицию")
                points_list = efp_points
                moves_done += 1
                improved = True
                continue

            swap_points, swap_ok = self._try_swap_with_later_window(
                points_list, orders, start_location, start_time, user_id, order_date, total_now, count_now
            )
            if swap_ok and swap_points is not None:
                logger.info("✅ Swap: обмен опаздывающего с заказом с более поздним окном")
                points_list = swap_points
                moves_done += 1
                improved = True
                continue

            tail_points, tail_ok = self._try_tail_permutation(
                points_list, orders, start_location, start_time, user_id, order_date, total_now, count_now
            )
            if tail_ok and tail_points is not None:
                t_total, t_count, _ = self._route_delay_stats(
                    self._recalculate_route_times(tail_points, orders, start_location, start_time, user_id),
                    order_date,
                )
                logger.info(
                    f"✅ Tail permutation: total delay {total_now:.0f}→{t_total:.0f} мин, "
                    f"опозданий {count_now}→{t_count}"
                )
                points_list = tail_points
                moves_done += 1
                improved = True
                continue

            best_points = None
            best_total = total_now
            best_count = count_now
            n = len(points_list)

            for idx, delayed_point, _ in delayed_points:
                candidates = [p for p in range(n) if p != idx]
                for new_pos in candidates:
                    base_points = list(points_list)
                    removed = base_points.pop(idx)
                    new_pos_adj = new_pos - 1 if new_pos > idx else new_pos
                    base_points.insert(new_pos_adj, removed)
                    trial_route = self._recalculate_route_times(
                        base_points, orders, start_location, start_time, user_id
                    )
                    if not trial_route:
                        continue
                    t_total, t_count, t_critical = self._route_delay_stats(trial_route, order_date)
                    if t_critical or t_count > count_now:
                        continue
                    if (t_total, -t_count) < (best_total, -best_count):
                        best_total = t_total
                        best_count = t_count
                        best_points = base_points

                    if new_pos < idx:
                        swap_points = list(points_list)
                        swap_points[idx], swap_points[new_pos] = swap_points[new_pos], swap_points[idx]
                        swap_route = self._recalculate_route_times(
                            swap_points, orders, start_location, start_time, user_id
                        )
                        if not swap_route:
                            continue
                        s_total, s_count, s_critical = self._route_delay_stats(swap_route, order_date)
                        if s_critical or s_count > count_now:
                            continue
                        if (s_total, -s_count) < (best_total, -best_count):
                            best_total = s_total
                            best_count = s_count
                            best_points = swap_points

            if best_points is not None and (best_total < total_now or (best_total == total_now and best_count < count_now)):
                logger.info(
                    f"✅ Move/swap: total delay {total_now:.0f}→{best_total:.0f} мин, "
                    f"опозданий {count_now}→{best_count}"
                )
                points_list = best_points
                moves_done += 1
                improved = True
                continue

            block_points, block_ok = self._try_block_move(
                points_list, orders, start_location, start_time, user_id, order_date,
                total_now, count_now, delayed_points,
            )
            if block_ok and block_points is not None:
                b_total, b_count, _ = self._route_delay_stats(
                    self._recalculate_route_times(block_points, orders, start_location, start_time, user_id),
                    order_date,
                )
                logger.info(
                    f"✅ Block move: total delay {total_now:.0f}→{b_total:.0f} мин, "
                    f"опозданий {count_now}→{b_count}"
                )
                points_list = block_points
                moves_done += 1
                improved = True
                continue

            if not improved:
                break

        final_route = self._recalculate_route_times(points_list, orders, start_location, start_time, user_id)
        return final_route if final_route else route
    
    def _optimize_subroute_by_time_windows(
        self,
        rescue_orders: List[Order],
        start_location: Tuple[float, float],
        start_time: datetime,
        order_date,
        user_id: Optional[int] = None
    ) -> Optional[List[Order]]:
        """
        Специализированная оптимизация небольшого подмаршрута по временным окнам.
        Полный перебор с отсечением по суммарному опозданию для 5–7 заказов.
        """
        if not rescue_orders:
            return None
        
        max_exact = 8
        n = len(rescue_orders)
        
        service_time_minutes = 10
        if user_id:
            try:
                user_settings = self.settings_service.get_settings(user_id)
                service_time_minutes = user_settings.service_time_minutes
            except Exception:
                pass
        
        def eval_sequence(seq: List[Order]) -> Tuple[float, float]:
            current_location = start_location
            current_time = start_time
            total_delay = 0.0
            total_distance = 0.0
            
            for order in seq:
                try:
                    distance, travel_time = self.maps_service.get_route_sync(
                        current_location[0], current_location[1],
                        order.latitude, order.longitude,
                        user_id=user_id
                    )
                except Exception as e:
                    logger.warning(f"⚠️ Ошибка маршрута для rescue-заказа {order.order_number}: {e}")
                    return float("inf"), float("inf")
                
                arrival_time = current_time + timedelta(minutes=travel_time)
                
                if order.delivery_time_start and order.delivery_time_end:
                    window_start = datetime.combine(order_date, order.delivery_time_start)
                    window_end = datetime.combine(order_date, order.delivery_time_end)
                    
                    if arrival_time < window_start:
                        arrival_time = window_start
                    if arrival_time > window_end:
                        delay = (arrival_time - window_end).total_seconds() / 60.0
                        total_delay += delay
                
                total_distance += distance
                current_location = (order.latitude, order.longitude)
                current_time = arrival_time + timedelta(minutes=service_time_minutes)
            
            return total_delay, total_distance
        
        best_seq: Optional[List[Order]] = None
        best_total_delay = float("inf")
        best_distance = float("inf")
        
        if n <= max_exact:
            for perm in itertools.permutations(rescue_orders):
                total_delay, total_distance = eval_sequence(list(perm))
                if total_delay < best_total_delay or (
                    total_delay == best_total_delay and total_distance < best_distance
                ):
                    best_total_delay = total_delay
                    best_distance = total_distance
                    best_seq = list(perm)
        else:
            # Эвристика: раньше конец окна, уже окно — раньше в последовательности
            def _rescue_order_key(o):
                if not o.delivery_time_end:
                    return (float("inf"), 0)
                end_ts = datetime.combine(order_date, o.delivery_time_end).timestamp()
                if not o.delivery_time_start:
                    return (end_ts, 0)
                start_dt = datetime.combine(order_date, o.delivery_time_start)
                end_dt = datetime.combine(order_date, o.delivery_time_end)
                duration_min = (end_dt - start_dt).total_seconds() / 60.0
                return (end_ts, -duration_min)
            heuristic_seq = sorted(rescue_orders, key=_rescue_order_key)
            total_delay, total_distance = eval_sequence(heuristic_seq)
            if total_delay < float("inf"):
                best_seq = heuristic_seq
                best_total_delay = total_delay
                best_distance = total_distance
        
        return best_seq
    
    def _rescue_feasibility(
        self,
        route: OptimizedRoute,
        orders: List[Order],
        start_location: Tuple[float, float],
        start_time: datetime,
        user_id: Optional[int] = None
    ) -> OptimizedRoute:
        """
        Фаза спасения достижимости: перестраиваем небольшой подмаршрут вокруг
        устойчиво опаздывающих заказов, почти игнорируя километраж.
        """
        if not route or not route.points:
            return route
        
        order_date = start_time.date()
        total_now, count_now, _ = self._route_delay_stats(route, order_date)
        if count_now == 0:
            return route
        
        # Собираем опаздывающие заказы
        late_points: List[Tuple[int, RoutePoint, float]] = []
        for idx, point in enumerate(route.points):
            o = point.order
            if o.delivery_time_start and o.delivery_time_end:
                we = datetime.combine(order_date, o.delivery_time_end)
                if point.estimated_arrival > we:
                    d = (point.estimated_arrival - we).total_seconds() / 60.0
                    if d > 0:
                        late_points.append((idx, point, d))
        
        if not late_points:
            return route
        
        late_points.sort(key=lambda x: x[2], reverse=True)
        
        n = len(route.points)
        max_rescue = 8
        rescue_indices: set[int] = set()
        
        # Опаздывающие и соседи по маршруту
        for idx, _, _ in late_points:
            for offset in range(-2, 3):
                j = idx + offset
                if 0 <= j < n:
                    rescue_indices.add(j)
        
        # Опаздывающие с более ранним концом окна: включаем все заказы с тем же или более
        # ранним window_end, чтобы переставить подмаршрут (узкие/ранние окна — вовремя)
        latest_late_window_end = None
        for idx, point, _ in late_points:
            o = point.order
            if o.delivery_time_end:
                we = datetime.combine(order_date, o.delivery_time_end)
                if latest_late_window_end is None or we < latest_late_window_end:
                    latest_late_window_end = we
        if latest_late_window_end is not None:
            for idx in range(n):
                o = route.points[idx].order
                if o.delivery_time_end:
                    we = datetime.combine(order_date, o.delivery_time_end)
                    if we <= latest_late_window_end:
                        rescue_indices.add(idx)
        
        # Ограничиваем размер; при расширении по window_end разрешаем до 12
        max_rescue_after_expand = 12
        if len(rescue_indices) > max_rescue_after_expand:
            rescue_indices = set(sorted(rescue_indices)[:max_rescue_after_expand])
        elif len(rescue_indices) > max_rescue:
            pass  # оставляем все (важнее охватить заказы с тем же/ранним концом окна)
        
        if not rescue_indices:
            return route
        
        rescue_indices_sorted = sorted(rescue_indices)
        prefix_end = rescue_indices_sorted[0]
        
        prefix_points = route.points[:prefix_end]
        rescue_orders = [route.points[i].order for i in rescue_indices_sorted]
        tail_points = [
            route.points[i]
            for i in range(prefix_end, n)
            if i not in rescue_indices
        ]
        
        # Определяем старт для rescue-подмаршрута
        if prefix_points:
            last_prefix = prefix_points[-1]
            sub_start_location = (last_prefix.order.latitude, last_prefix.order.longitude)
            service_time_minutes = 10
            if user_id:
                try:
                    user_settings = self.settings_service.get_settings(user_id)
                    service_time_minutes = user_settings.service_time_minutes
                except Exception:
                    pass
            sub_start_time = last_prefix.estimated_arrival + timedelta(minutes=service_time_minutes)
        else:
            sub_start_location = start_location
            sub_start_time = start_time
        
        best_seq = self._optimize_subroute_by_time_windows(
            rescue_orders, sub_start_location, sub_start_time, order_date, user_id
        )
        if not best_seq:
            return route
        
        # Собираем общий порядок заказов: префикс + rescue + хвост
        combined_orders: List[Order] = []
        for p in prefix_points:
            combined_orders.append(p.order)
        combined_orders.extend(best_seq)
        for p in tail_points:
            combined_orders.append(p.order)
        
        # Оборачиваем в временные точки для пересчёта
        dummy_points = [
            RoutePoint(order=o, estimated_arrival=start_time, distance_from_previous=0.0, time_from_previous=0.0)
            for o in combined_orders
        ]
        new_route = self._recalculate_route_times(dummy_points, orders, start_location, start_time, user_id)
        if not new_route or not new_route.points:
            return route
        
        new_total, new_count, new_critical = self._route_delay_stats(new_route, order_date)
        if new_critical:
            return route
        
        if new_count == 0 and count_now > 0:
            logger.info(
                f"✅ Rescue: полностью устранили опоздания ({count_now}→0, total {total_now:.0f}→0 мин)"
            )
            return new_route
        
        if new_count <= count_now and (
            new_total < total_now or (new_total == total_now and new_count < count_now)
        ):
            logger.info(
                f"✅ Rescue: улучшили опоздания count {count_now}→{new_count}, "
                f"total {total_now:.0f}→{new_total:.0f} мин"
            )
            return new_route
        
        return route
    
    def _recalculate_route_times(
        self,
        points_list: List[RoutePoint],
        orders: List[Order],
        start_location: Tuple[float, float],
        start_time: datetime,
        user_id: int = None
    ) -> Optional[OptimizedRoute]:
        """
        Пересчитать времена прибытия для списка точек маршрута
        
        Args:
            points_list: Список точек маршрута
            orders: Список заказов (для получения полной информации)
            start_location: Точка старта
            start_time: Время старта
            user_id: ID пользователя
            
        Returns:
            Оптимизированный маршрут с пересчитанными временами
        """
        if not points_list:
            return None
        
        recalculated_points = []
        total_distance = 0.0
        total_time = 0.0
        current_location = start_location
        current_time = start_time
        order_date = start_time.date()
        
        # Время обслуживания
        service_time_minutes = 10
        if user_id:
            user_settings = self.settings_service.get_settings(user_id)
            service_time_minutes = user_settings.service_time_minutes
        
        for point in points_list:
            order = point.order
            
            try:
                # Получаем расстояние и время
                distance, travel_time = self.maps_service.get_route_sync(
                    current_location[0], current_location[1],
                    order.latitude, order.longitude,
                    user_id=user_id
                )
                
                # Время прибытия
                arrival_time = current_time + timedelta(minutes=travel_time)
                
                # Проверяем временное окно
                if order.delivery_time_start and order.delivery_time_end:
                    window_start = datetime.combine(order_date, order.delivery_time_start)
                    window_end = datetime.combine(order_date, order.delivery_time_end)
                    
                    # Если приедем раньше - ждем
                    if arrival_time < window_start:
                        wait_time = (window_start - arrival_time).total_seconds() / 60.0
                        arrival_time = window_start
                    
                    # Проверяем опоздание (но не корректируем, только фиксируем)
                    if arrival_time > window_end:
                        delay = (arrival_time - window_end).total_seconds() / 60.0
                        if delay > self.MAX_DELAY_MINUTES:
                            logger.debug(f"   ⚠️ Заказ {order.order_number}: опоздание {delay:.0f} мин после пересчета")
                
                # Создаем точку маршрута
                recalculated_point = RoutePoint(
                    order=order,
                    estimated_arrival=arrival_time,
                    distance_from_previous=distance,
                    time_from_previous=travel_time
                )
                recalculated_points.append(recalculated_point)
                
                # Обновляем метрики
                total_distance += distance
                total_time += travel_time + service_time_minutes
                
                # Переходим к следующей точке
                current_location = (order.latitude, order.longitude)
                current_time = arrival_time + timedelta(minutes=service_time_minutes)
                
            except Exception as e:
                logger.error(f"❌ Ошибка пересчета для заказа {order.order_number}: {e}")
                return None
        
        return OptimizedRoute(
            points=recalculated_points,
            total_distance=total_distance,
            total_time=total_time,
            estimated_completion=current_time
        )
