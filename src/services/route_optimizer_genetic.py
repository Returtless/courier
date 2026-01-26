"""
Генетический алгоритм оптимизации маршрутов
Использует эволюционный подход для построения оптимальных маршрутов с учетом временных окон
"""
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
    CLUSTER_RADIUS_KM = 1.0  # Радиус кластеризации
    
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
        
        # Стратегия 1: Случайные перестановки (50%)
        for _ in range(self.POPULATION_SIZE // 2):
            chromosome = list(range(num_orders))
            random.shuffle(chromosome)
            population.append(chromosome)
        
        # Стратегия 2: Сортировка по началу временного окна (25%)
        for _ in range(self.POPULATION_SIZE // 4):
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
        
        # Стратегия 3: Сортировка по концу временного окна (для предотвращения опозданий)
        for _ in range(self.POPULATION_SIZE // 8):
            order_date = start_time.date()
            sorted_indices = sorted(
                range(num_orders),
                key=lambda i: (
                    datetime.combine(order_date, orders[i].delivery_time_end).timestamp()
                    if orders[i].delivery_time_end else float('inf')
                )
            )
            # Добавляем небольшую случайность
            chromosome = sorted_indices.copy()
            for _ in range(random.randint(0, num_orders // 4)):
                i, j = random.sample(range(num_orders), 2)
                chromosome[i], chromosome[j] = chromosome[j], chromosome[i]
            population.append(chromosome)
        
        # Стратегия 4: Greedy nearest neighbor с учетом временных окон
        remaining_count = self.POPULATION_SIZE - len(population)
        for _ in range(remaining_count):
            chromosome = self._greedy_nearest_neighbor(orders, start_location, start_time)
            population.append(chromosome)
        
        return population
    
    def _greedy_nearest_neighbor(
        self,
        orders: List[Order],
        start_location: Tuple[float, float],
        start_time: datetime = None
    ) -> List[int]:
        """
        Greedy алгоритм ближайшего соседа с учетом временных окон для генерации начальной популяции
        
        Args:
            orders: Список заказов
            start_location: Точка старта
            start_time: Время старта (для учета временных окон)
            
        Returns:
            Хромосома (список индексов)
        """
        num_orders = len(orders)
        if num_orders == 0:
            return []
        
        chromosome = []
        remaining = set(range(num_orders))
        current_location = start_location
        current_time = start_time if start_time else datetime.now()
        order_date = current_time.date()
        
        while remaining:
            best_idx = None
            best_score = float('inf')
            
            for idx in remaining:
                order = orders[idx]
                distance = self._haversine_distance(
                    current_location[0], current_location[1],
                    order.latitude, order.longitude
                )
                
                # Базовый score = расстояние
                score = distance
                
                # Бонус за ранние окна (приоритет заказам с ранними окнами)
                if order.delivery_time_end and start_time:
                    window_end = datetime.combine(order_date, order.delivery_time_end)
                    # Если окно заканчивается рано (< 13:00), уменьшаем score
                    if window_end.hour < 13:
                        score *= 0.5  # Приоритет ранним окнам
                
                if score < best_score:
                    best_score = score
                    best_idx = idx
            
            if best_idx is not None:
                chromosome.append(best_idx)
                remaining.remove(best_idx)
                current_location = (orders[best_idx].latitude, orders[best_idx].longitude)
        
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
        early_arrivals = 0  # Количество ранних прибытий
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
                
                # Раннее прибытие - КРИТИЧЕСКОЕ нарушение
                if arrival_time < window_start:
                    early_arrivals += 1
                    # Ждем до начала окна
                    wait_time = (window_start - arrival_time).total_seconds() / 60.0
                    arrival_time = window_start
                    total_time += wait_time
                
                # Позднее прибытие
                if arrival_time > window_end:
                    violations += 1
                    delay = (arrival_time - window_end).total_seconds() / 60.0
                    # Критическое опоздание > 10 минут - очень большой штраф
                    if delay > self.MAX_DELAY_MINUTES:
                        # Экспоненциальный штраф за критические опоздания
                        total_delay += delay * (1 + (delay - self.MAX_DELAY_MINUTES) * 10)
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
        
        # Фитнес = взвешенная сумма всех факторов
        # КРИТИЧНО: Увеличиваем штрафы за опоздания, особенно за критические (>10 мин)
        fitness = (
            total_distance * 0.2 +                    # Расстояние (20%)
            total_time * 0.1 +                        # Время (10%)
            violations * 50000 +                      # Штраф за нарушения окон (очень большой вес!)
            total_delay * 1000 +                       # Штраф за опоздания (1000x, было 100x)
            early_arrivals * 5000 +                    # Штраф за ранние прибытия (5000x)
            manual_time_violations * 2000              # Штраф за нарушение manual_arrival_time (2000x)
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
        
        # Умная мутация для исправления опозданий (20%)
        if mutation_type < 0.2 and orders and start_time:
            return self._smart_mutation_for_delays(chromosome, orders, start_time)
        
        elif mutation_type < 0.6:
            # Swap Mutation (40%)
            i, j = random.sample(range(len(chromosome)), 2)
            mutated = chromosome.copy()
            mutated[i], mutated[j] = mutated[j], mutated[i]
            return mutated
        
        elif mutation_type < 0.9:
            # Inversion Mutation (30%)
            if len(chromosome) >= 2:
                start = random.randint(0, len(chromosome) - 2)
                end = random.randint(start + 1, len(chromosome) - 1)
                mutated = chromosome.copy()
                mutated[start:end+1] = reversed(mutated[start:end+1])
                return mutated
        
        else:
            # Insertion Mutation (10%)
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
        
        # Находим заказы с ранними окнами (которые могут опоздать)
        early_window_orders = []
        for idx in chromosome:
            if idx < len(orders):
                order = orders[idx]
                if order.delivery_time_end:
                    window_end = datetime.combine(order_date, order.delivery_time_end)
                    # Окна, которые заканчиваются до 13:00 - приоритетные
                    if window_end.hour < 13:
                        early_window_orders.append((idx, window_end))
        
        if early_window_orders:
            # Сортируем по времени окончания окна
            early_window_orders.sort(key=lambda x: x[1])
            
            # Перемещаем первые 1-2 заказа с ранними окнами ближе к началу
            for order_idx, _ in early_window_orders[:min(2, len(early_window_orders))]:
                if order_idx in mutated:
                    # Удаляем из текущей позиции
                    current_pos = mutated.index(order_idx)
                    mutated.pop(current_pos)
                    # Вставляем ближе к началу (но не в самое начало, чтобы сохранить разнообразие)
                    new_pos = random.randint(0, min(3, len(mutated)))
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
        
        return OptimizedRoute(
            points=points,
            total_distance=total_distance,
            total_time=total_time,
            estimated_completion=current_time
        )
