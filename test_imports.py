#!/usr/bin/env python3
"""
Простой тест импортов для проверки синтаксиса
"""

def test_all_imports():
    """Тест всех импортов"""
    print("🔍 Тестирование импортов...")

    try:
        from src.models.order import Order, OptimizedRoute, RoutePoint
        print("✅ Модели импортированы")
    except Exception as e:
        print(f"❌ Ошибка импорта моделей: {e}")
        return False

    try:
        from src.services.maps_service import MapsService
        print("✅ MapsService импортирован")
    except Exception as e:
        print(f"❌ Ошибка импорта MapsService: {e}")
        return False

    try:
        from src.services.route_optimizer import RouteOptimizer
        print("✅ RouteOptimizer импортирован")
    except Exception as e:
        print(f"❌ Ошибка импорта RouteOptimizer: {e}")
        return False

    try:
        from src.services.traffic_monitor import TrafficMonitor
        print("✅ TrafficMonitor импортирован")
    except Exception as e:
        print(f"❌ Ошибка импорта TrafficMonitor: {e}")
        return False

    try:
        from src.config import settings
        print("✅ Конфигурация импортирована")
    except Exception as e:
        print(f"❌ Ошибка импорта конфигурации: {e}")
        return False

    print("✅ Все импорты успешны!")
    return True


if __name__ == "__main__":
    success = test_all_imports()
    if success:
        print("\n🎉 Все модули готовы к работе!")
    else:
        print("\n⚠️ Есть проблемы с импортами!")
