# Тестирование в Docker

## Варианты запуска тестов в Docker

### Вариант 1: Из хост-системы (Windows/Linux/Mac)

**Windows (PowerShell):**
```powershell
.\test_in_docker.ps1
```

**Linux/Mac:**
```bash
chmod +x test_in_docker.sh
./test_in_docker.sh
```

### Вариант 2: Внутри контейнера (если вы уже внутри)

Если вы уже находитесь внутри Docker контейнера (как в вашем случае):

```bash
# Просто запустите тесты напрямую
python test_bot_functions.py
```

Или для локального тестирования с SQLite:

```bash
python test_local_sqlite.py
```

## Текущая ситуация

Вы находитесь внутри Docker контейнера (`root@adc66e66adc7:/app#`), поэтому:

1. **Не используйте PowerShell скрипты** - они для Windows хост-системы
2. **Используйте команды напрямую** - вы уже в правильной среде

## Команды для запуска тестов внутри контейнера

```bash
# Вариант 1: Тесты с реальной БД (PostgreSQL)
python test_bot_functions.py

# Вариант 2: Тесты с SQLite (быстрее, не требует PostgreSQL)
python test_local_sqlite.py
```

## Если контейнер не запущен

Если нужно запустить тесты из хост-системы:

**Windows:**
```powershell
docker exec courier_bot python test_bot_functions.py
```

**Linux/Mac:**
```bash
docker exec courier_bot python test_bot_functions.py
```

