# 🏗️ План архитектуры с разделением API и Bot

**Цель:** Создать архитектуру, где бизнес-логика отделена от UI (Telegram Bot), что позволит использовать её как для бота, так и для REST API (мобильное приложение).

---

## 📐 Целевая архитектура

```
┌─────────────────────────────────────────────────────────────┐
│                        Presentation Layer                    │
├──────────────────────┬──────────────────────────────────────┤
│   Telegram Bot       │         REST API (FastAPI)           │
│   (src/bot/)         │         (src/api/)                  │
│                      │                                      │
│  - Handlers          │  - Controllers                       │
│  - Message Format    │  - Request/Response Models           │
│  - Callback Routing  │  - Authentication                    │
└──────────┬───────────┴──────────────┬───────────────────────┘
           │                          │
           └──────────┬───────────────┘
                      │
        ┌─────────────▼──────────────┐
        │   Application Services      │
        │   (src/application/)        │
        │                             │
        │  - OrderService             │
        │  - RouteService             │
        │  - CallService              │
        │  - ImportService            │
        │  - SettingsService          │
        └─────────────┬──────────────┘
                      │
        ┌─────────────▼──────────────┐
        │   Domain Services           │
        │   (src/services/)           │
        │                             │
        │  - RouteOptimizer           │
        │  - MapsService              │
        │  - ImageParser              │
        │  - ChefMarketParser         │
        └─────────────┬──────────────┘
                      │
        ┌─────────────▼──────────────┐
        │   Repositories             │
        │   (src/repositories/)      │
        │                             │
        │  - OrderRepository         │
        │  - RouteRepository         │
        │  - CallStatusRepository    │
        │  - SettingsRepository      │
        └─────────────┬──────────────┘
                      │
        ┌─────────────▼──────────────┐
        │   Database Layer           │
        │   (src/database/)          │
        │                             │
        │  - Connection              │
        │  - Models (SQLAlchemy)      │
        └────────────────────────────┘
```

---

## 🎯 Принципы разделения

### 1. **Presentation Layer (UI)**
- **Не содержит бизнес-логики**
- Только валидация входных данных
- Форматирование ответов для конкретного UI
- Обработка ошибок UI-уровня

### 2. **Application Services**
- **Оркестрация бизнес-логики**
- Координируют вызовы Domain Services и Repositories
- Не зависят от UI (Telegram или REST)
- Возвращают чистые данные (DTO)

### 3. **Domain Services**
- **Чистая бизнес-логика**
- Не знают о БД или UI
- Могут использоваться из любого UI

### 4. **Repositories**
- **Абстракция доступа к данным**
- Инкапсулируют SQLAlchemy запросы
- Возвращают Domain Models или DTO

---

## 📁 Новая структура проекта

```
src/
├── api/                          # REST API слой
│   ├── __init__.py
│   ├── main.py                   # FastAPI app
│   ├── dependencies.py           # DI контейнер
│   ├── auth.py                   # Аутентификация
│   ├── routes/                   # API endpoints
│   │   ├── orders.py
│   │   ├── routes.py
│   │   ├── calls.py
│   │   └── settings.py
│   └── schemas/                  # Pydantic схемы для API
│       ├── orders.py
│       ├── routes.py
│       └── responses.py
│
├── bot/                          # Telegram Bot слой
│   ├── __init__.py
│   ├── main.py                   # Bot initialization
│   ├── dependencies.py          # DI контейнер для бота
│   └── handlers/                 # Обработчики (упрощенные)
│       ├── base_handlers.py
│       ├── order_handlers.py     # Только форматирование
│       ├── route_handlers.py     # Только форматирование
│       └── ...
│
├── application/                  # Application Services (НОВОЕ)
│   ├── __init__.py
│   ├── services/
│   │   ├── order_service.py     # Бизнес-логика заказов
│   │   ├── route_service.py     # Бизнес-логика маршрутов
│   │   ├── call_service.py      # Бизнес-логика звонков
│   │   ├── import_service.py    # Бизнес-логика импорта
│   │   └── settings_service.py  # Бизнес-логика настроек
│   └── dto/                     # Data Transfer Objects
│       ├── order_dto.py
│       ├── route_dto.py
│       └── call_dto.py
│
├── services/                     # Domain Services (существующие, очищенные)
│   ├── route_optimizer.py       # Чистая логика оптимизации
│   ├── maps_service.py          # Чистая логика карт
│   ├── image_parser.py          # Чистая логика парсинга
│   └── ...
│
├── repositories/                 # Repositories (НОВОЕ)
│   ├── __init__.py
│   ├── order_repository.py
│   ├── route_repository.py
│   ├── call_status_repository.py
│   ├── settings_repository.py
│   └── base_repository.py      # Базовый класс
│
├── models/                       # Domain Models (существующие)
│   ├── order.py
│   └── geocache.py
│
├── database/                     # Database Layer (существующее)
│   ├── connection.py
│   └── models.py                # SQLAlchemy models
│
└── utils/                        # Утилиты
    ├── message_utils.py         # FakeMessage и т.д.
    ├── formatters.py            # Форматирование для UI
    └── error_handler.py         # Централизованная обработка ошибок
```

---

## 🔄 Пример миграции: Оптимизация маршрута

### Текущая реализация (плохо):

```python
# src/bot/handlers/route_handlers.py
def handle_optimize_route(self, message):
    user_id = message.from_user.id
    today = date.today()
    
    # Загрузка данных из БД (в handler!)
    orders_data = self.parent.db_service.get_today_orders(user_id)
    start_location_data = self.parent.db_service.get_start_location(user_id, today)
    
    # Преобразование данных (в handler!)
    orders = [Order(**od) for od in orders_data]
    
    # Вызов оптимизации (в handler!)
    optimized_route = self.parent.route_optimizer.optimize_route_sync(...)
    
    # Сохранение в БД (в handler!)
    self.parent.db_service.save_route_data(user_id, today, route_data)
    
    # Форматирование ответа (в handler!)
    self.bot.reply_to(message, "✅ Маршрут оптимизирован!")
```

**Проблемы:**
- Вся логика в handler
- Невозможно использовать из API
- Сложно тестировать
- Дублирование кода при создании API

---

### Новая реализация (хорошо):

#### 1. Application Service

```python
# src/application/services/route_service.py
from typing import List, Optional
from datetime import date
from src.application.dto.route_dto import RouteOptimizationRequest, RouteOptimizationResult
from src.repositories.order_repository import OrderRepository
from src.repositories.route_repository import RouteRepository
from src.services.route_optimizer import RouteOptimizer

class RouteService:
    """Сервис для работы с маршрутами (независим от UI)"""
    
    def __init__(
        self,
        order_repo: OrderRepository,
        route_repo: RouteRepository,
        route_optimizer: RouteOptimizer
    ):
        self.order_repo = order_repo
        self.route_repo = route_repo
        self.route_optimizer = route_optimizer
    
    def optimize_route(
        self,
        user_id: int,
        order_date: date = None
    ) -> RouteOptimizationResult:
        """Оптимизировать маршрут для пользователя"""
        if order_date is None:
            order_date = date.today()
        
        # 1. Загружаем заказы через репозиторий
        orders = self.order_repo.get_active_orders(user_id, order_date)
        if not orders:
            raise ValueError("Нет активных заказов")
        
        # 2. Загружаем точку старта
        start_location = self.route_repo.get_start_location(user_id, order_date)
        if not start_location:
            raise ValueError("Точка старта не установлена")
        
        # 3. Вызываем оптимизацию (Domain Service)
        optimized_route = self.route_optimizer.optimize_route_sync(
            orders=orders,
            start_location=(start_location.latitude, start_location.longitude),
            start_time=start_location.start_time,
            user_id=user_id
        )
        
        # 4. Сохраняем результат через репозиторий
        self.route_repo.save_route(user_id, order_date, optimized_route)
        
        # 5. Возвращаем DTO (чистые данные)
        return RouteOptimizationResult(
            route_id=optimized_route.id,
            total_distance=optimized_route.total_distance,
            total_time=optimized_route.total_time,
            points_count=len(optimized_route.points)
        )
```

#### 2. Telegram Bot Handler (упрощенный)

```python
# src/bot/handlers/route_handlers.py
from src.application.services.route_service import RouteService
from src.utils.formatters import format_route_message
from src.utils.error_handler import handle_errors

class RouteHandlers:
    def __init__(self, bot, route_service: RouteService):
        self.bot = bot
        self.route_service = route_service
    
    @handle_errors
    def handle_optimize_route(self, message):
        """Обработчик команды оптимизации (только UI логика)"""
        user_id = message.from_user.id
        
        try:
            # Вызываем Application Service (чистая бизнес-логика)
            result = self.route_service.optimize_route(user_id)
            
            # Форматируем ответ для Telegram
            text = format_route_message(result)
            self.bot.reply_to(message, text)
            
        except ValueError as e:
            # Обрабатываем бизнес-ошибки
            self.bot.reply_to(message, f"❌ {str(e)}")
        except Exception as e:
            # Обрабатываем технические ошибки
            logger.error(f"Ошибка оптимизации: {e}", exc_info=True)
            self.bot.reply_to(message, "❌ Произошла ошибка при оптимизации")
```

#### 3. REST API Controller

```python
# src/api/routes/routes.py
from fastapi import APIRouter, Depends, HTTPException
from src.application.services.route_service import RouteService
from src.api.schemas.routes import RouteOptimizationResponse
from src.api.dependencies import get_route_service, get_current_user

router = APIRouter(prefix="/routes", tags=["routes"])

@router.post("/optimize", response_model=RouteOptimizationResponse)
async def optimize_route(
    route_service: RouteService = Depends(get_route_service),
    user_id: int = Depends(get_current_user)
):
    """Оптимизировать маршрут (REST API)"""
    try:
        # Вызываем тот же Application Service!
        result = route_service.optimize_route(user_id)
        
        # Возвращаем JSON (Pydantic автоматически сериализует)
        return RouteOptimizationResponse(
            route_id=result.route_id,
            total_distance=result.total_distance,
            total_time=result.total_time,
            points_count=result.points_count
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Ошибка оптимизации: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Внутренняя ошибка сервера")
```

---

## 🔧 Dependency Injection

### DI Контейнер для Application Services

```python
# src/api/dependencies.py (или src/bot/dependencies.py)
from dependency_injector import containers, providers
from src.repositories.order_repository import OrderRepository
from src.repositories.route_repository import RouteRepository
from src.application.services.route_service import RouteService
from src.services.route_optimizer import RouteOptimizer
from src.services.maps_service import MapsService

class ApplicationContainer(containers.DeclarativeContainer):
    """DI контейнер для Application Services"""
    
    # Repositories
    order_repository = providers.Singleton(OrderRepository)
    route_repository = providers.Singleton(RouteRepository)
    
    # Domain Services
    maps_service = providers.Singleton(MapsService)
    route_optimizer = providers.Factory(
        RouteOptimizer,
        maps_service=maps_service
    )
    
    # Application Services
    route_service = providers.Factory(
        RouteService,
        order_repo=order_repository,
        route_repo=route_repository,
        route_optimizer=route_optimizer
    )

# Глобальный контейнер
container = ApplicationContainer()

# Функции для FastAPI Depends
def get_route_service() -> RouteService:
    return container.route_service()
```

---

## 📱 Пример использования из мобильного приложения

### REST API Endpoints

```python
# src/api/routes/orders.py
@router.get("/orders", response_model=List[OrderResponse])
async def get_orders(
    user_id: int = Depends(get_current_user),
    order_service: OrderService = Depends(get_order_service)
):
    """Получить список заказов"""
    orders = order_service.get_today_orders(user_id)
    return [OrderResponse.from_dto(o) for o in orders]

@router.post("/orders", response_model=OrderResponse)
async def create_order(
    order_data: CreateOrderRequest,
    user_id: int = Depends(get_current_user),
    order_service: OrderService = Depends(get_order_service)
):
    """Создать заказ"""
    order = order_service.create_order(user_id, order_data)
    return OrderResponse.from_dto(order)

@router.put("/orders/{order_number}", response_model=OrderResponse)
async def update_order(
    order_number: str,
    order_data: UpdateOrderRequest,
    user_id: int = Depends(get_current_user),
    order_service: OrderService = Depends(get_order_service)
):
    """Обновить заказ"""
    order = order_service.update_order(user_id, order_number, order_data)
    return OrderResponse.from_dto(order)
```

### Мобильное приложение (пример)

```dart
// Flutter пример
class CourierApi {
  final String baseUrl = "https://api.courier.example.com";
  
  Future<List<Order>> getOrders() async {
    final response = await http.get(
      Uri.parse("$baseUrl/api/orders"),
      headers: {"Authorization": "Bearer $token"},
    );
    return (json.decode(response.body) as List)
        .map((o) => Order.fromJson(o))
        .toList();
  }
  
  Future<Route> optimizeRoute() async {
    final response = await http.post(
      Uri.parse("$baseUrl/api/routes/optimize"),
      headers: {"Authorization": "Bearer $token"},
    );
    return Route.fromJson(json.decode(response.body));
  }
}
```

---

## 🔄 Миграция CallNotifier

### Проблема: CallNotifier зависит от Telegram Bot

```python
# Текущая реализация (плохо)
class CallNotifier:
    def __init__(self, bot, courier_bot):
        self.bot = bot  # Зависимость от Telegram!
```

### Решение: Event-Driven Architecture

```python
# src/application/services/call_service.py
class CallService:
    """Сервис для работы со звонками (независим от UI)"""
    
    def check_pending_calls(self, user_id: int) -> List[CallNotification]:
        """Проверить pending звонки и вернуть список для уведомления"""
        # Бизнес-логика проверки
        pending_calls = self.call_repo.get_pending_calls(user_id)
        notifications = []
        
        for call in pending_calls:
            if self._should_notify(call):
                notifications.append(CallNotification(
                    user_id=user_id,
                    order_number=call.order_number,
                    call_time=call.call_time,
                    message=self._generate_message(call)
                ))
        
        return notifications

# src/bot/services/telegram_notifier.py
class TelegramNotifier:
    """Уведомления через Telegram"""
    
    def __init__(self, bot):
        self.bot = bot
    
    def send_call_notification(self, notification: CallNotification):
        self.bot.send_message(
            notification.user_id,
            notification.message
        )

# src/api/services/push_notifier.py
class PushNotifier:
    """Уведомления через Push (для мобильного приложения)"""
    
    def send_call_notification(self, notification: CallNotification):
        # Отправка через FCM/APNS
        pass

# src/bot/main.py
def setup_call_monitoring():
    call_service = container.call_service()
    telegram_notifier = TelegramNotifier(bot)
    
    def check_and_notify():
        for user_id in active_users:
            notifications = call_service.check_pending_calls(user_id)
            for notification in notifications:
                telegram_notifier.send_call_notification(notification)
    
    # Запускаем в фоне
    threading.Thread(target=check_and_notify, daemon=True).start()
```

---

## 📋 План миграции

### Этап 1: Подготовка (3-5 дней)

1. **Создать структуру папок**
   - `src/application/`
   - `src/repositories/`
   - `src/api/`

2. **Создать DI контейнер**
   - Настроить `dependency-injector`
   - Создать базовые провайдеры

3. **Создать базовые репозитории**
   - `BaseRepository`
   - `OrderRepository`
   - `RouteRepository`

### Этап 2: Миграция Application Services (5-7 дней)

1. **OrderService**
   - Вынести логику из `OrderHandlers`
   - Создать DTO для заказов
   - Написать тесты

2. **RouteService**
   - Вынести логику из `RouteHandlers`
   - Создать DTO для маршрутов
   - Написать тесты

3. **CallService**
   - Рефакторинг `CallNotifier`
   - Разделить на сервис и notifier
   - Написать тесты

### Этап 3: Рефакторинг Bot Handlers (3-5 дней)

1. **Упростить handlers**
   - Оставить только форматирование
   - Использовать Application Services
   - Убрать прямые обращения к БД

2. **Обновить форматирование**
   - Вынести в `src/utils/formatters.py`
   - Создать отдельные форматтеры для Telegram

### Этап 4: Создание REST API (5-7 дней)

1. **Настроить FastAPI**
   - Создать `src/api/main.py`
   - Настроить CORS, аутентификацию
   - Подключить DI контейнер

2. **Создать endpoints**
   - `/api/orders` - CRUD заказов
   - `/api/routes` - работа с маршрутами
   - `/api/calls` - график звонков
   - `/api/settings` - настройки

3. **Создать Pydantic схемы**
   - Request models
   - Response models
   - Validation

### Этап 5: Тестирование и документация (3-5 дней)

1. **Интеграционные тесты**
   - Тесты Application Services
   - Тесты API endpoints
   - Тесты Bot handlers

2. **Документация**
   - OpenAPI/Swagger для API
   - Архитектурная диаграмма
   - Миграционный гайд

---

## ✅ Преимущества новой архитектуры

1. **Переиспользование кода**
   - Одна бизнес-логика для Bot и API
   - Легко добавить новый UI (Web, CLI)

2. **Тестируемость**
   - Application Services легко тестировать (без UI)
   - Моки для репозиториев
   - Изолированное тестирование

3. **Масштабируемость**
   - API и Bot могут работать на разных серверах
   - Горизонтальное масштабирование API
   - Независимое развертывание

4. **Поддерживаемость**
   - Четкое разделение ответственности
   - Легко найти и изменить код
   - Меньше дублирования

5. **Гибкость**
   - Легко добавить GraphQL вместо REST
   - Легко заменить Telegram на другой мессенджер
   - Легко добавить WebSocket для real-time

---

## 🎯 Итоговая структура

```
Courier Bot (Telegram)  ──┐
                           ├──> Application Services ──> Domain Services ──> Repositories ──> Database
REST API (Mobile App)  ─────┘
```

**Одна бизнес-логика, множество UI!**

