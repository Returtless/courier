"""
Скрипт для локального тестирования с SQLite (без Docker)
Использует SQLite вместо PostgreSQL для быстрого тестирования
"""
import sys
import os
import logging
from datetime import date, datetime, time
from dotenv import load_dotenv

# Принудительно используем SQLite для локального тестирования
os.environ['DATABASE_URL'] = 'sqlite:///./test_courier_bot.db'

# Загружаем остальные переменные окружения из файла env (если есть)
if os.path.exists('env'):
    load_dotenv('env')
    # Переопределяем DATABASE_URL на SQLite
    os.environ['DATABASE_URL'] = 'sqlite:///./test_courier_bot.db'
else:
    # Если файла env нет, создаем минимальную конфигурацию
    os.environ.setdefault('TELEGRAM_BOT_TOKEN', 'test_token')
    os.environ.setdefault('DATABASE_URL', 'sqlite:///./test_courier_bot.db')

from src.database.connection import get_db_session

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def setup_database():
    """Настройка БД - применение миграций"""
    logger.info("=" * 60)
    logger.info("Настройка БД: применение миграций (SQLite)")
    logger.info("=" * 60)
    
    try:
        # Добавляем корень проекта в путь для импорта migrate
        import sys
        from pathlib import Path
        project_root = Path(__file__).parent.parent
        if str(project_root) not in sys.path:
            sys.path.insert(0, str(project_root))
        from scripts.migrate import run_migrations
        logger.info("📝 Применение миграций...")
        result = run_migrations()
        if result:
            logger.info("✅ Миграции применены успешно")
            return True
        else:
            logger.warning("⚠️ Миграции не применены (возможно, уже применены)")
            return True  # Не критично, если миграции уже применены
    except Exception as e:
        logger.error(f"❌ Ошибка применения миграций: {e}", exc_info=True)
        return False

def test_services_initialization():
    """Тест 1: Проверка инициализации сервисов"""
    logger.info("=" * 60)
    logger.info("Тест 1: Инициализация сервисов")
    logger.info("=" * 60)
    
    try:
        from src.application.container import get_container
        
        container = get_container()
        
        # Проверяем, что все сервисы доступны
        order_service = container.order_service()
        route_service = container.route_service()
        call_service = container.call_service()
        maps_service = container.maps_service()
        
        logger.info("✅ OrderService инициализирован")
        logger.info("✅ RouteService инициализирован")
        logger.info("✅ CallService инициализирован")
        logger.info("✅ MapsService инициализирован")
        
        return True
    except Exception as e:
        logger.error(f"❌ Ошибка инициализации сервисов: {e}", exc_info=True)
        return False

def test_order_service():
    """Тест 2: Проверка OrderService"""
    logger.info("=" * 60)
    logger.info("Тест 2: OrderService")
    logger.info("=" * 60)
    
    try:
        from src.application.container import get_container
        from src.application.dto.order_dto import CreateOrderDTO
        
        container = get_container()
        order_service = container.order_service()
        
        # Тестовый user_id
        test_user_id = 999999
        test_date = date.today()
        
        # Создаем тестовый заказ
        create_dto = CreateOrderDTO(
            order_number="TEST001",
            address="Тестовый адрес, д. 1",
            customer_name="Тестовый клиент",
            phone="+79991234567",
            delivery_time_window="10:00-13:00"
        )
        
        with get_db_session() as session:
            order_dto = order_service.create_order(test_user_id, create_dto, test_date, session)
            logger.info(f"✅ Заказ создан: {order_dto.order_number}")
            
            # Получаем заказ
            retrieved_order = order_service.get_order_by_number(test_user_id, "TEST001", test_date, session)
            if retrieved_order:
                logger.info(f"✅ Заказ получен: {retrieved_order.order_number}")
            else:
                logger.error("❌ Заказ не найден после создания")
                return False
            
            # Получаем все заказы за дату
            orders = order_service.get_orders_by_date(test_user_id, test_date, session)
            logger.info(f"✅ Получено заказов за дату: {len(orders)}")
            
            # Удаляем тестовый заказ (через прямой запрос)
            from src.models.order import OrderDB
            test_order = session.query(OrderDB).filter(
                OrderDB.user_id == test_user_id,
                OrderDB.order_number == "TEST001",
                OrderDB.order_date == test_date
            ).first()
            if test_order:
                session.delete(test_order)
                session.commit()
                logger.info("✅ Тестовый заказ удален")
            else:
                logger.warning("⚠️ Тестовый заказ не найден для удаления")
        
        return True
    except Exception as e:
        logger.error(f"❌ Ошибка тестирования OrderService: {e}", exc_info=True)
        return False

def test_route_service():
    """Тест 3: Проверка RouteService"""
    logger.info("=" * 60)
    logger.info("Тест 3: RouteService")
    logger.info("=" * 60)
    
    try:
        from src.application.container import get_container
        from src.application.dto.route_dto import StartLocationDTO
        
        container = get_container()
        route_service = container.route_service()
        
        # Тестовый user_id
        test_user_id = 999999
        test_date = date.today()
        
        # Сохраняем точку старта
        start_location = StartLocationDTO(
            location_type="address",
            address="Москва, Красная площадь, 1",
            latitude=55.7539,
            longitude=37.6208,
            start_time=datetime.combine(test_date, time(9, 0))
        )
        
        with get_db_session() as session:
            saved_location = route_service.save_start_location(test_user_id, start_location, test_date, session)
            logger.info(f"✅ Точка старта сохранена: {saved_location.address}")
            
            # Получаем точку старта
            retrieved_location = route_service.get_start_location(test_user_id, test_date, session)
            if retrieved_location:
                logger.info(f"✅ Точка старта получена: {retrieved_location.address}")
            else:
                logger.error("❌ Точка старта не найдена")
                return False
            
            # Удаляем точку старта (через прямой запрос, так как метод delete_start_location может отсутствовать)
            from src.models.order import StartLocationDB
            start_location_db = session.query(StartLocationDB).filter(
                StartLocationDB.user_id == test_user_id,
                StartLocationDB.location_date == test_date
            ).first()
            if start_location_db:
                session.delete(start_location_db)
                session.commit()
                logger.info("✅ Точка старта удалена")
            else:
                logger.warning("⚠️ Точка старта не найдена для удаления")
        
        return True
    except Exception as e:
        logger.error(f"❌ Ошибка тестирования RouteService: {e}", exc_info=True)
        return False

def test_call_service():
    """Тест 4: Проверка CallService"""
    logger.info("=" * 60)
    logger.info("Тест 4: CallService")
    logger.info("=" * 60)
    
    try:
        from src.application.container import get_container
        from src.application.dto.call_dto import CreateCallStatusDTO
        
        container = get_container()
        call_service = container.call_service()
        
        # Тестовый user_id
        test_user_id = 999999
        test_date = date.today()
        
        # Создаем статус звонка
        call_data = CreateCallStatusDTO(
            order_number="TEST001",
            call_time=datetime.combine(test_date, time(10, 0)),
            phone="+79991234567",
            customer_name="Тестовый клиент"
        )
        
        with get_db_session() as session:
            call_status = call_service.create_call_status(test_user_id, call_data, test_date, session)
            logger.info(f"✅ Статус звонка создан: {call_status.order_number}")
            
            # Получаем статус звонка
            retrieved_call = call_service.get_call_status(test_user_id, "TEST001", test_date, session)
            if retrieved_call:
                logger.info(f"✅ Статус звонка получен: {retrieved_call.order_number}")
            else:
                logger.error("❌ Статус звонка не найден")
                return False
            
            # Получаем статус по ID
            if call_status.id:
                call_by_id = call_service.get_call_status_by_id(call_status.id, session)
                if call_by_id:
                    logger.info(f"✅ Статус звонка получен по ID: {call_by_id.order_number}")
                else:
                    logger.error("❌ Статус звонка не найден по ID")
                    return False
            
            # Удаляем статус звонка (через прямой запрос)
            from src.models.order import CallStatusDB
            call_status_db = session.query(CallStatusDB).filter(
                CallStatusDB.user_id == test_user_id,
                CallStatusDB.order_number == "TEST001",
                CallStatusDB.call_date == test_date
            ).first()
            if call_status_db:
                session.delete(call_status_db)
                session.commit()
                logger.info("✅ Статус звонка удален")
        
        return True
    except Exception as e:
        logger.error(f"❌ Ошибка тестирования CallService: {e}", exc_info=True)
        return False

def test_bot_initialization():
    """Тест 5: Проверка инициализации бота"""
    logger.info("=" * 60)
    logger.info("Тест 5: Инициализация CourierBot")
    logger.info("=" * 60)
    
    try:
        import telebot
        from src.bot.handlers import CourierBot
        
        # Создаем фиктивный бот для теста
        bot = telebot.TeleBot("123456789:ABCdefGHIjklMNOpqrsTUVwxyz")
        
        # Инициализируем CourierBot
        courier_bot = CourierBot(bot)
        
        # Проверяем, что все сервисы инициализированы
        assert courier_bot.order_service is not None, "OrderService не инициализирован"
        assert courier_bot.route_service is not None, "RouteService не инициализирован"
        assert courier_bot.call_service is not None, "CallService не инициализирован"
        assert courier_bot.maps_service is not None, "MapsService не инициализирован"
        
        # Проверяем, что handlers инициализированы
        assert courier_bot.orders is not None, "OrderHandlers не инициализированы"
        assert courier_bot.routes is not None, "RouteHandlers не инициализированы"
        assert courier_bot.calls is not None, "CallHandlers не инициализированы"
        
        logger.info("✅ CourierBot инициализирован успешно")
        logger.info("✅ Все сервисы доступны")
        logger.info("✅ Все handlers инициализированы")
        
        return True
    except Exception as e:
        logger.error(f"❌ Ошибка инициализации CourierBot: {e}", exc_info=True)
        return False

def cleanup_test_db():
    """Очистка тестовой БД"""
    try:
        test_db_path = './test_courier_bot.db'
        if os.path.exists(test_db_path):
            os.remove(test_db_path)
            logger.info(f"✅ Тестовая БД удалена: {test_db_path}")
    except Exception as e:
        logger.warning(f"⚠️ Не удалось удалить тестовую БД: {e}")

def main():
    """Запуск всех тестов"""
    logger.info("🚀 Начало локального тестирования (SQLite)")
    logger.info("")
    
    # Сначала применяем миграции
    if not setup_database():
        logger.error("❌ Не удалось применить миграции. Тесты не могут быть выполнены.")
        return 1
    
    logger.info("")
    results = []
    
    # Запускаем тесты
    results.append(("Инициализация сервисов", test_services_initialization()))
    results.append(("OrderService", test_order_service()))
    results.append(("RouteService", test_route_service()))
    results.append(("CallService", test_call_service()))
    results.append(("Инициализация CourierBot", test_bot_initialization()))
    
    # Выводим результаты
    logger.info("")
    logger.info("=" * 60)
    logger.info("Результаты тестирования")
    logger.info("=" * 60)
    
    passed = 0
    failed = 0
    
    for test_name, result in results:
        status = "✅ ПРОЙДЕН" if result else "❌ ПРОВАЛЕН"
        logger.info(f"{test_name}: {status}")
        if result:
            passed += 1
        else:
            failed += 1
    
    logger.info("")
    logger.info(f"Всего тестов: {len(results)}")
    logger.info(f"Пройдено: {passed}")
    logger.info(f"Провалено: {failed}")
    
    # Опционально: удаляем тестовую БД
    # cleanup_test_db()
    
    if failed == 0:
        logger.info("")
        logger.info("🎉 Все тесты пройдены успешно!")
        return 0
    else:
        logger.info("")
        logger.info("⚠️ Некоторые тесты провалены. Проверьте логи выше.")
        return 1

if __name__ == "__main__":
    sys.exit(main())

