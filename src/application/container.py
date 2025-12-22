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
    
    # Services
    from src.application.services.order_service import OrderService
    from src.application.services.route_service import RouteService
    from src.application.services.call_service import CallService
    from src.services.maps_service import MapsService
    
    # Singleton services
    maps_service = providers.Singleton(MapsService)
    
    # Factory services
    order_service = providers.Factory(
        OrderService,
        order_repository=order_repository,
        call_status_repository=call_status_repository
    )
    
    route_service = providers.Factory(
        RouteService,
        route_repository=route_repository,
        order_service=order_service,
        call_status_repository=call_status_repository,
        maps_service=maps_service
    )
    
    call_service = providers.Factory(
        CallService,
        call_status_repository=call_status_repository,
        order_repository=order_repository
    )


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

