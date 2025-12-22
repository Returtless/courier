"""
Утилиты для работы с сообщениями Telegram
"""
from typing import Optional


class FakeMessage:
    """
    Фейковое сообщение для вызова handlers из callback
    Используется когда нужно вызвать handler, который ожидает message, из callback
    """
    
    def __init__(self, chat_id: int, user, message_id: Optional[int] = None, text: Optional[str] = None):
        """
        Args:
            chat_id: ID чата
            user: Объект пользователя (обычно call.from_user)
            message_id: ID сообщения (опционально)
            text: Текст сообщения (опционально)
        """
        self.chat = type('obj', (object,), {'id': chat_id})()
        self.from_user = user
        self.message_id = message_id
        self.text = text
        self.location = None
        self.photo = None
        self.document = None

