import threading
import time
import logging
from typing import Dict, List, Optional, Callable
from datetime import datetime, timedelta
from src.services.maps_service import MapsService
from src.models.order import Order, OptimizedRoute

logger = logging.getLogger(__name__)


class TrafficMonitor:
    """
    Сервис мониторинга пробок в реальном времени
    Поддерживает несколько пользователей одновременно
    """

    def __init__(self, maps_service: MapsService, check_interval_minutes: int = 5):
        self.maps_service = maps_service
        self.check_interval = check_interval_minutes * 60  # convert to seconds
        self.traffic_threshold = 1.5  # 50% increase in time
        self.callbacks: List[Callable] = []
        
        # Хранилище данных мониторинга для каждого пользователя
        # user_id -> {route, orders, start_location, start_time, last_check_time, is_monitoring, thread}
        self.user_monitors: Dict[int, Dict] = {}
        self.monitor_lock = threading.Lock()  # Блокировка для потокобезопасности

    def start_monitoring(
        self,
        user_id: int,
        route: OptimizedRoute,
        orders: List[Order],
        start_location,
        start_time: datetime
    ):
        """Начать мониторинг маршрута для конкретного пользователя"""
        with self.monitor_lock:
            # Остановить предыдущий мониторинг для этого пользователя, если был
            if user_id in self.user_monitors:
                self._stop_monitoring_for_user(user_id)
            
            # Создать новую запись мониторинга
            monitor_data = {
                'route': route,
                'orders': orders,
                'start_location': start_location,
                'start_time': start_time,
                'last_check_time': datetime.now(),
                'is_monitoring': True
            }
            
            # Запустить поток мониторинга для этого пользователя
            monitor_thread = threading.Thread(
                target=self._monitor_loop,
                args=(user_id,),
                daemon=True
            )
            monitor_thread.start()
            monitor_data['thread'] = monitor_thread
            
            self.user_monitors[user_id] = monitor_data
            logger.info(f"🚦 Начат мониторинг пробок для user_id={user_id} каждые 5 минут")

    def stop_monitoring(self, user_id: int = None):
        """Остановить мониторинг для конкретного пользователя или всех"""
        with self.monitor_lock:
            if user_id is not None:
                if user_id in self.user_monitors:
                    self._stop_monitoring_for_user(user_id)
                    logger.info(f"🛑 Мониторинг пробок остановлен для user_id={user_id}")
            else:
                # Остановить все мониторинги
                for uid in list(self.user_monitors.keys()):
                    self._stop_monitoring_for_user(uid)
                logger.info("🛑 Все мониторинги пробок остановлены")
    
    def _stop_monitoring_for_user(self, user_id: int):
        """Внутренний метод для остановки мониторинга конкретного пользователя"""
        if user_id in self.user_monitors:
            monitor_data = self.user_monitors[user_id]
            monitor_data['is_monitoring'] = False
            if 'thread' in monitor_data and monitor_data['thread'].is_alive():
                monitor_data['thread'].join(timeout=1)
            del self.user_monitors[user_id]

    def add_callback(self, callback: Callable):
        """Добавить callback для уведомлений о изменениях"""
        self.callbacks.append(callback)

    def _monitor_loop(self, user_id: int):
        """Основной цикл мониторинга для конкретного пользователя"""
        while True:
            with self.monitor_lock:
                if user_id not in self.user_monitors:
                    break
                monitor_data = self.user_monitors[user_id]
                if not monitor_data.get('is_monitoring', False):
                    break
                route = monitor_data['route']
                orders = monitor_data['orders']
                start_location = monitor_data['start_location']
            
            try:
                self._check_traffic_changes(user_id, route, orders, start_location)
                time.sleep(self.check_interval)
            except Exception as e:
                logger.error(f"❌ Ошибка мониторинга пробок для user_id={user_id}: {e}", exc_info=True)
                time.sleep(60)  # Wait 1 minute before retrying

    def _check_traffic_changes(self, user_id: int, route: OptimizedRoute, orders: List[Order], start_location):
        """Проверить изменения в пробках для конкретного пользователя"""
        if not route or not orders:
            return

        logger.debug(f"🔍 Проверяю изменения в пробках для user_id={user_id}...")

        current_time = datetime.now()
        total_current_time = 0
        significant_changes = []

        # Проверить каждую часть маршрута
        for i, point in enumerate(route.points):
            order = point.order

            # Определить предыдущую точку
            prev_location = start_location if i == 0 else (
                route.points[i-1].order.latitude,
                route.points[i-1].order.longitude
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

        # Обновить время последней проверки
        with self.monitor_lock:
            if user_id in self.user_monitors:
                self.user_monitors[user_id]['last_check_time'] = current_time

        # Если есть значительные изменения, уведомить
        if significant_changes:
            self._notify_traffic_changes(user_id, significant_changes, total_current_time)
        else:
            logger.debug(f"✅ Пробки в норме для user_id={user_id}, маршрут оптимален")

    def _notify_traffic_changes(self, user_id: int, changes: List[Dict], total_current_time: float):
        """Уведомить о изменениях в пробках для конкретного пользователя"""
        logger.warning(f"🚨 ОБНАРУЖЕНЫ ИЗМЕНЕНИЯ В ПРОБКАХ для user_id={user_id}!")

        for change in changes:
            order = change['order']
            logger.warning(f"   📍 Заказ {change['step']}: {order.customer_name}")
            logger.warning(f"   🚦 Задержка: {change['delay']:.1f} мин")
            logger.warning(f"   📊 Текущее время: {change['current_time']:.1f} мин")
        # Вызвать callbacks с указанием user_id
        for callback in self.callbacks:
            try:
                callback(user_id, changes, total_current_time)
            except Exception as e:
                logger.error(f"❌ Ошибка callback для user_id={user_id}: {e}", exc_info=True)

    def get_current_traffic_status(self, user_id: int = None) -> Dict:
        """Получить текущий статус пробок для конкретного пользователя или всех"""
        with self.monitor_lock:
            if user_id is not None:
                if user_id in self.user_monitors:
                    monitor_data = self.user_monitors[user_id]
                    return {
                        'is_monitoring': monitor_data.get('is_monitoring', False),
                        'last_check': monitor_data.get('last_check_time').isoformat() if monitor_data.get('last_check_time') else None,
                        'route_points': len(monitor_data.get('route', {}).points) if monitor_data.get('route') else 0,
                        'check_interval_minutes': self.check_interval / 60
                    }
                else:
                    return {
                        'is_monitoring': False,
                        'last_check': None,
                        'route_points': 0,
                        'check_interval_minutes': self.check_interval / 60
                    }
            else:
                # Статус для всех пользователей
                return {
                    'total_monitors': len(self.user_monitors),
                    'active_monitors': sum(1 for m in self.user_monitors.values() if m.get('is_monitoring', False)),
                    'check_interval_minutes': self.check_interval / 60
                }

    def force_recheck(self, user_id: int):
        """Принудительно проверить пробки для конкретного пользователя"""
        with self.monitor_lock:
            if user_id in self.user_monitors and self.user_monitors[user_id].get('is_monitoring', False):
                monitor_data = self.user_monitors[user_id]
                threading.Thread(
                    target=self._check_traffic_changes,
                    args=(user_id, monitor_data['route'], monitor_data['orders'], monitor_data['start_location']),
                    daemon=True
                ).start()
                logger.info(f"🔄 Запущена принудительная проверка пробок для user_id={user_id}")
