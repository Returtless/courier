"""
Dependency Injection Container для Application Services
"""
from dependency_injector import containers, providers

# Импортируем репозитории
from src.repositories.order_repository import OrderRepository
from src.repositories.route_repository import RouteRepository
from src.repositories.call_status_repository import CallStatusRepository


class ApplicationContainer(containers.DeclarativeContainer):
    """DI контейнер для Application Services и Repositories"""
    
    # Repositories (Singleton - один экземпляр на все приложение)
    order_repository = providers.Singleton(OrderRepository)
    route_repository = providers.Singleton(RouteRepository)
    call_status_repository = providers.Singleton(CallStatusRepository)
    
    # Application Services будут добавлены на следующих этапах
    # order_service = providers.Factory(...)
    # route_service = providers.Factory(...)


# Глобальный контейнер
container: ApplicationContainer = None


def init_container() -> ApplicationContainer:
    """Инициализация контейнера"""
    global container
    container = ApplicationContainer()
    return container


def get_container() -> ApplicationContainer:
    """Получить глобальный контейнер"""
    global container
    if container is None:
        container = init_container()
    return container

