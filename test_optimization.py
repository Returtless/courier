#!/usr/bin/env python3
"""
Тестовый скрипт для проверки OR-Tools оптимизации маршрутов
"""

from datetime import datetime
from src.services.maps_service import MapsService
from src.services.route_optimizer import RouteOptimizer
from src.models.order import Order


def test_or_tools_optimization():
    """Тест OR-Tools оптимизации"""
    print("🧮 Тестирование OR-Tools оптимизации...")

    # Создание тестовых заказов с координатами
    orders = [
        Order("Иван Петров", "+7-999-123-45-67", "Москва, ул. Арбат, 15", "Звонок в домофон"),
        Order("Анна Сидорова", "+7-999-234-56-78", "Москва, ул. Новый Арбат, 25", "Оставить у двери"),
        Order("Михаил Иванов", "+7-999-345-67-89", "Москва, ул. Садовое кольцо, 5", "Подъезд 3"),
        Order("Елена Козлова", "+7-999-456-78-90", "Москва, ул. Пушкина, 15", "Точное время"),
        Order("Дмитрий Смирнов", "+7-999-567-89-01", "Москва, пр. Мира, 50", "Офисное здание"),
    ]

    # Присвоим координаты для тестирования
    coordinates = [
        (55.7485, 37.5880),  # Арбат
        (55.7512, 37.5974),  # Новый Арбат
        (55.7616, 37.6209),  # Садовое кольцо
        (55.7656, 37.6057),  # Пушкина
        (55.7764, 37.6367),  # пр. Мира
    ]

    for i, coord in enumerate(coordinates):
        orders[i].latitude = coord[0]
        orders[i].longitude = coord[1]

    # Точка старта (Красная площадь)
    start_location = (55.7558, 37.6173)
    start_time = datetime.now().replace(hour=9, minute=0, second=0, microsecond=0)

    print(f"🏭 Точка старта: {start_location}")
    print(f"🕐 Время старта: {start_time.strftime('%H:%M')}")
    print(f"📦 Заказов: {len(orders)}")
    print()

    try:
        maps_service = MapsService()
        route_optimizer = RouteOptimizer(maps_service)

        print("⏳ Запуск оптимизации с OR-Tools...")
        optimized_route = route_optimizer.optimize_route_sync(
            orders, start_location, start_time
        )

        print("\n✅ ОПТИМИЗАЦИЯ ЗАВЕРШЕНА!")
        print("=" * 50)
        print(f"📊 Заказов: {len(optimized_route.points)}")
        print(f"📏 Общее расстояние: {optimized_route.total_distance:.1f} км")
        print(f"⏱️ Общее время: {optimized_route.total_time:.0f} мин")
        print(f"🏁 Завершение: {optimized_route.estimated_completion.strftime('%H:%M')}")
        print()

        print("🚚 ОПТИМАЛЬНЫЙ МАРШРУТ (OR-Tools):")
        print("=" * 50)
        for i, point in enumerate(optimized_route.points, 1):
            order = point.order
            print(f"{i}. {order.customer_name}")
            print(f"   📍 {order.address}")
            print(f"   📞 {order.phone}")
            print(f"   ⏰ Прибытие: {point.estimated_arrival.strftime('%H:%M')}")
            print(f"   📏 Расстояние: {point.distance_from_previous:.1f} км")
            print(f"   ⏱️ Время в пути: {point.time_from_previous:.0f} мин")
            if order.comment:
                print(f"   💬 {order.comment}")
            print()

        return optimized_route

    except Exception as e:
        print(f"❌ Ошибка оптимизации: {e}")
        import traceback
        traceback.print_exc()
        return None


def test_traffic_monitoring():
    """Тест мониторинга пробок"""
    print("\n🚦 Тестирование мониторинга пробок...")

    try:
        from src.services.traffic_monitor import TrafficMonitor

        monitor = TrafficMonitor(MapsService(), check_interval_minutes=1)  # 1 минута для теста

        # Создать тестовый маршрут
        orders = [
            Order("Тестовый заказ", "+7-999-999-99-99", "Москва, Тверская, 10", ""),
        ]
        orders[0].latitude = 55.7580
        orders[0].longitude = 37.6170

        from src.models.order import OptimizedRoute, RoutePoint
        start_time = datetime.now()

        points = [
            RoutePoint(
                order=orders[0],
                estimated_arrival=start_time + timedelta(minutes=30),
                distance_from_previous=5.0,
                time_from_previous=15.0
            )
        ]

        route = OptimizedRoute(
            points=points,
            total_distance=5.0,
            total_time=25.0,
            estimated_completion=start_time + timedelta(minutes=30)
        )

        print("Запуск мониторинга на 30 секунд...")
        monitor.start_monitoring(route, orders, (55.7558, 37.6173), start_time)

        # Подождать немного
        import time
        time.sleep(35)

        monitor.stop_monitoring()
        print("✅ Мониторинг пробок протестирован")

    except Exception as e:
        print(f"❌ Ошибка тестирования мониторинга: {e}")
        import traceback
        traceback.print_exc()


def main():
    print("🧪 ТЕСТИРОВАНИЕ OR-Tools и МОНИТОРИНГА ПРОБОК")
    print("=" * 60)

    # Тест OR-Tools оптимизации
    route = test_or_tools_optimization()

    # Тест мониторинга пробок
    test_traffic_monitoring()

    print("\n🎯 ТЕСТИРОВАНИЕ ЗАВЕРШЕНО!")
    print("\n💡 Возможные улучшения:")
    print("   - Добавить ограничения по времени доставки")
    print("   - Интегрировать несколько курьеров")
    print("   - Добавить приоритеты заказов")
    print("   - Улучшить обработку ошибок API")


if __name__ == "__main__":
    main()
