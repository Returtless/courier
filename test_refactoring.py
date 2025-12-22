"""
Скрипт для тестирования рефакторинга без запуска Docker
Проверяет импорты, инициализацию, базовую функциональность
"""
import sys
import traceback
from datetime import date
from unittest.mock import Mock

def test_di_container():
    """Тест DI контейнера"""
    print("\n" + "="*60)
    print("1. Тест DI контейнера")
    print("="*60)
    try:
        from src.application.container import get_container
        container = get_container()
        print("✅ DI контейнер создан")
        
        # Проверяем сервисы
        order_service = container.order_service()
        print(f"✅ OrderService: {type(order_service).__name__}")
        
        route_service = container.route_service()
        print(f"✅ RouteService: {type(route_service).__name__}")
        
        call_service = container.call_service()
        print(f"✅ CallService: {type(call_service).__name__}")
        
        maps_service = container.maps_service()
        print(f"✅ MapsService: {type(maps_service).__name__}")
        
        return True
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        traceback.print_exc()
        return False


def test_repositories():
    """Тест репозиториев"""
    print("\n" + "="*60)
    print("2. Тест репозиториев")
    print("="*60)
    try:
        from src.repositories.order_repository import OrderRepository
        from src.repositories.route_repository import RouteRepository
        from src.repositories.call_status_repository import CallStatusRepository
        
        order_repo = OrderRepository()
        print(f"✅ OrderRepository: {type(order_repo).__name__}")
        
        route_repo = RouteRepository()
        print(f"✅ RouteRepository: {type(route_repo).__name__}")
        
        call_repo = CallStatusRepository()
        print(f"✅ CallStatusRepository: {type(call_repo).__name__}")
        
        return True
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        traceback.print_exc()
        return False


def test_application_services():
    """Тест Application Services"""
    print("\n" + "="*60)
    print("3. Тест Application Services")
    print("="*60)
    try:
        from src.application.container import get_container
        container = get_container()
        
        # OrderService
        order_service = container.order_service()
        print(f"✅ OrderService методы: {[m for m in dir(order_service) if not m.startswith('_')][:5]}...")
        
        # RouteService
        route_service = container.route_service()
        print(f"✅ RouteService методы: {[m for m in dir(route_service) if not m.startswith('_')][:5]}...")
        
        # CallService
        call_service = container.call_service()
        print(f"✅ CallService методы: {[m for m in dir(call_service) if not m.startswith('_')][:5]}...")
        
        return True
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        traceback.print_exc()
        return False


def test_courier_bot():
    """Тест CourierBot"""
    print("\n" + "="*60)
    print("4. Тест CourierBot")
    print("="*60)
    try:
        from src.bot.handlers import CourierBot
        from unittest.mock import Mock
        
        bot_mock = Mock()
        courier_bot = CourierBot(bot_mock)
        
        print(f"✅ CourierBot инициализирован")
        print(f"✅ OrderService: {type(courier_bot.order_service).__name__}")
        print(f"✅ RouteService: {type(courier_bot.route_service).__name__}")
        print(f"✅ CallService: {type(courier_bot.call_service).__name__}")
        print(f"✅ MapsService: {type(courier_bot.maps_service).__name__}")
        
        # Проверяем вспомогательный метод
        try:
            orders = courier_bot.get_today_orders_dict(12345, date.today())
            print(f"✅ get_today_orders_dict работает (вернул {len(orders)} заказов)")
        except Exception as e:
            print(f"⚠️ get_today_orders_dict: {e} (это нормально, если БД пустая)")
        
        return True
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        traceback.print_exc()
        return False


def test_handlers_import():
    """Тест импорта handlers"""
    print("\n" + "="*60)
    print("5. Тест импорта handlers")
    print("="*60)
    try:
        from src.bot.handlers.base_handlers import BaseHandlers
        from src.bot.handlers.order_handlers import OrderHandlers
        from src.bot.handlers.route_handlers import RouteHandlers
        from src.bot.handlers.call_handlers import CallHandlers
        from src.bot.handlers.settings_handlers import SettingsHandlers
        from src.bot.handlers.import_handlers import ImportHandlers
        from src.bot.handlers.traffic_handlers import TrafficHandlers
        
        print("✅ Все handlers импортируются успешно")
        
        # Проверяем, что они могут быть созданы
        from unittest.mock import Mock
        from src.bot.handlers import CourierBot
        
        bot_mock = Mock()
        courier_bot = CourierBot(bot_mock)
        
        print(f"✅ BaseHandlers: {type(courier_bot.base).__name__}")
        print(f"✅ OrderHandlers: {type(courier_bot.orders).__name__}")
        print(f"✅ RouteHandlers: {type(courier_bot.routes).__name__}")
        print(f"✅ CallHandlers: {type(courier_bot.calls).__name__}")
        print(f"✅ SettingsHandlers: {type(courier_bot.settings).__name__}")
        print(f"✅ ImportHandlers: {type(courier_bot.imports).__name__}")
        print(f"✅ TrafficHandlers: {type(courier_bot.traffic).__name__}")
        
        return True
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        traceback.print_exc()
        return False


def test_api_imports():
    """Тест импорта API"""
    print("\n" + "="*60)
    print("6. Тест импорта API")
    print("="*60)
    try:
        from src.api.main import app
        print(f"✅ FastAPI приложение создано")
        print(f"✅ Endpoints: {len(app.routes)}")
        
        # Проверяем роуты
        from src.api.routes import orders, routes, calls, settings, import_routes
        print("✅ Все API роуты импортируются")
        
        # Проверяем схемы
        from src.api.schemas import orders as order_schemas
        from src.api.schemas import routes as route_schemas
        from src.api.schemas import calls as call_schemas
        from src.api.schemas import settings as setting_schemas
        from src.api.schemas import import_schemas
        print("✅ Все API схемы импортируются")
        
        return True
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        traceback.print_exc()
        return False


def test_dto_imports():
    """Тест импорта DTO"""
    print("\n" + "="*60)
    print("7. Тест импорта DTO")
    print("="*60)
    try:
        from src.application.dto.order_dto import OrderDTO, CreateOrderDTO, UpdateOrderDTO
        from src.application.dto.route_dto import RouteDTO, RouteOptimizationRequest, RouteOptimizationResult
        from src.application.dto.call_dto import CallStatusDTO, CreateCallStatusDTO, CallNotificationDTO
        
        print("✅ Все DTO импортируются")
        
        # Проверяем создание DTO
        create_dto = CreateOrderDTO(
            order_number="TEST001",
            address="Test Address"
        )
        print(f"✅ CreateOrderDTO создается: {create_dto.order_number}")
        
        return True
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        traceback.print_exc()
        return False


def test_formatters():
    """Тест форматтеров"""
    print("\n" + "="*60)
    print("8. Тест форматтеров")
    print("="*60)
    try:
        from src.utils.formatters import OrderFormatter, RouteFormatter, CallFormatter
        from src.application.container import get_container
        
        print("✅ Все форматтеры импортируются")
        
        order_formatter = OrderFormatter()
        print(f"✅ OrderFormatter: {type(order_formatter).__name__}")
        
        # RouteFormatter требует maps_service
        container = get_container()
        maps_service = container.maps_service()
        route_formatter = RouteFormatter(maps_service)
        print(f"✅ RouteFormatter: {type(route_formatter).__name__}")
        
        call_formatter = CallFormatter()
        print(f"✅ CallFormatter: {type(call_formatter).__name__}")
        
        return True
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        traceback.print_exc()
        return False


def main():
    """Запуск всех тестов"""
    print("\n" + "="*60)
    print("ТЕСТИРОВАНИЕ РЕФАКТОРИНГА")
    print("="*60)
    
    tests = [
        test_di_container,
        test_repositories,
        test_application_services,
        test_courier_bot,
        test_handlers_import,
        test_api_imports,
        test_dto_imports,
        test_formatters,
    ]
    
    results = []
    for test in tests:
        try:
            result = test()
            results.append(result)
        except Exception as e:
            print(f"\n❌ Критическая ошибка в тесте {test.__name__}: {e}")
            traceback.print_exc()
            results.append(False)
    
    # Итоги
    print("\n" + "="*60)
    print("ИТОГИ ТЕСТИРОВАНИЯ")
    print("="*60)
    passed = sum(results)
    total = len(results)
    print(f"✅ Пройдено: {passed}/{total}")
    print(f"❌ Провалено: {total - passed}/{total}")
    
    if passed == total:
        print("\n🎉 Все тесты пройдены!")
        return 0
    else:
        print("\n⚠️ Некоторые тесты провалены")
        return 1


if __name__ == "__main__":
    sys.exit(main())

