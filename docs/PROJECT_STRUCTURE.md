# 📚 Полная документация структуры проекта

**Проект:** Courier Route Optimization Bot  
**Версия:** 1.0  
**Дата:** 2025-01-XX

---

## 📁 Структура проекта

```
courier/
├── src/                          # Исходный код
│   ├── bot/                      # Telegram Bot слой
│   │   ├── handlers/             # Обработчики сообщений
│   │   └── main.py               # Точка входа бота
│   ├── services/                 # Domain Services (бизнес-логика)
│   ├── models/                   # Domain Models (Pydantic + SQLAlchemy)
│   ├── database/                 # Database Layer
│   ├── config.py                 # Конфигурация
│   └── utils/                    # Утилиты
├── tests/                        # Тесты
├── alembic/                      # Миграции БД
├── data/                         # Данные (Docker volume)
├── main.py                       # Точка входа приложения
├── docker-compose.yml            # Docker конфигурация
└── requirements.txt              # Зависимости
```

---

## 🏗️ Архитектура

### Текущая архитектура (до рефакторинга)

```
Telegram Bot Handlers
    ↓
Services (Domain Logic)
    ↓
DatabaseService (Data Access)
    ↓
SQLAlchemy Models
    ↓
Database
```

**Проблемы:**
- Handlers содержат бизнес-логику
- Прямые обращения к БД из handlers
- Тесная связанность через `self.parent`

---

## 📦 Модули и классы

### 1. Bot Layer (`src/bot/`)

#### 1.1. `CourierBot` (`src/bot/handlers/__init__.py`)

**Назначение:** Главный класс бота, координирует все handlers и сервисы.

**Методы:**

| Метод | Описание | Параметры | Возвращает |
|-------|----------|-----------|------------|
| `__init__` | Инициализация бота и сервисов | `bot: TeleBot, llm_service=None` | - |
| `register_handlers` | Регистрация всех обработчиков | - | - |
| `_handle_message_with_state` | Главный обработчик сообщений с состояниями | `message` | - |
| `get_user_state` | Получить состояние пользователя | `user_id: int` | `Dict` |
| `update_user_state` | Обновить состояние пользователя | `user_id: int, key: str, value` | - |
| `clear_user_state` | Очистить состояние пользователя | `user_id: int` | - |
| `_main_menu_markup` | Разметка главного меню | `user_id: int = None` | `ReplyKeyboardMarkup` |
| `_orders_menu_markup` | Разметка меню заказов | `user_id: int = None` | `ReplyKeyboardMarkup` |
| `_route_menu_markup` | Разметка меню маршрута | - | `ReplyKeyboardMarkup` |
| `_add_orders_menu_markup` | Разметка меню добавления заказов | - | `ReplyKeyboardMarkup` |

**Атрибуты:**
- `bot: TeleBot` - экземпляр Telegram бота
- `maps_service: MapsService` - сервис карт
- `db_service: DatabaseService` - сервис БД
- `call_notifier: CallNotifier` - уведомления о звонках
- `settings_service: UserSettingsService` - настройки пользователей
- `credentials_service: CredentialsService` - учетные данные
- `user_states: Dict` - состояния пользователей (в памяти)

---

#### 1.2. `BaseHandlers` (`src/bot/handlers/base_handlers.py`)

**Назначение:** Базовые обработчики (команды, меню, роутинг callback).

**Методы:**

| Метод | Описание | Параметры | Возвращает |
|-------|----------|-----------|------------|
| `register` | Регистрация обработчиков | - | - |
| `handle_start` | Обработка `/start` | `message` | - |
| `handle_help` | Обработка `/help` | `message` | - |
| `handle_orders_menu` | Обработка кнопки "📦 Заказы" | `message` | - |
| `handle_route_menu` | Обработка кнопки "🗺️ Маршрут" | `message` | - |
| `handle_settings_menu` | Обработка кнопки "⚙️ Настройки" | `message` | - |
| `handle_back_to_main` | Возврат в главное меню | `message` | - |
| `handle_callback_query` | Роутинг callback запросов | `call` | - |

---

#### 1.3. `OrderHandlers` (`src/bot/handlers/order_handlers.py`)

**Назначение:** Обработка всех операций с заказами.

**Методы:**

| Метод | Описание | Параметры | Возвращает |
|-------|----------|-----------|------------|
| `register` | Регистрация обработчиков | - | - |
| `handle_callback` | Обработка callback для заказов | `call` | - |
| `handle_photo` | Обработка фото (скриншот заказа) | `message` | - |
| `handle_load_from_screenshot` | Загрузка из скриншота | `message` | - |
| `handle_add_orders` | Добавление заказов | `message` | - |
| `process_order_number` | Парсинг номера заказа | `message` | - |
| `show_order_details` | Показать детали заказа | `user_id, order_number, chat_id` | - |
| `mark_order_delivered` | Отметить заказ доставленным | `user_id, order_number, chat_id` | - |
| `handle_delivered_orders` | Показать доставленные заказы | `message` | - |
| `_update_order_field` | Обновить поле заказа | `user_id, order_number, field_name, field_value, message` | - |
| `_update_manual_arrival_time` | Обновить ручное время прибытия | `user_id, order_number, manual_arrival_time, message` | - |
| `_update_manual_call_time` | Обновить ручное время звонка | `user_id, order_number, manual_call_time, message` | - |

**Состояния:**
- `waiting_for_orders` - ожидание ввода заказов
- `waiting_for_order_phone` - ожидание телефона
- `waiting_for_order_name` - ожидание имени
- `waiting_for_order_comment` - ожидание комментария
- `waiting_for_order_entrance` - ожидание подъезда
- `waiting_for_order_apartment` - ожидание квартиры
- `waiting_for_order_delivery_time` - ожидание времени доставки
- `waiting_for_manual_arrival_time` - ожидание ручного времени прибытия
- `waiting_for_manual_call_time` - ожидание ручного времени звонка
- `searching_order_by_number` - поиск заказа по номеру

---

#### 1.4. `RouteHandlers` (`src/bot/handlers/route_handlers.py`)

**Назначение:** Обработка операций с маршрутами.

**Методы:**

| Метод | Описание | Параметры | Возвращает |
|-------|----------|-----------|------------|
| `register` | Регистрация обработчиков | - | - |
| `handle_callback` | Обработка callback для маршрутов | `call` | - |
| `handle_set_start` | Установка точки старта | `message` | - |
| `handle_set_start_location_geo` | Установка геопозиции старта | `message` | - |
| `handle_set_start_location_address` | Установка адреса старта | `message` | - |
| `handle_optimize_route` | Оптимизация маршрута | `message` | - |
| `handle_show_route` | Показать маршрут | `message` | - |
| `handle_show_calls` | Показать график звонков | `message` | - |
| `handle_current_order` | Показать текущий заказ | `message` | - |
| `handle_show_order_by_index` | Показать заказ по индексу | `call, index: int` | - |
| `handle_mark_order_delivered` | Отметить заказ доставленным | `call` | - |
| `handle_edit_order_from_route` | Редактировать заказ из маршрута | `call` | - |
| `handle_reset_day` | Сброс данных за день | `message` | - |
| `handle_recalculate_without_manual` | Пересчет без ручных времен | `call` | - |
| `_format_route_summary` | Форматирование маршрута | `user_id, route_points_data, orders_dict, start_location_data, maps_service` | `List[Dict]` |
| `_show_order_at_index` | Показать заказ по индексу | `chat_id, user_id, active_points, index, message_id` | - |

**Состояния:**
- `waiting_for_start_location` - ожидание геопозиции
- `waiting_for_start_address` - ожидание адреса
- `confirming_start_location` - подтверждение адреса
- `waiting_for_start_time` - ожидание времени старта

---

#### 1.5. `CallHandlers` (`src/bot/handlers/call_handlers.py`)

**Назначение:** Обработка операций со звонками.

**Методы:**

| Метод | Описание | Параметры | Возвращает |
|-------|----------|-----------|------------|
| `register` | Регистрация обработчиков | - | - |
| `handle_callback` | Обработка callback для звонков | `call` | - |
| `handle_call_confirm` | Подтверждение звонка | `call, call_status_id` | - |
| `handle_call_reject` | Отклонение звонка | `call, call_status_id` | - |
| `process_call_comment` | Обработка комментария к звонку | `message, state_data` | - |

**Состояния:**
- `waiting_for_call_comment` - ожидание комментария к звонку

---

#### 1.6. `SettingsHandlers` (`src/bot/handlers/settings_handlers.py`)

**Назначение:** Обработка настроек пользователя.

**Методы:**

| Метод | Описание | Параметры | Возвращает |
|-------|----------|-----------|------------|
| `register` | Регистрация обработчиков | - | - |
| `handle_callback` | Обработка callback для настроек | `call` | - |
| `show_settings_menu` | Показать меню настроек | `message` | - |
| `handle_setting_update` | Обновление настройки | `call, setting_name` | - |
| `handle_setting_value` | Обработка нового значения | `message, state_data` | - |
| `handle_settings_reset` | Сброс настроек | `call` | - |
| `handle_settings_back` | Возврат из настроек | `call` | - |
| `handle_chefmarket_credentials_menu` | Меню учетных данных | `call` | - |
| `handle_reset_day_from_settings` | Сброс дня из настроек | `call` | - |

**Состояния:**
- `waiting_for_setting_value` - ожидание значения настройки

---

#### 1.7. `ImportHandlers` (`src/bot/handlers/import_handlers.py`)

**Назначение:** Импорт заказов из внешних источников.

**Методы:**

| Метод | Описание | Параметры | Возвращает |
|-------|----------|-----------|------------|
| `register` | Регистрация обработчиков | - | - |
| `handle_callback` | Обработка callback для импорта | `call` | - |
| `handle_set_credentials` | Установка учетных данных | `message` | - |
| `handle_delete_credentials` | Удаление учетных данных | `message` | - |
| `handle_import_orders` | Импорт заказов | `message` | - |
| `process_chefmarket_login` | Обработка логина ШефМаркет | `message, state_data` | - |
| `process_chefmarket_password` | Обработка пароля ШефМаркет | `message, state_data` | - |

**Состояния:**
- `waiting_for_chefmarket_login` - ожидание логина
- `waiting_for_chefmarket_password` - ожидание пароля

---

#### 1.8. `TrafficHandlers` (`src/bot/handlers/traffic_handlers.py`)

**Назначение:** Обработка мониторинга пробок.

**Методы:**

| Метод | Описание | Параметры | Возвращает |
|-------|----------|-----------|------------|
| `register` | Регистрация обработчиков | - | - |
| `handle_monitor` | Запуск мониторинга | `message` | - |
| `handle_stop_monitor` | Остановка мониторинга | `message` | - |
| `handle_traffic_status` | Статус мониторинга | `message` | - |

---

### 2. Services Layer (`src/services/`)

#### 2.1. `DatabaseService` (`src/services/db_service.py`)

**Назначение:** Абстракция доступа к базе данных.

**Методы:**

| Метод | Описание | Параметры | Возвращает |
|-------|----------|-----------|------------|
| `get_today_orders` | Получить заказы за сегодня | `user_id, session=None` | `List[Dict]` |
| `get_orders_by_date` | Получить заказы за дату | `user_id, order_date, session=None` | `List[Dict]` |
| `save_order` | Сохранить заказ | `user_id, order, order_date, session=None, partial_update=False` | `OrderDB` |
| `update_order` | Обновить заказ | `user_id, order_number, updates, order_date, session=None` | `bool` |
| `get_order_by_number` | Получить заказ по номеру | `user_id, order_number, order_date, session=None` | `OrderDB\|None` |
| `get_start_location` | Получить точку старта | `user_id, location_date, session=None` | `Dict\|None` |
| `save_start_location` | Сохранить точку старта | `user_id, location_data, location_date, session=None` | `StartLocationDB` |
| `get_route_data` | Получить данные маршрута | `user_id, route_date, session=None` | `Dict\|None` |
| `save_route_data` | Сохранить данные маршрута | `user_id, route_data, route_date, session=None` | `RouteDataDB` |
| `get_confirmed_calls` | Получить подтвержденные звонки | `user_id, call_date, session=None` | `List[Dict]` |
| `get_orders_status_by_numbers` | Получить статусы заказов | `user_id, order_numbers, order_date, session=None` | `Dict[str, str]` |
| `get_order_status` | Получить статус заказа | `user_id, order_number, order_date, session=None` | `str\|None` |
| `delete_all_data_by_date` | Удалить все данные за дату | `user_id, target_date, session=None` | - |

---

#### 2.2. `RouteOptimizer` (`src/services/route_optimizer.py`)

**Назначение:** Оптимизация маршрутов с использованием OR-Tools.

**Методы:**

| Метод | Описание | Параметры | Возвращает |
|-------|----------|-----------|------------|
| `optimize_route_sync` | Оптимизировать маршрут | `orders, start_location, start_time, vehicle_capacity, user_id, use_fallback` | `OptimizedRoute` |
| `_build_matrices` | Построить матрицы расстояний/времени | `locations` | `Tuple[np.ndarray, np.ndarray]` |
| `_build_fallback_route` | Построить простой маршрут (fallback) | `orders, start_location, start_time, user_id` | `OptimizedRoute` |
| `_solve_vrp` | Решить задачу VRP с OR-Tools | `orders, start_location, start_time, user_id, use_fallback` | `OptimizedRoute\|None` |

**Особенности:**
- Использует OR-Tools для оптимизации
- Поддерживает временные окна доставки
- Поддерживает ручные времена прибытия/звонка
- Fallback механизм при ошибке OR-Tools

---

#### 2.3. `MapsService` (`src/services/maps_service.py`)

**Назначение:** Работа с картами и геокодированием.

**Методы:**

| Метод | Описание | Параметры | Возвращает |
|-------|----------|-----------|------------|
| `geocode_address_sync` | Геокодирование адреса (синхронно) | `address: str` | `Tuple[float, float, str\|None]` |
| `geocode_address` | Геокодирование адреса (асинхронно) | `address: str` | `Tuple[float, float, str\|None]` |
| `get_route_sync` | Получить маршрут (синхронно) | `start_lat, start_lon, end_lat, end_lon` | `Tuple[float, float]` |
| `build_route_links` | Построить ссылки на маршрут | `start_lat, start_lon, end_lat, end_lon` | `Dict` |
| `build_point_links` | Построить ссылки на точку | `lat, lon, gid, zoom` | `Dict` |

**Особенности:**
- Поддержка 2GIS API (основной)
- Поддержка Yandex Maps API (резервный)
- Кэширование результатов геокодирования
- Кэширование маршрутов

---

#### 2.4. `CallNotifier` (`src/services/call_notifier.py`)

**Назначение:** Уведомления о времени звонков.

**Методы:**

| Метод | Описание | Параметры | Возвращает |
|-------|----------|-----------|------------|
| `start` | Запустить фоновую проверку | - | - |
| `stop` | Остановить проверку | - | - |
| `create_call_status` | Создать/обновить запись о звонке | `user_id, order_number, call_time, phone, customer_name, call_date, is_manual_call, is_manual_arrival, arrival_time, manual_arrival_time` | `CallStatusDB\|None` |
| `_check_loop` | Основной цикл проверки | - | - |
| `_check_pending_calls` | Проверить pending звонки | - | - |
| `_check_retry_calls` | Проверить повторные звонки | - | - |
| `_send_call_notification` | Отправить уведомление о звонке | `call_id, session, is_retry` | - |

**Особенности:**
- Работает в отдельном потоке
- Проверяет звонки каждые 30 секунд
- Поддерживает повторные попытки
- Фильтрует доставленные заказы

---

#### 2.5. `TrafficMonitor` (`src/services/traffic_monitor.py`)

**Назначение:** Мониторинг пробок в реальном времени.

**Методы:**

| Метод | Описание | Параметры | Возвращает |
|-------|----------|-----------|------------|
| `start_monitoring` | Начать мониторинг | `user_id, route, orders, start_location, start_time` | - |
| `stop_monitoring` | Остановить мониторинг | `user_id` | - |
| `add_callback` | Добавить callback для уведомлений | `callback: Callable` | - |
| `get_current_traffic_status` | Получить текущий статус | `user_id` | `Dict` |

**Особенности:**
- Поддерживает несколько пользователей одновременно
- Потокобезопасный
- Использует настройки пользователя для интервала проверки

---

#### 2.6. `UserSettingsService` (`src/services/user_settings_service.py`)

**Назначение:** Управление настройками пользователей.

**Методы:**

| Метод | Описание | Параметры | Возвращает |
|-------|----------|-----------|------------|
| `get_settings` | Получить настройки | `user_id` | `UserSettings` |
| `update_setting` | Обновить одну настройку | `user_id, setting_name, value` | `bool` |
| `reset_to_defaults` | Сбросить к умолчанию | `user_id` | `bool` |

---

#### 2.7. `CredentialsService` (`src/services/credentials_service.py`)

**Назначение:** Шифрование и хранение учетных данных.

**Методы:**

| Метод | Описание | Параметры | Возвращает |
|-------|----------|-----------|------------|
| `encrypt` | Зашифровать текст | `text: str` | `str` |
| `decrypt` | Расшифровать текст | `encrypted_text: str` | `str` |
| `save_credentials` | Сохранить учетные данные | `user_id, login, password, site` | `bool` |
| `get_credentials` | Получить учетные данные | `user_id, site` | `Tuple[str, str]\|None` |
| `delete_credentials` | Удалить учетные данные | `user_id, site` | `bool` |
| `has_credentials` | Проверить наличие данных | `user_id, site` | `bool` |

**Особенности:**
- Использует Fernet (симметричное шифрование)
- Автоматическая генерация ключа при отсутствии

---

#### 2.8. `ImageOrderParser` (`src/services/image_parser.py`)

**Назначение:** Парсинг данных заказа из изображений (OCR).

**Методы:**

| Метод | Описание | Параметры | Возвращает |
|-------|----------|-----------|------------|
| `parse_order_from_image` | Парсинг заказа из изображения | `image_data: bytes` | `Dict\|None` |
| `_parse_text` | Парсинг текста | `text: str` | `Dict\|None` |
| `_extract_order_number` | Извлечь номер заказа | `text: str` | `str\|None` |
| `_extract_address` | Извлечь адрес | `text: str` | `str\|None` |
| `_extract_customer_name` | Извлечь имя клиента | `text: str` | `str\|None` |
| `_extract_phone` | Извлечь телефон | `text: str` | `str\|None` |
| `_extract_comment` | Извлечь комментарий | `text: str` | `str\|None` |
| `_extract_delivery_time_window` | Извлечь временное окно | `text: str` | `str\|None` |
| `_filter_service_phrases` | Фильтрация служебных фраз | `text: str` | `str` |
| `_clean_field_value` | Очистка значения поля | `value: str` | `str` |
| `_fix_ocr_name_errors` | Исправление OCR ошибок в именах | `name: str` | `str` |

**Особенности:**
- Использует Tesseract OCR
- Поддержка русского и английского языков
- Фильтрация служебных фраз
- Исправление частых OCR ошибок

---

#### 2.9. `ChefMarketParser` (`src/services/chefmarket_parser.py`)

**Назначение:** Парсинг заказов из веб-приложения ШефМаркет.

**Методы:**

| Метод | Описание | Параметры | Возвращает |
|-------|----------|-----------|------------|
| `import_orders` | Импорт заказов | `login, password` | `List[Dict]` |

**Особенности:**
- Использует Playwright для автоматизации браузера
- Сохраняет скриншоты для отладки
- Обрабатывает ошибки авторизации

---

#### 2.10. `LLMService` (`src/services/llm_service.py`)

**Назначение:** Работа с LLM для анализа комментариев (пока отключено).

**Методы:**

| Метод | Описание | Параметры | Возвращает |
|-------|----------|-----------|------------|
| `initialize` | Инициализация модели | - | - |
| `analyze_order_comment` | Анализ комментария | `comment: str` | `Dict` |
| `_simple_call_script` | Простой скрипт звонка | `order, estimated_delivery` | `str` |

---

### 3. Models Layer (`src/models/`)

#### 3.1. SQLAlchemy Models (`src/models/order.py`)

**`OrderDB`** - Заказы
- `id`, `user_id`, `order_date`
- `customer_name`, `phone`, `address`
- `latitude`, `longitude`, `gis_id`
- `comment`, `delivery_time_start`, `delivery_time_end`
- `delivery_time_window`, `status`, `order_number`
- `entrance_number`, `apartment_number`
- `estimated_delivery_time`, `call_time`, `route_order`

**`StartLocationDB`** - Точки старта
- `id`, `user_id`, `location_date`
- `location_type` ("geo" или "address")
- `address`, `latitude`, `longitude`, `start_time`

**`RouteDataDB`** - Данные маршрутов
- `id`, `user_id`, `route_date`
- `route_summary` (JSON), `call_schedule` (JSON)
- `route_order` (JSON)
- `total_distance`, `total_time`, `estimated_completion`

**`CallStatusDB`** - Статусы звонков
- `id`, `user_id`, `order_number`, `call_date`
- `call_time`, `arrival_time`
- `is_manual_call`, `is_manual_arrival`, `manual_arrival_time`
- `phone`, `customer_name`
- `status` (pending, confirmed, rejected, failed, inactive)
- `attempts`, `next_attempt_time`, `confirmation_comment`

**`UserSettingsDB`** - Настройки пользователей
- `id`, `user_id`
- `call_advance_minutes`, `call_retry_interval_minutes`, `call_max_attempts`
- `service_time_minutes`, `parking_time_minutes`
- `traffic_check_interval_minutes`, `traffic_threshold_percent`

**`UserCredentialsDB`** - Учетные данные
- `id`, `user_id`, `site`
- `encrypted_login`, `encrypted_password`

**`GeocodeCacheDB`** (`src/models/geocache.py`) - Кэш геокодирования
- `id`, `address`, `latitude`, `longitude`, `gis_id`

---

#### 3.2. Pydantic Models (`src/models/order.py`)

**`Order`** - Domain модель заказа
- Все поля опциональны, кроме `status`
- Автоматический парсинг `delivery_time_window`
- Метод `get_time_window_minutes()` для получения окна в минутах

**`RoutePoint`** - Точка маршрута
- `order: Order`
- `estimated_arrival: datetime`
- `distance_from_previous: float`
- `time_from_previous: float`

**`OptimizedRoute`** - Оптимизированный маршрут
- `points: List[RoutePoint]`
- `total_distance: float`
- `total_time: float`
- `estimated_completion: datetime`

**`UserSettings`** - Настройки пользователя (Pydantic)

---

### 4. Database Layer (`src/database/`)

#### 4.1. `connection.py`

**Функции:**

| Функция | Описание | Параметры | Возвращает |
|---------|----------|-----------|------------|
| `get_db` | Генератор для FastAPI-style DI | - | `Generator[Session]` |
| `get_db_session` | Контекстный менеджер для БД | - | `ContextManager[Session]` |

**Переменные:**
- `engine: Engine` - SQLAlchemy engine
- `SessionLocal: sessionmaker` - Фабрика сессий
- `Base: DeclarativeMeta` - Базовый класс для моделей

---

### 5. Config (`src/config.py`)

**`Settings`** - Конфигурация приложения (Pydantic BaseSettings)

**Поля:**
- `telegram_bot_token: str`
- `yandex_maps_api_key: Optional[str]`
- `two_gis_api_key: Optional[str]`
- `database_url: str`
- `encryption_key: Optional[str]`
- `llm_model_path: str`
- `llm_device: str`
- `llm_max_tokens: int`

**Особенности:**
- Читает из переменных окружения
- Не использует `.env` файл (только Portainer)

---

## 🔄 Потоки данных

### 1. Оптимизация маршрута

```
User → RouteHandlers.handle_optimize_route()
    → DatabaseService.get_today_orders()
    → DatabaseService.get_start_location()
    → RouteOptimizer.optimize_route_sync()
        → MapsService.geocode_address_sync() (если нужно)
        → MapsService.get_route_sync() (для матриц)
        → OR-Tools VRP Solver
    → DatabaseService.save_route_data()
    → CallNotifier.create_call_status() (для каждого заказа)
    → Bot.send_message() (результат)
```

### 2. Добавление заказа

```
User → OrderHandlers.handle_add_orders()
    → OrderHandlers.process_order_number()
    → Order() (Pydantic модель)
    → DatabaseService.save_order()
    → Bot.send_message() (подтверждение)
```

### 3. Уведомление о звонке

```
CallNotifier._check_loop() (фоновый поток)
    → CallNotifier._check_pending_calls()
    → CallNotifier._send_call_notification()
    → Bot.send_message() (уведомление)
    → CallStatusDB.status = "sent"
```

---

## 📊 Зависимости между модулями

```
CourierBot
├── BaseHandlers → CourierBot
├── OrderHandlers → CourierBot → DatabaseService, ImageOrderParser
├── RouteHandlers → CourierBot → DatabaseService, RouteOptimizer, MapsService
├── CallHandlers → CourierBot → DatabaseService
├── SettingsHandlers → CourierBot → UserSettingsService, CredentialsService
├── ImportHandlers → CourierBot → ChefMarketParser, CredentialsService
└── TrafficHandlers → CourierBot → TrafficMonitor

RouteOptimizer → MapsService, UserSettingsService
MapsService → (2GIS API, Yandex Maps API)
CallNotifier → DatabaseService, UserSettingsService, Bot
TrafficMonitor → MapsService, UserSettingsService
DatabaseService → (SQLAlchemy Models)
```

---

## 🗄️ База данных

### Таблицы:

1. **orders** - Заказы
2. **start_locations** - Точки старта
3. **route_data** - Данные маршрутов
4. **call_status** - Статусы звонков
5. **user_settings** - Настройки пользователей
6. **user_credentials** - Учетные данные
7. **geocode_cache** - Кэш геокодирования

### Индексы:

- `orders`: `user_id`, `order_date`, `order_number`
- `start_locations`: `user_id`, `location_date`
- `route_data`: `user_id`, `route_date`
- `call_status`: `user_id`, `call_date`, `order_number`, `status`, `call_time`
- `user_settings`: `user_id` (unique)
- `user_credentials`: `user_id` (unique)
- `geocode_cache`: `address`

---

## 🔐 Безопасность

1. **Шифрование учетных данных**
   - Fernet (симметричное шифрование)
   - Ключ хранится в переменных окружения

2. **Многопользовательский режим**
   - Все данные привязаны к `user_id`
   - Пользователи не видят чужие данные

3. **Валидация данных**
   - Pydantic модели для валидации
   - SQLAlchemy constraints на уровне БД

---

## 📝 Примечания

1. **Состояния пользователей** хранятся в памяти (`CourierBot.user_states`)
   - Не сохраняются при перезапуске
   - Не масштабируются для нескольких инстансов

2. **CallNotifier** зависит от Telegram Bot
   - Невозможно использовать для других UI

3. **Handlers содержат бизнес-логику**
   - Сложно тестировать
   - Невозможно переиспользовать для API

4. **Прямые обращения к БД из handlers**
   - Нарушение слоев архитектуры
   - Дублирование кода

---

## 🎯 Планы на рефакторинг

См. `REFACTORING_PLAN.md` и `API_ARCHITECTURE_PLAN.md` для детального плана улучшения архитектуры.

---

**Последнее обновление:** 2025-01-XX

