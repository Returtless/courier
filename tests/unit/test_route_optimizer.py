"""
Unit-тесты для RouteOptimizer (оптимизация маршрута)
"""
import pytest
from datetime import datetime, time, timedelta
from unittest.mock import Mock, patch
import numpy as np
from src.services.route_optimizer import RouteOptimizer
from src.models.order import Order


@pytest.mark.unit
class TestRouteOptimizerBasic:
    """Базовые тесты оптимизатора маршрутов"""
    
    def test_optimizer_initialization(self, mock_maps_service):
        """Инициализация оптимизатора"""
        optimizer = RouteOptimizer(mock_maps_service)
        
        assert optimizer.maps_service == mock_maps_service
        assert optimizer.settings_service is not None
    
    def test_build_matrices(self, mock_maps_service):
        """Построение матриц расстояний и времени"""
        optimizer = RouteOptimizer(mock_maps_service)
        
        locations = [
            (55.7558, 37.6173),  # Старт
            (55.7522, 37.5989),  # Точка 1
            (55.7505, 37.6175)   # Точка 2
        ]
        
        # Настройка мока
        mock_maps_service.get_route_distance_matrix_sync.return_value = (
            [[0, 1000, 2000], [1000, 0, 1500], [2000, 1500, 0]],  # distance (meters)
            [[0, 5, 10], [5, 0, 8], [10, 8, 0]]  # time (minutes)
        )
        
        distance_matrix, time_matrix = optimizer._build_matrices(locations)
        
        # Проверяем формат
        assert distance_matrix.shape == (3, 3)
        assert time_matrix.shape == (3, 3)
        assert isinstance(distance_matrix, np.ndarray)
        assert isinstance(time_matrix, np.ndarray)
    
    def test_optimize_empty_orders(self, mock_maps_service):
        """Оптимизация пустого списка заказов"""
        optimizer = RouteOptimizer(mock_maps_service)
        
        result = optimizer.optimize_route_sync(
            orders=[],
            start_location=(55.7558, 37.6173),
            start_time=datetime(2025, 12, 15, 9, 0),
            user_id=123
        )
        
        assert result.points == []
        assert result.total_distance == 0
        assert result.total_time == 0


@pytest.mark.unit
class TestRouteOptimizerWithOrders:
    """Тесты оптимизации с заказами"""
    
    def test_optimize_single_order(self, mock_maps_service):
        """Оптимизация с одним заказом"""
        optimizer = RouteOptimizer(mock_maps_service)
        
        order = Order(
            customer_name="Клиент 1",
            phone="+79991111111",
            address="Москва, Тверская 1",
            latitude=55.7558,
            longitude=37.6173
        )
        
        mock_maps_service.get_route_distance_matrix_sync.return_value = (
            [[0, 1000], [1000, 0]],
            [[0, 10], [10, 0]]
        )
        
        result = optimizer.optimize_route_sync(
            orders=[order],
            start_location=(55.7558, 37.6173),
            start_time=datetime(2025, 12, 15, 9, 0),
            user_id=123
        )
        
        assert len(result.points) == 1
        assert result.points[0].order == order
        assert result.total_distance > 0
    
    def test_optimize_multiple_orders(self, mock_maps_service):
        """Оптимизация с несколькими заказами"""
        optimizer = RouteOptimizer(mock_maps_service)
        
        orders = [
            Order(
                customer_name="Клиент 1",
                phone="+79991111111",
                address="Москва, Тверская 1",
                latitude=55.7558,
                longitude=37.6173
            ),
            Order(
                customer_name="Клиент 2",
                phone="+79992222222",
                address="Москва, Арбат 1",
                latitude=55.7522,
                longitude=37.5989
            )
        ]
        
        mock_maps_service.get_route_distance_matrix_sync.return_value = (
            [[0, 1000, 2000], [1000, 0, 1500], [2000, 1500, 0]],
            [[0, 5, 10], [5, 0, 8], [10, 8, 0]]
        )
        
        result = optimizer.optimize_route_sync(
            orders=orders,
            start_location=(55.7558, 37.6173),
            start_time=datetime(2025, 12, 15, 9, 0),
            user_id=123
        )
        
        assert len(result.points) == 2
        assert result.total_distance > 0


@pytest.mark.unit
class TestRouteOptimizerWithManualTimes:
    """Тесты оптимизации с ручными временами (КРИТИЧНО!)"""
    
    def test_optimize_with_manual_arrival_time(self, mock_maps_service, mock_settings_service):
        """Оптимизация с ручным временем прибытия"""
        optimizer = RouteOptimizer(mock_maps_service)
        optimizer.settings_service = mock_settings_service
        
        # Заказ с ручным временем прибытия
        order_with_manual_time = Order(
            order_number="12345",
            customer_name="Клиент 1",
            phone="+79991111111",
            address="Москва, Тверская 1",
            latitude=55.7558,
            longitude=37.6173,
            manual_arrival_time=datetime(2025, 12, 15, 11, 0)  # Жесткое ограничение!
        )
        
        # Обычный заказ без ограничений
        order_without_manual = Order(
            order_number="67890",
            customer_name="Клиент 2",
            phone="+79992222222",
            address="Москва, Арбат 1",
            latitude=55.7522,
            longitude=37.5989
        )
        
        mock_maps_service.get_route_distance_matrix_sync.return_value = (
            [[0, 1000, 2000], [1000, 0, 1500], [2000, 1500, 0]],
            [[0, 10, 20], [10, 0, 15], [20, 15, 0]]
        )
        
        result = optimizer.optimize_route_sync(
            orders=[order_with_manual_time, order_without_manual],
            start_location=(55.7558, 37.6173),
            start_time=datetime(2025, 12, 15, 9, 0),
            user_id=123
        )
        
        assert len(result.points) == 2
        
        # Находим точку с ручным временем
        manual_point = None
        for point in result.points:
            if point.order.order_number == "12345":
                manual_point = point
                break
        
        assert manual_point is not None
        # Проверяем, что прибытие примерно в указанное время (±5 минут допуск)
        expected_arrival = datetime(2025, 12, 15, 11, 0)
        time_diff = abs((manual_point.estimated_arrival - expected_arrival).total_seconds())
        assert time_diff <= 300  # 5 минут = 300 секунд
    
    def test_optimize_with_delivery_time_window(self, mock_maps_service, mock_settings_service):
        """Оптимизация с временным окном доставки"""
        optimizer = RouteOptimizer(mock_maps_service)
        optimizer.settings_service = mock_settings_service
        
        order = Order(
            customer_name="Клиент 1",
            phone="+79991111111",
            address="Москва, Тверская 1",
            latitude=55.7558,
            longitude=37.6173,
            delivery_time_window="10:00 - 12:00"
        )
        
        mock_maps_service.get_route_distance_matrix_sync.return_value = (
            [[0, 1000], [1000, 0]],
            [[0, 5], [5, 0]]
        )
        
        result = optimizer.optimize_route_sync(
            orders=[order],
            start_location=(55.7558, 37.6173),
            start_time=datetime(2025, 12, 15, 9, 0),
            user_id=123
        )
        
        # Проверяем, что прибытие в пределах окна
        arrival = result.points[0].estimated_arrival
        assert time(10, 0) <= arrival.time() <= time(12, 0)
    
    def test_manual_arrival_time_priority_over_time_window(self, mock_maps_service, mock_settings_service):
        """manual_arrival_time имеет приоритет над delivery_time_window"""
        optimizer = RouteOptimizer(mock_maps_service)
        optimizer.settings_service = mock_settings_service
        
        # Заказ с ОБОИМИ ограничениями
        order = Order(
            order_number="12345",
            customer_name="Клиент 1",
            phone="+79991111111",
            address="Москва, Тверская 1",
            latitude=55.7558,
            longitude=37.6173,
            delivery_time_window="10:00 - 12:00",  # Окно доставки
            manual_arrival_time=datetime(2025, 12, 15, 11, 30)  # Ручное время (приоритет!)
        )
        
        mock_maps_service.get_route_distance_matrix_sync.return_value = (
            [[0, 1000], [1000, 0]],
            [[0, 10], [10, 0]]
        )
        
        result = optimizer.optimize_route_sync(
            orders=[order],
            start_location=(55.7558, 37.6173),
            start_time=datetime(2025, 12, 15, 9, 0),
            user_id=123
        )
        
        # Проверяем, что используется ручное время (11:30), а не начало окна (10:00)
        arrival = result.points[0].estimated_arrival
        expected = datetime(2025, 12, 15, 11, 30)
        time_diff = abs((arrival - expected).total_seconds())
        assert time_diff <= 300  # ±5 минут


@pytest.mark.unit
class TestRouteOptimizerTimeCalculations:
    """Тесты расчетов времени в маршруте"""
    
    def test_estimated_arrival_calculation(self, mock_maps_service, mock_settings_service):
        """Расчет времени прибытия с учетом времени обслуживания"""
        optimizer = RouteOptimizer(mock_maps_service)
        optimizer.settings_service = mock_settings_service
        
        order = Order(
            customer_name="Клиент 1",
            phone="+79991111111",
            address="Москва, Тверская 1",
            latitude=55.7558,
            longitude=37.6173
        )
        
        # Время в пути: 10 минут
        mock_maps_service.get_route_distance_matrix_sync.return_value = (
            [[0, 1000], [1000, 0]],
            [[0, 10], [10, 0]]
        )
        
        start_time = datetime(2025, 12, 15, 9, 0)
        
        result = optimizer.optimize_route_sync(
            orders=[order],
            start_location=(55.7558, 37.6173),
            start_time=start_time,
            user_id=123
        )
        
        # Ожидаемое время: start_time + travel_time + service_time
        # 9:00 + 10 мин (путь) + 10 мин (обслуживание) = 9:20
        expected_arrival = start_time + timedelta(minutes=20)
        
        actual_arrival = result.points[0].estimated_arrival
        
        # Допускаем небольшую погрешность
        time_diff = abs((actual_arrival - expected_arrival).total_seconds())
        assert time_diff <= 60  # 1 минута


@pytest.mark.unit
class TestRouteOptimizerEdgeCases:
    """Тесты граничных случаев"""
    
    def test_order_without_coordinates(self, mock_maps_service):
        """Заказ без координат (требуется геокодирование)"""
        optimizer = RouteOptimizer(mock_maps_service)
        
        order = Order(
            customer_name="Клиент 1",
            phone="+79991111111",
            address="Москва, Тверская 1",
            latitude=None,  # Нет координат
            longitude=None
        )
        
        # Мок геокодирования
        mock_maps_service.geocode_address_sync.return_value = (55.7558, 37.6173, "gis_123")
        mock_maps_service.get_route_distance_matrix_sync.return_value = (
            [[0, 1000], [1000, 0]],
            [[0, 10], [10, 0]]
        )
        
        result = optimizer.optimize_route_sync(
            orders=[order],
            start_location=(55.7558, 37.6173),
            start_time=datetime(2025, 12, 15, 9, 0),
            user_id=123
        )
        
        # Проверяем, что геокодирование было вызвано
        assert mock_maps_service.geocode_address_sync.called
        
        # Проверяем, что координаты установлены
        assert result.points[0].order.latitude == 55.7558
        assert result.points[0].order.longitude == 37.6173
    
    def test_impossible_time_constraints(self, mock_maps_service, mock_settings_service):
        """Невыполнимые временные ограничения"""
        optimizer = RouteOptimizer(mock_maps_service)
        optimizer.settings_service = mock_settings_service
        
        # Заказ с окном доставки, которое уже прошло
        order = Order(
            customer_name="Клиент 1",
            phone="+79991111111",
            address="Москва, Тверская 1",
            latitude=55.7558,
            longitude=37.6173,
            delivery_time_window="08:00 - 09:00"  # Уже прошло!
        )
        
        mock_maps_service.get_route_distance_matrix_sync.return_value = (
            [[0, 1000], [1000, 0]],
            [[0, 30], [30, 0]]  # 30 минут в пути
        )
        
        start_time = datetime(2025, 12, 15, 9, 0)  # Начало в 9:00
        
        # Оптимизатор должен справиться, но выдать предупреждение
        result = optimizer.optimize_route_sync(
            orders=[order],
            start_location=(55.7558, 37.6173),
            start_time=start_time,
            user_id=123
        )
        
        # Маршрут построен, хоть и с нарушением окна
        assert len(result.points) == 1

