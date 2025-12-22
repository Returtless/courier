"""
FastAPI приложение для REST API
"""
import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager

from src.application.container import init_container

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Управление жизненным циклом приложения"""
    # Startup
    logger.info("🚀 Запуск FastAPI приложения")
    # Инициализируем DI контейнер
    init_container()
    logger.info("✅ DI контейнер инициализирован")
    
    yield
    
    # Shutdown
    logger.info("🛑 Остановка FastAPI приложения")


app = FastAPI(
    title="Courier Route Optimization API",
    description=(
        "REST API для управления заказами и маршрутами курьера.\n\n"
        "## Аутентификация\n\n"
        "API использует Bearer токен для аутентификации. "
        "В качестве токена используется Telegram user_id.\n\n"
        "Пример заголовка:\n"
        "```\n"
        "Authorization: Bearer 123456789\n"
        "```\n\n"
        "## Endpoints\n\n"
        "- `/api/orders` - управление заказами\n"
        "- `/api/routes` - управление маршрутами\n"
        "- `/api/calls` - управление звонками\n"
        "- `/api/settings` - настройки пользователя"
    ),
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_tags=[
        {
            "name": "Orders",
            "description": "Операции с заказами: создание, получение, обновление, отметка доставки"
        },
        {
            "name": "Routes",
            "description": "Операции с маршрутами: оптимизация, получение, настройка точки старта"
        },
        {
            "name": "Calls",
            "description": "Операции со звонками: график звонков, подтверждение, отклонение"
        },
        {
            "name": "Settings",
            "description": "Настройки пользователя: время звонка, интервалы повторов"
        }
    ]
)

# Настройка CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # В продакшене указать конкретные домены
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Middleware для обработки ошибок
@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    """Глобальный обработчик исключений"""
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal server error",
            "message": str(exc) if logger.level <= logging.DEBUG else "An error occurred"
        }
    )


@app.get("/")
async def root():
    """Корневой endpoint"""
    return {
        "message": "Courier Route Optimization API",
        "status": "ok",
        "version": "1.0.0",
        "docs": "/docs"
    }


@app.get("/health")
async def health():
    """Health check endpoint"""
    return {"status": "healthy"}


# Подключаем роуты
from src.api.routes import orders
from src.api.routes import routes as routes_module
from src.api.routes import calls as calls_module
from src.api.routes import settings as settings_module
from src.api.routes import import_routes as import_module

app.include_router(orders.router, prefix="/api/orders", tags=["Orders"])
app.include_router(routes_module.router, prefix="/api/routes", tags=["Routes"])
app.include_router(calls_module.router, prefix="/api/calls", tags=["Calls"])
app.include_router(settings_module.router, prefix="/api/settings", tags=["Settings"])
app.include_router(import_module.router, prefix="/api/import", tags=["Import"])

