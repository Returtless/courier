# 🧪 Стратегия тестирования Courier Planning Bot

## 📋 Общая структура

```
tests/
├── unit/                    # Изолированные тесты отдельных компонентов
│   ├── test_models.py
│   ├── test_db_service.py
│   ├── test_route_optimizer.py
│   ├── test_call_notifier.py
│   ├── test_maps_service.py
│   └── test_settings_service.py
├── integration/             # Тесты взаимодействия компонентов
│   ├── test_route_flow.py
│   ├── test_order_flow.py
│   ├── test_call_flow.py
│   └── test_manual_times.py
├── e2e/                     # End-to-end тесты
│   ├── test_full_scenario.py
│   └── test_user_journey.py
├── fixtures/                # Тестовые данные
│   ├── orders.json
│   ├── routes.json
│   └── users.json
└── conftest.py             # Общие фикстуры pytest
```

---

## 1️⃣ Unit-тесты (Изолированные компоненты)

### 🎯 Цель
Проверить корректность работы отдельных методов и классов в изоляции.

### 📦 Инструменты
- **pytest** - фреймворк для тестирования
- **pytest-mock** - моки для изоляции зависимостей
- **pytest-cov** - измерение покрытия кода
- **freezegun** - заморозка времени для тестов

### 📝 Примеры тестов

#### `tests/unit/test_models.py`
```python
import pytest
from datetime import datetime, time, date
from src.models.order import Order, CallStatusDB, OrderDB

class TestOrderModel:
    """Тесты модели Order"""
    
    def test_order_creation_with_minimal_data(self):
        """Создание заказа с минимальными данными"""
        order = Order(
            customer_name="Тест",
            phone="+79991234567",
            address="Москва, Тверская 1"
        )
        assert order.customer_name == "Тест"
        assert order.status == "pending"
    
    def test_order_time_window_parsing(self):
        """Парсинг временного окна доставки"""
        order = Order(
            customer_name="Тест",
            phone="+79991234567",
            address="Москва, Тверская 1",
            delivery_time_window="14:00 - 16:00"
        )
        assert order.delivery_time_start == time(14, 0)
        assert order.delivery_time_end == time(16, 0)
    
    def test_order_invalid_time_window(self):
        """Невалидное временное окно"""
        order = Order(
            customer_name="Тест",
            phone="+79991234567",
            address="Москва, Тверская 1",
            delivery_time_window="invalid"
        )
        assert order.delivery_time_start is None
        assert order.delivery_time_end is None

class TestCallStatusDB:
    """Тесты модели CallStatusDB"""
    
    def test_call_status_creation(self):
        """Создание записи о звонке"""
        call_status = CallStatusDB(
            user_id=123,
            order_number="12345",
            call_date=date.today(),
            call_time=datetime(2025, 12, 15, 12, 50),
            arrival_time=datetime(2025, 12, 15, 13, 30),
            is_manual=True,
            phone="+79991234567",
            customer_name="Тест"
        )
        assert call_status.is_manual is True
        assert call_status.status == "pending"
        assert call_status.attempts == 0
```

#### `tests/unit/test_db_service.py`
```python
import pytest
from datetime import date, time, datetime
from unittest.mock import Mock, patch
from src.services.db_service import DatabaseService

@pytest.fixture
def db_service():
    """Фикстура для DatabaseService"""
    return DatabaseService()

@pytest.fixture
def mock_session():
    """Мок сессии БД"""
    with patch('src.services.db_service.get_db_session') as mock:
        session = Mock()
        mock.return_value.__enter__.return_value = session
        yield session

class TestDatabaseService:
    """Тесты DatabaseService"""
    
    def test_add_order(self, db_service, mock_session):
        """Добавление заказа в БД"""
        order_data = {
            'customer_name': 'Тест',
            'phone': '+79991234567',
            'address': 'Москва, Тверская 1',
            'delivery_time_window': '14:00 - 16:00'
        }
        
        user_id = 123
        order_number = db_service.add_order(user_id, order_data)
        
        # Проверяем, что сессия была использована
        assert mock_session.add.called
        assert mock_session.commit.called
    
    def test_get_today_orders(self, db_service, mock_session):
        """Получение заказов на сегодня"""
        # Настраиваем мок
        mock_order = Mock()
        mock_order.id = 1
        mock_order.order_number = "12345"
        mock_order.customer_name = "Тест"
        mock_order.phone = "+79991234567"
        mock_order.address = "Москва"
        mock_order.status = "pending"
        mock_order.manual_arrival_time = None
        
        mock_session.query.return_value.filter.return_value.all.return_value = [mock_order]
        
        orders = db_service.get_today_orders(123)
        
        assert len(orders) > 0
        assert orders[0]['order_number'] == "12345"
    
    def test_update_order(self, db_service, mock_session):
        """Обновление заказа"""
        mock_order = Mock()
        mock_session.query.return_value.filter.return_value.first.return_value = mock_order
        
        updates = {'phone': '+79999999999'}
        db_service.update_order(123, "12345", updates, date.today())
        
        assert mock_order.phone == '+79999999999'
        assert mock_session.commit.called
```

#### `tests/unit/test_route_optimizer.py`
```python
import pytest
from datetime import datetime, time
from unittest.mock import Mock, patch
from src.services.route_optimizer import RouteOptimizer
from src.models.order import Order

@pytest.fixture
def optimizer():
    """Фикстура для RouteOptimizer"""
    maps_service = Mock()
    return RouteOptimizer(maps_service)

@pytest.fixture
def sample_orders():
    """Тестовые заказы"""
    return [
        Order(
            customer_name="Клиент 1",
            phone="+79991111111",
            address="Москва, Тверская 1",
            latitude=55.7558,
            longitude=37.6173,
            delivery_time_window="10:00 - 12:00"
        ),
        Order(
            customer_name="Клиент 2",
            phone="+79992222222",
            address="Москва, Арбат 1",
            latitude=55.7522,
            longitude=37.5989,
            delivery_time_window="12:00 - 14:00"
        )
    ]

class TestRouteOptimizer:
    """Тесты RouteOptimizer"""
    
    def test_build_matrices(self, optimizer):
        """Построение матриц расстояний и времени"""
        locations = [
            (55.7558, 37.6173),  # Старт
            (55.7522, 37.5989),  # Точка 1
            (55.7505, 37.6175)   # Точка 2
        ]
        
        optimizer.maps_service.get_route_distance_matrix_sync.return_value = (
            [[0, 1000, 2000], [1000, 0, 1500], [2000, 1500, 0]],  # distance
            [[0, 5, 10], [5, 0, 8], [10, 8, 0]]  # time
        )
        
        distance_matrix, time_matrix = optimizer._build_matrices(locations)
        
        assert distance_matrix.shape == (3, 3)
        assert time_matrix.shape == (3, 3)
    
    def test_optimize_route_with_manual_arrival_time(self, optimizer, sample_orders):
        """Оптимизация с ручным временем прибытия"""
        # Устанавливаем ручное время для первого заказа
        sample_orders[0].manual_arrival_time = datetime(2025, 12, 15, 11, 0)
        
        start_location = (55.7558, 37.6173)
        start_time = datetime(2025, 12, 15, 9, 0)
        
        # Мокаем методы
        optimizer.maps_service.get_route_distance_matrix_sync.return_value = (
            [[0, 1000, 2000], [1000, 0, 1500], [2000, 1500, 0]],
            [[0, 5, 10], [5, 0, 8], [10, 8, 0]]
        )
        
        result = optimizer.optimize_route_sync(
            sample_orders,
            start_location,
            start_time,
            user_id=123
        )
        
        # Проверяем, что маршрут построен
        assert len(result.points) == 2
        # Проверяем, что первый заказ прибывает примерно в 11:00 (±5 мин)
        first_arrival = result.points[0].estimated_arrival
        assert abs((first_arrival - sample_orders[0].manual_arrival_time).total_seconds()) < 300
```

#### `tests/unit/test_call_notifier.py`
```python
import pytest
from datetime import datetime, date
from unittest.mock import Mock, patch
from src.services.call_notifier import CallNotifier

@pytest.fixture
def call_notifier():
    """Фикстура для CallNotifier"""
    bot = Mock()
    db_service = Mock()
    return CallNotifier(bot, db_service)

class TestCallNotifier:
    """Тесты CallNotifier"""
    
    @patch('src.services.call_notifier.get_db_session')
    def test_create_call_status_new(self, mock_session, call_notifier):
        """Создание нового call_status"""
        session = Mock()
        mock_session.return_value.__enter__.return_value = session
        session.query.return_value.filter.return_value.first.return_value = None
        
        call_notifier.create_call_status(
            user_id=123,
            order_number="12345",
            call_time=datetime(2025, 12, 15, 12, 50),
            phone="+79991234567",
            customer_name="Тест",
            is_manual=True,
            arrival_time=datetime(2025, 12, 15, 13, 30)
        )
        
        # Проверяем, что запись создана
        assert session.add.called
        assert session.commit.called
        call_status = session.add.call_args[0][0]
        assert call_status.is_manual is True
    
    @patch('src.services.call_notifier.get_db_session')
    def test_create_call_status_update_manual_protected(self, mock_session, call_notifier):
        """Защита от перезаписи ручных установок"""
        session = Mock()
        mock_session.return_value.__enter__.return_value = session
        
        # Существующая ручная запись
        existing = Mock()
        existing.is_manual = True
        existing.call_time = datetime(2025, 12, 15, 12, 50)
        session.query.return_value.filter.return_value.first.return_value = existing
        
        # Пытаемся обновить автоматически
        result = call_notifier.create_call_status(
            user_id=123,
            order_number="12345",
            call_time=datetime(2025, 12, 15, 13, 0),
            phone="+79991234567",
            is_manual=False  # Автоматическое обновление
        )
        
        # Проверяем, что НЕ перезаписали
        assert result == existing
        assert existing.call_time == datetime(2025, 12, 15, 12, 50)
        assert not session.commit.called
```

---

## 2️⃣ Integration-тесты (Взаимодействие компонентов)

### 🎯 Цель
Проверить корректность работы нескольких компонентов вместе.

### 📝 Примеры тестов

#### `tests/integration/test_manual_times.py`
```python
import pytest
from datetime import datetime, date, time
from src.services.db_service import DatabaseService
from src.services.call_notifier import CallNotifier
from src.services.route_optimizer import RouteOptimizer
from unittest.mock import Mock

@pytest.fixture
def setup_services():
    """Настройка всех сервисов"""
    db_service = DatabaseService()
    bot = Mock()
    call_notifier = CallNotifier(bot, db_service)
    maps_service = Mock()
    optimizer = RouteOptimizer(maps_service)
    
    return {
        'db': db_service,
        'call_notifier': call_notifier,
        'optimizer': optimizer,
        'bot': bot
    }

class TestManualTimesFlow:
    """Интеграционные тесты ручного времени"""
    
    @pytest.mark.integration
    def test_set_manual_call_time_creates_call_status(self, setup_services):
        """Установка ручного времени звонка создает call_status"""
        db = setup_services['db']
        call_notifier = setup_services['call_notifier']
        
        # Создаем заказ
        user_id = 123
        order_data = {
            'customer_name': 'Тест',
            'phone': '+79991234567',
            'address': 'Москва, Тверская 1'
        }
        order_number = db.add_order(user_id, order_data)
        
        # Устанавливаем ручное время звонка
        call_time = datetime(2025, 12, 15, 12, 50)
        arrival_time = datetime(2025, 12, 15, 13, 30)
        
        call_notifier.create_call_status(
            user_id=user_id,
            order_number=order_number,
            call_time=call_time,
            phone='+79991234567',
            is_manual=True,
            arrival_time=arrival_time
        )
        
        # Проверяем, что call_status создан
        from src.database.connection import get_db_session
        from src.models.order import CallStatusDB
        
        with get_db_session() as session:
            call_status = session.query(CallStatusDB).filter(
                CallStatusDB.user_id == user_id,
                CallStatusDB.order_number == order_number
            ).first()
            
            assert call_status is not None
            assert call_status.is_manual is True
            assert call_status.call_time == call_time
            assert call_status.arrival_time == arrival_time
    
    @pytest.mark.integration
    def test_reoptimization_preserves_manual_times(self, setup_services):
        """Реоптимизация сохраняет ручные времена"""
        db = setup_services['db']
        call_notifier = setup_services['call_notifier']
        
        user_id = 123
        
        # Создаем заказ с ручным временем
        order_data = {
            'customer_name': 'Тест 1',
            'phone': '+79991234567',
            'address': 'Москва, Тверская 1'
        }
        order_number = db.add_order(user_id, order_data)
        
        manual_call_time = datetime(2025, 12, 15, 12, 50)
        manual_arrival_time = datetime(2025, 12, 15, 13, 30)
        
        call_notifier.create_call_status(
            user_id=user_id,
            order_number=order_number,
            call_time=manual_call_time,
            phone='+79991234567',
            is_manual=True,
            arrival_time=manual_arrival_time
        )
        
        # Имитируем реоптимизацию (автоматическое обновление)
        new_call_time = datetime(2025, 12, 15, 14, 0)
        new_arrival_time = datetime(2025, 12, 15, 14, 40)
        
        call_notifier.create_call_status(
            user_id=user_id,
            order_number=order_number,
            call_time=new_call_time,
            phone='+79991234567',
            is_manual=False,  # Автоматическое
            arrival_time=new_arrival_time
        )
        
        # Проверяем, что ручное время НЕ изменилось
        from src.database.connection import get_db_session
        from src.models.order import CallStatusDB
        
        with get_db_session() as session:
            call_status = session.query(CallStatusDB).filter(
                CallStatusDB.user_id == user_id,
                CallStatusDB.order_number == order_number
            ).first()
            
            assert call_status.is_manual is True
            assert call_status.call_time == manual_call_time
            assert call_status.arrival_time == manual_arrival_time
```

#### `tests/integration/test_route_flow.py`
```python
import pytest
from datetime import datetime, time
from src.services.db_service import DatabaseService
from src.services.route_optimizer import RouteOptimizer
from unittest.mock import Mock

@pytest.mark.integration
class TestRouteOptimizationFlow:
    """Тесты полного цикла оптимизации маршрута"""
    
    def test_optimize_route_with_mixed_constraints(self):
        """Оптимизация с разными типами ограничений"""
        db = DatabaseService()
        maps_service = Mock()
        optimizer = RouteOptimizer(maps_service)
        
        user_id = 123
        
        # Заказ 1: Обычное временное окно
        order1_data = {
            'customer_name': 'Клиент 1',
            'phone': '+79991111111',
            'address': 'Москва, Тверская 1',
            'delivery_time_window': '10:00 - 12:00',
            'latitude': 55.7558,
            'longitude': 37.6173
        }
        order1_number = db.add_order(user_id, order1_data)
        
        # Заказ 2: Ручное время прибытия
        order2_data = {
            'customer_name': 'Клиент 2',
            'phone': '+79992222222',
            'address': 'Москва, Арбат 1',
            'latitude': 55.7522,
            'longitude': 37.5989
        }
        order2_number = db.add_order(user_id, order2_data)
        db.update_order(
            user_id,
            order2_number,
            {'manual_arrival_time': datetime(2025, 12, 15, 11, 0)},
            date.today()
        )
        
        # Заказ 3: Без ограничений
        order3_data = {
            'customer_name': 'Клиент 3',
            'phone': '+79993333333',
            'address': 'Москва, Патриаршие пруды 1',
            'latitude': 55.7647,
            'longitude': 37.5951
        }
        order3_number = db.add_order(user_id, order3_data)
        
        # Мокаем матрицы
        maps_service.get_route_distance_matrix_sync.return_value = (
            [[0, 1000, 2000, 1500],
             [1000, 0, 1500, 1200],
             [2000, 1500, 0, 1800],
             [1500, 1200, 1800, 0]],
            [[0, 5, 10, 8],
             [5, 0, 8, 6],
             [10, 8, 0, 9],
             [8, 6, 9, 0]]
        )
        
        # Загружаем заказы
        orders_data = db.get_today_orders(user_id)
        from src.models.order import Order
        orders = [Order(**od) for od in orders_data]
        
        # Оптимизируем
        start_location = (55.7558, 37.6173)
        start_time = datetime(2025, 12, 15, 9, 0)
        
        result = optimizer.optimize_route_sync(
            orders,
            start_location,
            start_time,
            user_id=user_id
        )
        
        # Проверяем результат
        assert len(result.points) == 3
        
        # Проверяем, что заказ с ручным временем близок к 11:00
        for point in result.points:
            if point.order.order_number == order2_number:
                arrival = point.estimated_arrival
                expected = datetime(2025, 12, 15, 11, 0)
                # Должно быть в пределах ±5 минут
                assert abs((arrival - expected).total_seconds()) < 300
```

---

## 3️⃣ End-to-End тесты (Полные сценарии)

### 🎯 Цель
Проверить работу всего приложения от начала до конца, имитируя действия пользователя.

### 📦 Инструменты
- **pytest-asyncio** - для асинхронных тестов
- **aiogram-tests** - для тестирования телеграм-ботов
- **Testcontainers** - для запуска PostgreSQL в Docker

### 📝 Примеры тестов

#### `tests/e2e/test_full_scenario.py`
```python
import pytest
from datetime import datetime, date
from unittest.mock import Mock, AsyncMock
from aiogram import types
from src.bot.handlers import CourierBot

@pytest.mark.asyncio
@pytest.mark.e2e
class TestFullUserScenario:
    """End-to-end тесты полного сценария пользователя"""
    
    async def test_complete_delivery_scenario(self):
        """Полный сценарий от добавления заказа до доставки"""
        # 1. Пользователь начинает работу
        # 2. Добавляет несколько заказов
        # 3. Устанавливает ручное время для одного
        # 4. Оптимизирует маршрут
        # 5. Начинает доставку
        # 6. Помечает заказы как доставленные
        
        # TODO: Реализовать с использованием aiogram-tests
        pass
```

---

## 4️⃣ Тестирование БД и миграций

### 📝 Примеры тестов

#### `tests/integration/test_migrations.py`
```python
import pytest
from alembic import command
from alembic.config import Config
from src.database.connection import get_engine
from sqlalchemy import inspect

@pytest.mark.migration
class TestDatabaseMigrations:
    """Тесты миграций БД"""
    
    def test_migration_003_adds_columns(self):
        """Миграция 003 добавляет arrival_time и is_manual"""
        # Применяем миграцию
        alembic_cfg = Config("alembic.ini")
        command.upgrade(alembic_cfg, "003")
        
        # Проверяем структуру таблицы
        engine = get_engine()
        inspector = inspect(engine)
        columns = [c['name'] for c in inspector.get_columns('call_status')]
        
        assert 'arrival_time' in columns
        assert 'is_manual' in columns
    
    def test_migration_003_removes_manual_call_time(self):
        """Миграция 003 удаляет manual_call_time из orders"""
        alembic_cfg = Config("alembic.ini")
        command.upgrade(alembic_cfg, "003")
        
        engine = get_engine()
        inspector = inspect(engine)
        columns = [c['name'] for c in inspector.get_columns('orders')]
        
        assert 'manual_call_time' not in columns
        assert 'manual_arrival_time' in columns
    
    def test_migration_downgrade(self):
        """Откат миграции работает корректно"""
        alembic_cfg = Config("alembic.ini")
        
        # Откатываем
        command.downgrade(alembic_cfg, "002")
        
        # Проверяем
        engine = get_engine()
        inspector = inspect(engine)
        
        call_status_columns = [c['name'] for c in inspector.get_columns('call_status')]
        assert 'arrival_time' not in call_status_columns
        assert 'is_manual' not in call_status_columns
        
        orders_columns = [c['name'] for c in inspector.get_columns('orders')]
        assert 'manual_call_time' in orders_columns
```

---

## 5️⃣ Настройка окружения для тестов

### `conftest.py`
```python
import pytest
from datetime import datetime
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from src.models.order import Base
from src.database.connection import set_test_engine

@pytest.fixture(scope="session")
def test_db_engine():
    """Создаем тестовую БД"""
    # Используем SQLite в памяти для тестов
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    set_test_engine(engine)
    yield engine
    Base.metadata.drop_all(engine)

@pytest.fixture(scope="function")
def test_db_session(test_db_engine):
    """Сессия БД для каждого теста"""
    Session = sessionmaker(bind=test_db_engine)
    session = Session()
    yield session
    session.rollback()
    session.close()

@pytest.fixture
def freeze_time():
    """Заморозка времени для тестов"""
    from freezegun import freeze_time
    frozen_time = datetime(2025, 12, 15, 9, 0, 0)
    with freeze_time(frozen_time):
        yield frozen_time

@pytest.fixture
def sample_user():
    """Тестовый пользователь"""
    return {
        'user_id': 123,
        'username': 'test_courier',
        'first_name': 'Тест'
    }
```

### `pytest.ini`
```ini
[pytest]
testpaths = tests
python_files = test_*.py
python_classes = Test*
python_functions = test_*
markers =
    unit: Unit tests
    integration: Integration tests
    e2e: End-to-end tests
    migration: Database migration tests
    slow: Tests that take a long time
addopts = 
    -v
    --strict-markers
    --cov=src
    --cov-report=html
    --cov-report=term-missing
```

### `requirements-dev.txt`
```txt
# Тестирование
pytest==7.4.3
pytest-asyncio==0.21.1
pytest-cov==4.1.0
pytest-mock==3.12.0
freezegun==1.4.0
aiogram-tests==1.1.4
testcontainers==3.7.1

# Линтинг и форматирование
black==23.12.1
flake8==6.1.0
mypy==1.7.1
isort==5.13.2

# Дополнительно
faker==20.1.0  # Генерация тестовых данных
```

---

## 6️⃣ Запуск тестов

### Все тесты
```bash
pytest
```

### Только unit-тесты
```bash
pytest -m unit
```

### Только integration-тесты
```bash
pytest -m integration
```

### С покрытием кода
```bash
pytest --cov=src --cov-report=html
```

### Параллельный запуск
```bash
pip install pytest-xdist
pytest -n auto
```

---

## 7️⃣ CI/CD Integration

### `.github/workflows/tests.yml`
```yaml
name: Tests

on:
  push:
    branches: [ main, develop, feature/* ]
  pull_request:
    branches: [ main, develop ]

jobs:
  test:
    runs-on: ubuntu-latest
    
    services:
      postgres:
        image: postgres:15
        env:
          POSTGRES_PASSWORD: postgres
          POSTGRES_DB: test_courier_db
        ports:
          - 5432:5432
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5
    
    steps:
    - uses: actions/checkout@v3
    
    - name: Set up Python
      uses: actions/setup-python@v4
      with:
        python-version: '3.11'
    
    - name: Install dependencies
      run: |
        pip install -r requirements.txt
        pip install -r requirements-dev.txt
    
    - name: Run unit tests
      run: pytest -m unit --cov=src --cov-report=xml
    
    - name: Run integration tests
      env:
        DATABASE_URL: postgresql://postgres:postgres@localhost:5432/test_courier_db
      run: pytest -m integration
    
    - name: Upload coverage
      uses: codecov/codecov-action@v3
      with:
        file: ./coverage.xml
```

---

## 8️⃣ Тестовые данные (Fixtures)

### `tests/fixtures/orders.json`
```json
[
  {
    "customer_name": "Иван Иванов",
    "phone": "+79991234567",
    "address": "Москва, Тверская улица, 1",
    "delivery_time_window": "10:00 - 12:00",
    "comment": "Домофон не работает"
  },
  {
    "customer_name": "Мария Петрова",
    "phone": "+79997654321",
    "address": "Москва, Арбат, 10",
    "delivery_time_window": "12:00 - 14:00",
    "entrance_number": "2",
    "apartment_number": "42"
  }
]
```

---

## 📊 Метрики покрытия

### Целевые показатели:
- **Unit-тесты:** 80%+ покрытие кода
- **Integration-тесты:** Все основные сценарии
- **E2E-тесты:** 3-5 ключевых user journeys

### Приоритетные области:
1. ✅ Логика ручного времени (100%)
2. ✅ Оптимизация маршрута (90%+)
3. ✅ Работа с БД (80%+)
4. ✅ Уведомления о звонках (80%+)
5. ⚠️ Обработчики бота (60%+)

---

## 🚀 С чего начать

### Этап 1: Базовая инфраструктура (1-2 дня)
1. Создать структуру папок `tests/`
2. Настроить `pytest` и `conftest.py`
3. Настроить тестовую БД

### Этап 2: Unit-тесты критических компонентов (3-5 дней)
1. `test_models.py` - модели данных
2. `test_db_service.py` - работа с БД
3. `test_route_optimizer.py` - оптимизация
4. `test_call_notifier.py` - уведомления

### Этап 3: Integration-тесты (2-3 дня)
1. `test_manual_times.py` - ручное время
2. `test_route_flow.py` - оптимизация маршрута
3. `test_call_flow.py` - уведомления

### Этап 4: E2E-тесты (2-3 дня)
1. `test_full_scenario.py` - полный сценарий доставки

### Этап 5: CI/CD (1 день)
1. Настроить GitHub Actions
2. Интегрировать с Codecov

---

## 📝 Чек-лист готовности

- [ ] Установлены все зависимости для тестов
- [ ] Создана структура `tests/`
- [ ] Настроен `pytest` и `conftest.py`
- [ ] Написаны unit-тесты для моделей
- [ ] Написаны unit-тесты для сервисов
- [ ] Написаны integration-тесты
- [ ] Настроен CI/CD
- [ ] Покрытие кода > 70%
- [ ] Все тесты проходят

---

## 🎯 Итого

Комплексное тестирование позволит:
- ✅ Обнаруживать баги на ранних этапах
- ✅ Безопасно рефакторить код
- ✅ Документировать поведение системы
- ✅ Ускорить разработку новых фичей
- ✅ Повысить уверенность в стабильности

**Рекомендация:** Начать с unit-тестов критических компонентов (особенно логики ручного времени после рефакторинга), затем добавить integration-тесты.

