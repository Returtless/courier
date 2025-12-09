#!/usr/bin/env python3
"""
Тестовый скрипт для проверки работы карт и оптимизации маршрутов
"""

from datetime import datetime
from src.services.maps_service import MapsService
from src.services.route_optimizer import RouteOptimizer
from src.models.order import Order


def test_geocoding():
    """Тест геокодирования"""
    print("🗺️ Тестирование геокодирования...")

    maps_service = MapsService()

    # Тестовые адреса
    addresses = [
        "Москва, Красная площадь, 1",
        "Москва, ул. Тверская, 10",
        "Москва, пр. Ленинский, 25"
    ]

    for address in addresses:
        lat, lon = maps_service.geocode_address_sync(address)
        print(f"📍 {address}")
        if lat and lon:
            print(f"   ✅ Координаты: {lat:.4f}, {lon:.4f}")
        else:
            print("   ❌ Не удалось определить координаты")
        print()


def test_route_optimization():
    """Тест оптимизации маршрутов"""
    print("🚚 Тестирование оптимизации маршрутов...")

    # Создание тестовых заказов
    orders = [
        Order("Иван Петров", "+7-999-123-45-67", "Москва, ул. Арбат, 15", "Звонок в домофон"),
        Order("Анна Сидорова", "+7-999-234-56-78", "Москва, ул. Новый Арбат, 25", "Оставить у двери"),
        Order("Михаил Иванов", "+7-999-345-67-89", "Москва, ул. Садовое кольцо, 5", "Подъезд 3"),
    ]

    # Точка старта (Москва, центр)
    start_location = (55.7558, 37.6173)  # Красная площадь
    start_time = datetime.now().replace(hour=9, minute=0)

    print(f"🏭 Точка старта: {start_location}")
    print(f"🕐 Время старта: {start_time.strftime('%H:%M')}")
    print()

    try:
        maps_service = MapsService()
        route_optimizer = RouteOptimizer(maps_service)

        optimized_route = route_optimizer.optimize_route_sync(
            orders, start_location, start_time
        )

        print("✅ МАРШРУТ ОПТИМИЗИРОВАН")
        print("-" * 50)
        print(f"📊 Заказов: {len(optimized_route.points)}")
        print(f"📏 Расстояние: {optimized_route.total_distance:.1f} км")
        print(f"⏱️ Время: {optimized_route.total_time:.0f} мин")
        print(f"🏁 Завершение: {optimized_route.estimated_completion.strftime('%H:%M')}")
        print()

        print("🚚 ОПТИМАЛЬНЫЙ МАРШРУТ:")
        for i, point in enumerate(optimized_route.points, 1):
            order = point.order
            print(f"{i}. {order.customer_name}")
            print(f"   📍 {order.address}")
            print(f"   📞 {order.phone}")
            print(f"   ⏰ {point.estimated_arrival.strftime('%H:%M')}")
            if order.comment:
                print(f"   💬 {order.comment}")
            print()

    except Exception as e:
        print(f"❌ Ошибка оптимизации: {e}")
        import traceback
        traceback.print_exc()


def main():
    print("🧪 ТЕСТИРОВАНИЕ СИСТЕМЫ КАРТ И ОПТИМИЗАЦИИ")
    print("=" * 60)

    # Тест геокодирования
    test_geocoding()

    # Тест оптимизации
    test_route_optimization()

    print("🎯 ТЕСТИРОВАНИЕ ЗАВЕРШЕНО!")


if __name__ == "__main__":
    main()
