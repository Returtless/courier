# Скрипт для запуска тестов в Docker контейнере (PowerShell)

Write-Host "🐳 Запуск тестов в Docker контейнере..." -ForegroundColor Cyan

# Проверяем, запущен ли контейнер
$containerRunning = docker ps --filter "name=courier_bot" --format "{{.Names}}"
if (-not $containerRunning) {
    Write-Host "❌ Контейнер courier_bot не запущен" -ForegroundColor Red
    Write-Host "💡 Запустите сначала: docker-compose up -d" -ForegroundColor Yellow
    exit 1
}

# Запускаем тесты в контейнере
Write-Host "📋 Запуск тестов..." -ForegroundColor Cyan
docker exec courier_bot python test_bot_functions.py

Write-Host "✅ Тесты завершены" -ForegroundColor Green

