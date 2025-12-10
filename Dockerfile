FROM python:3.11-slim

WORKDIR /app

# Установка системных зависимостей
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# Копирование requirements
COPY requirements.txt .

# Установка Python зависимостей
RUN pip install --no-cache-dir -r requirements.txt

# Копирование кода приложения
COPY . .

# Создание директории для БД (если используется SQLite)
RUN mkdir -p /app/data

# Переменные окружения
ENV PYTHONUNBUFFERED=1

# Команда запуска
CMD ["python", "main.py"]

