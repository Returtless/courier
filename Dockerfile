FROM python:3.11-slim

WORKDIR /app

# Установка системных зависимостей + зависимости для Playwright
ENV DEBIAN_FRONTEND=noninteractive
ENV DEBCONF_NONINTERACTIVE_SEEN=true

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    tzdata \
    wget \
    gnupg \
    && rm -rf /var/lib/apt/lists/*

# Копирование requirements
COPY requirements.txt .

# Установка Python зависимостей
RUN pip install --no-cache-dir -r requirements.txt

# Установка браузеров для Playwright
RUN playwright install chromium
RUN DEBIAN_FRONTEND=noninteractive playwright install-deps chromium

# Копирование кода приложения
COPY . .

# Создание директории для БД (если используется SQLite)
RUN mkdir -p /app/data

# Переменные окружения
ENV PYTHONUNBUFFERED=1

# Команда запуска
CMD ["python", "main.py"]

