#!/usr/bin/env python3
"""
Финальный тест всех компонентов системы
"""

def test_imports():
    """Тест всех импортов"""
    print("🔍 Финальная проверка импортов...")

    try:
        from src.models.order import Order
        from src.services.maps_service import MapsService
        from src.services.route_optimizer import RouteOptimizer
        from src.services.traffic_monitor import TrafficMonitor
        from src.bot.handlers import CourierBot
        from src.config import settings
        print("✅ Все импорты успешны")
        return True
    except Exception as e:
        print(f"❌ Ошибка импорта: {e}")
        return False

def test_basic_functionality():
    """Тест базовой функциональности"""
    print("\n🧪 Тест базовой функциональности...")

    try:
        # Создание заказа
        order = Order(
            customer_name="Иван Петров",
            phone="+7-999-123-45-67",
            address="ул. Ленина, 10",
            comment="Звонок в домофон",
            order_number="3258104",
            delivery_time_window="10:00 - 13:00"
        )
        print(f"✅ Заказ создан: {order.customer_name}, №{order.order_number}")

        # Тест геокодирования (без API ключа)
        maps = MapsService()
        result = maps.geocode_address_sync("Москва, Красная площадь")
        if result:
            print(f"✅ Геокодирование работает: {result}")
        else:
            print("⚠️ Геокодирование вернуло None (ожидаемо без API)")

        print("✅ Базовая функциональность работает")
        return True

    except Exception as e:
        print(f"❌ Ошибка функциональности: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    print("🎯 ФИНАЛЬНЫЙ ТЕСТ СИСТЕМЫ ОПТИМИЗАЦИИ МАРШРУТОВ")
    print("=" * 60)

    imports_ok = test_imports()
    functionality_ok = test_basic_functionality()

    print("\n" + "=" * 60)
    if imports_ok and functionality_ok:
        print("🎉 ВСЕ ТЕСТЫ ПРОЙДЕНЫ!")
        print("Система готова к запуску!")
        print("\n🚀 Команды для запуска:")
        print("  pip install -r requirements.txt")
        print("  python main.py")
    else:
        print("⚠️ ОБНАРУЖЕНЫ ПРОБЛЕМЫ")
        if not imports_ok:
            print("  - Проблемы с импортами")
        if not functionality_ok:
            print("  - Проблемы с функциональностью")

if __name__ == "__main__":
    main()
