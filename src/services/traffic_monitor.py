import threading
import time
from typing import Dict, List, Optional, Callable
from datetime import datetime, timedelta
from src.services.maps_service import MapsService
from src.models.order import Order, OptimizedRoute


class TrafficMonitor:
    """
    Сервис мониторинга пробок в реальном времени
    """

    def __init__(self, maps_service: MapsService, check_interval_minutes: int = 5):
        self.maps_service = maps_service
        self.check_interval = check_interval_minutes * 60  # convert to seconds
        self.is_monitoring = False
        self.monitor_thread: Optional[threading.Thread] = None
        self.current_route: Optional[OptimizedRoute] = None
        self.route_orders: List[Order] = []
        self.start_location = None
        self.start_time: Optional[datetime] = None
        self.last_check_time: Optional[datetime] = None
        self.traffic_threshold = 1.5  # 50% increase in time
        self.callbacks: List[Callable] = []

    def start_monitoring(
        self,
        route: OptimizedRoute,
        orders: List[Order],
        start_location,
        start_time: datetime
    ):
        """Начать мониторинг маршрута"""
        if self.is_monitoring:
            self.stop_monitoring()

        self.current_route = route
        self.route_orders = orders
        self.start_location = start_location
        self.start_time = start_time
        self.last_check_time = datetime.now()
        self.is_monitoring = True

        self.monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self.monitor_thread.start()

        print("🚦 Начат мониторинг пробок каждые 5 минут")

    def stop_monitoring(self):
        """Остановить мониторинг"""
        self.is_monitoring = False
        if self.monitor_thread and self.monitor_thread.is_alive():
            self.monitor_thread.join(timeout=1)
        print("🛑 Мониторинг пробок остановлен")

    def add_callback(self, callback: Callable):
        """Добавить callback для уведомлений о изменениях"""
        self.callbacks.append(callback)

    def _monitor_loop(self):
        """Основной цикл мониторинга"""
        while self.is_monitoring:
            try:
                self._check_traffic_changes()
                time.sleep(self.check_interval)
            except Exception as e:
                print(f"❌ Ошибка мониторинга пробок: {e}")
                time.sleep(60)  # Wait 1 minute before retrying

    def _check_traffic_changes(self):
        """Проверить изменения в пробках"""
        if not self.current_route or not self.route_orders:
            return

        print("🔍 Проверяю изменения в пробках...")

        current_time = datetime.now()
        total_current_time = 0
        significant_changes = []

        # Проверить каждую часть маршрута
        for i, point in enumerate(self.current_route.points):
            order = point.order

            # Определить предыдущую точку
            prev_location = self.start_location if i == 0 else (
                self.current_route.points[i-1].order.latitude,
                self.current_route.points[i-1].order.longitude
            )

            if prev_location and order.latitude and order.longitude:
                # Проверить текущее время маршрута
                distance, travel_time = self.maps_service.get_route_sync(
                    prev_location[0], prev_location[1],
                    order.latitude, order.longitude
                )

                # Сравнить с запланированным временем
                planned_time = point.time_from_previous
                current_ratio = travel_time / planned_time if planned_time > 0 else 1

                if current_ratio > self.traffic_threshold:
                    delay_minutes = travel_time - planned_time
                    significant_changes.append({
                        'order': order,
                        'planned_time': planned_time,
                        'current_time': travel_time,
                        'delay': delay_minutes,
                        'ratio': current_ratio,
                        'step': i + 1
                    })

                total_current_time += travel_time + 10  # +10 минут на доставку

        self.last_check_time = current_time

        # Если есть значительные изменения, уведомить
        if significant_changes:
            self._notify_traffic_changes(significant_changes, total_current_time)
        else:
            print("✅ Пробки в норме, маршрут оптимален")

    def _notify_traffic_changes(self, changes: List[Dict], total_current_time: float):
        """Уведомить о изменениях в пробках"""
        print("🚨 ОБНАРУЖЕНЫ ИЗМЕНЕНИЯ В ПРОБКАХ!")

        for change in changes:
            order = change['order']
            print(f"   📍 Заказ {change['step']}: {order.customer_name}")
            print(f"   🚦 Задержка: {change['delay']:.1f} мин")
            print(f"   📊 Текущее время: {change['current_time']:.1f} мин")
        # Вызвать callbacks
        for callback in self.callbacks:
            try:
                callback(changes, total_current_time)
            except Exception as e:
                print(f"❌ Ошибка callback: {e}")

    def get_current_traffic_status(self) -> Dict:
        """Получить текущий статус пробок"""
        return {
            'is_monitoring': self.is_monitoring,
            'last_check': self.last_check_time.isoformat() if self.last_check_time else None,
            'route_points': len(self.current_route.points) if self.current_route else 0,
            'check_interval_minutes': self.check_interval / 60
        }

    def force_recheck(self):
        """Принудительно проверить пробки"""
        if self.is_monitoring:
            threading.Thread(target=self._check_traffic_changes, daemon=True).start()
            print("🔄 Запущена принудительная проверка пробок")
