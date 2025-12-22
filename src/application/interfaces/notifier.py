"""
Интерфейс для отправки уведомлений
Позволяет легко заменить Telegram на другие каналы (Push, SMS, Email и т.д.)
"""
from abc import ABC, abstractmethod
from typing import Protocol
from src.application.dto.call_dto import CallNotificationDTO


class Notifier(Protocol):
    """Протокол для отправки уведомлений"""
    
    def send_call_notification(self, notification: CallNotificationDTO) -> bool:
        """
        Отправить уведомление о звонке
        
        Args:
            notification: Данные уведомления
            
        Returns:
            True если успешно отправлено, False в случае ошибки
        """
        ...


class AbstractNotifier(ABC):
    """Абстрактный базовый класс для уведомлений"""
    
    @abstractmethod
    def send_call_notification(self, notification: CallNotificationDTO) -> bool:
        """
        Отправить уведомление о звонке
        
        Args:
            notification: Данные уведомления
            
        Returns:
            True если успешно отправлено, False в случае ошибки
        """
        pass

