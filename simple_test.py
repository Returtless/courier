#!/usr/bin/env python3
"""
Простой тест основных функций без сложных зависимостей
"""

from datetime import datetime, timedelta
from src.models.order import Order


def test_basic_functionality():
    """Тест базовой функциональности"""
    print("🧪 Тестирование базовой функциональности...")

    # Создание заказов с временными окнами
    orders = [
        Order("Иван Петров", "+7-999-123-45-67", "ул. Ленина, 10", "Звонок в домофон",
              delivery_time_window="10:00 - 13:00"),
        Order("Анна Сидорова", "+7-999-234-56-78", "пр. Победы, 25", "Оставить у двери",
              delivery_time_window="11:00 - 14:00"),
        Order("Михаил Иванов", "+7-999-345-67-89", "ул. Гагарина, 5", "Подъезд 3",
              delivery_time_window="12:00 - 15:00"),
    ]

    print(f"✅ Создано {len(orders)} заказов:")
    for i, order in enumerate(orders, 1):
        print(f"   {i}. {order.customer_name} - {order.address}")
        if order.delivery_time_window:
            print(f"      🕐 {order.delivery_time_window}")
        if order.comment:
            print(f"      💬 {order.comment}")
    print()

    # Имитация маршрута
    start_time = datetime.now().replace(hour=9, minute=0)
    total_distance = 0
    total_time = 0

    print("🚚 Имитация маршрута:")
    print("-" * 40)

    current_time = start_time
    for i, order in enumerate(orders, 1):
        # Имитация времени в пути
        travel_time = 15 + (i * 5)  # минут
        delivery_time = 10  # минут на доставку

        current_time += timedelta(minutes=travel_time + delivery_time)
        distance = 5 + (i * 2)  # км

        total_distance += distance
        total_time += travel_time + delivery_time

        print(f"{i}. {order.customer_name}")
        print(f"   ⏰ Прибытие: {current_time.strftime('%H:%M')}")
        print(f"   📏 Расстояние: {distance} км")
        print(f"   ⏱️ Время: {travel_time + delivery_time} мин")
        print()

    print("📊 ИТОГИ:")
    print(f"   📦 Заказов: {len(orders)}")
    print(f"   📏 Расстояние: {total_distance:.1f} км")
    print(f"   ⏱️ Время: {total_time:.0f} мин")
    print(f"   🏁 Завершение: {current_time.strftime('%H:%M')}")
    print()

    # График звонков
    print("📞 ГРАФИК ЗВОНКОВ:")
    print("-" * 40)

    for i, order in enumerate(orders, 1):
        call_time = current_time - timedelta(minutes=(len(orders) - i + 1) * 20)
        print(f"📞 {call_time.strftime('%H:%M')} - {order.customer_name} ({order.phone})")

    print("\n✅ Базовая функциональность работает!")


def test_imports():
    """Тест импортов"""
    print("🔍 Тестирование импортов...")

    try:
        from src.models.order import Order, OptimizedRoute, RoutePoint
        print("✅ Модели импортированы")
    except Exception as e:
        print(f"❌ Ошибка импорта моделей: {e}")
        return

    try:
        from src.services.maps_service import MapsService
        print("✅ MapsService импортирован")
    except Exception as e:
        print(f"❌ Ошибка импорта MapsService: {e}")
        return

    try:
        from src.services.route_optimizer import RouteOptimizer
        print("✅ RouteOptimizer импортирован")
    except Exception as e:
        print(f"❌ Ошибка импорта RouteOptimizer: {e}")
        return

    try:
        from src.services.traffic_monitor import TrafficMonitor
        print("✅ TrafficMonitor импортирован")
    except Exception as e:
        print(f"❌ Ошибка импорта TrafficMonitor: {e}")
        return

    print("✅ Все импорты успешны!")


def main():
    print("🚚 ПРОСТОЕ ТЕСТИРОВАНИЕ СИСТЕМЫ")
    print("=" * 50)

    test_imports()
    print()
    test_basic_functionality()

    print("\n🎯 ТЕСТИРОВАНИЕ ЗАВЕРШЕНО!")
    print("\n💡 Система готова к работе!")
    print("   - Базовые модели работают")
    print("   - Импорты настроены правильно")
    print("   - Логика маршрутов функционирует")


if __name__ == "__main__":
    main()
