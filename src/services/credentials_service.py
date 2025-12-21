"""
Сервис для безопасного хранения учетных данных пользователей
"""
import logging
from cryptography.fernet import Fernet
from sqlalchemy.orm import Session
from src.database.connection import get_db_session
from src.models.order import UserCredentialsDB
from src.config import settings

logger = logging.getLogger(__name__)


class CredentialsService:
    """Сервис для шифрования и хранения учетных данных"""
    
    def __init__(self):
        # Получаем ключ шифрования из настроек (Pydantic автоматически читает из env файла и переменных окружения)
        encryption_key = settings.encryption_key
        
        # Дополнительная проверка через os.getenv для диагностики (но не используем как основной источник)
        import os
        env_key_direct = os.getenv("ENCRYPTION_KEY") or os.getenv("encryption_key")
        
        # Детальная диагностика - проверяем все возможные варианты имени
        logger.info(f"🔍 Диагностика ENCRYPTION_KEY:")
        logger.info(f"   - os.getenv('ENCRYPTION_KEY'): {os.getenv('ENCRYPTION_KEY')}")
        logger.info(f"   - os.getenv('encryption_key'): {os.getenv('encryption_key')}")
        logger.info(f"   - settings.encryption_key: {settings.encryption_key}")
        
        # Проверяем все переменные окружения, содержащие 'encryption' или 'key'
        all_env_vars = {k: v for k, v in os.environ.items() if 'encryption' in k.lower() or (k.lower() == 'encryption_key')}
        if all_env_vars:
            logger.info(f"   - Найдены переменные окружения с 'encryption': {list(all_env_vars.keys())}")
        else:
            logger.warning(f"   - ⚠️ НЕ найдено переменных окружения с 'encryption' в имени!")
        
        # Дополнительная диагностика: показываем ВСЕ переменные окружения, которые начинаются с известных префиксов
        known_prefixes = ['TELEGRAM', 'YANDEX', 'TWO_GIS', 'DATABASE', 'ENCRYPTION', 'LLM']
        relevant_vars = {k: v[:20] + '...' if len(v) > 20 else v for k, v in os.environ.items() 
                        if any(k.startswith(prefix) for prefix in known_prefixes)}
        logger.info(f"🔍 Все релевантные переменные окружения в контейнере:")
        for key, value in sorted(relevant_vars.items()):
            logger.info(f"   - {key}: {value}")
        
        # Проверяем, почему settings.encryption_key пустой, если другие переменные читаются
        if not encryption_key:
            logger.warning(f"⚠️ settings.encryption_key пустой, но другие переменные читаются:")
            logger.warning(f"   - settings.yandex_maps_api_key: {settings.yandex_maps_api_key[:10] if settings.yandex_maps_api_key else None}...")
            logger.warning(f"   - settings.two_gis_api_key: {settings.two_gis_api_key[:10] if settings.two_gis_api_key else None}...")
            logger.warning(f"   - settings.telegram_bot_token: {settings.telegram_bot_token[:10] if settings.telegram_bot_token else None}...")
            logger.warning(f"   - Проверьте, что в Portainer переменная называется именно 'ENCRYPTION_KEY' (заглавными буквами)")
        
        # Если settings.encryption_key пустой, но есть в os.getenv - используем его
        # (это может быть, если переменная установлена в Portainer, но Pydantic не подхватил)
        if not encryption_key and env_key_direct:
            logger.info(f"✅ ENCRYPTION_KEY найден в переменных окружения процесса, но не в settings. Используем из env.")
            encryption_key = env_key_direct
        elif encryption_key and env_key_direct and encryption_key != env_key_direct:
            logger.warning(f"⚠️ ENCRYPTION_KEY из settings ({encryption_key[:10]}...) отличается от переменной окружения ({env_key_direct[:10]}...). Используем из settings.")
        elif encryption_key:
            logger.info(f"✅ ENCRYPTION_KEY найден в settings")
        
        # Проверяем, что ключ установлен и не является дефолтным значением
        if not encryption_key or encryption_key == "your_encryption_key_here":
            # Генерируем новый ключ
            logger.warning("⚠️ ENCRYPTION_KEY не установлен! Генерирую новый ключ...")
            logger.warning("⚠️ Проверьте:")
            logger.warning("   1. Файл 'env' содержит строку: ENCRYPTION_KEY=...")
            logger.warning("   2. В docker-compose.yml используется env_file: - env")
            logger.warning("   3. Контейнер перезапущен после добавления переменной")
            encryption_key = Fernet.generate_key().decode()
            logger.warning(f"⚠️ ВАЖНО! Добавьте в файл 'env' или переменные окружения:\nENCRYPTION_KEY={encryption_key}")
            logger.warning("⚠️ Без этого ключа вы не сможете расшифровать сохраненные пароли после перезапуска!")
        
        # Проверяем, что ключ в правильном формате
        try:
            self.cipher = Fernet(encryption_key.encode() if isinstance(encryption_key, str) else encryption_key)
        except Exception as e:
            # Если ключ невалидный, генерируем новый
            logger.error(f"❌ Невалидный ENCRYPTION_KEY: {e}")
            encryption_key = Fernet.generate_key().decode()
            logger.warning(f"⚠️ Сгенерирован новый ключ. Добавьте в файл 'env':\nENCRYPTION_KEY={encryption_key}")
            self.cipher = Fernet(encryption_key.encode())
    
    def encrypt(self, text: str) -> str:
        """Зашифровать текст"""
        if not text:
            return ""
        return self.cipher.encrypt(text.encode()).decode()
    
    def decrypt(self, encrypted_text: str) -> str:
        """Расшифровать текст"""
        if not encrypted_text:
            return ""
        try:
            return self.cipher.decrypt(encrypted_text.encode()).decode()
        except Exception as e:
            logger.error(f"Ошибка расшифровки: {e}")
            raise ValueError("Не удалось расшифровать данные. Возможно, ENCRYPTION_KEY был изменен.")
    
    def save_credentials(self, user_id: int, login: str, password: str, site: str = "chefmarket") -> bool:
        """Сохранить учетные данные пользователя"""
        try:
            encrypted_login = self.encrypt(login)
            encrypted_password = self.encrypt(password)
            
            with get_db_session() as session:
                # Проверяем, есть ли уже запись для этого пользователя
                existing = session.query(UserCredentialsDB).filter(
                    UserCredentialsDB.user_id == user_id
                ).first()
                
                if existing:
                    # Обновляем существующую запись
                    existing.encrypted_login = encrypted_login
                    existing.encrypted_password = encrypted_password
                    existing.site = site
                    logger.info(f"Обновлены учетные данные для user_id={user_id}, site={site}")
                else:
                    # Создаем новую запись
                    credentials = UserCredentialsDB(
                        user_id=user_id,
                        site=site,
                        encrypted_login=encrypted_login,
                        encrypted_password=encrypted_password
                    )
                    session.add(credentials)
                    logger.info(f"Созданы учетные данные для user_id={user_id}, site={site}")
                
                session.commit()
                return True
        
        except Exception as e:
            logger.error(f"Ошибка сохранения учетных данных: {e}", exc_info=True)
            return False
    
    def get_credentials(self, user_id: int, site: str = "chefmarket") -> tuple[str, str] | None:
        """Получить учетные данные пользователя (login, password)"""
        try:
            with get_db_session() as session:
                credentials = session.query(UserCredentialsDB).filter(
                    UserCredentialsDB.user_id == user_id,
                    UserCredentialsDB.site == site
                ).first()
                
                if not credentials:
                    return None
                
                login = self.decrypt(credentials.encrypted_login)
                password = self.decrypt(credentials.encrypted_password)
                
                return (login, password)
        
        except Exception as e:
            logger.error(f"Ошибка получения учетных данных: {e}", exc_info=True)
            return None
    
    def delete_credentials(self, user_id: int, site: str = "chefmarket") -> bool:
        """Удалить учетные данные пользователя"""
        try:
            with get_db_session() as session:
                deleted = session.query(UserCredentialsDB).filter(
                    UserCredentialsDB.user_id == user_id,
                    UserCredentialsDB.site == site
                ).delete()
                
                session.commit()
                
                if deleted:
                    logger.info(f"Удалены учетные данные для user_id={user_id}, site={site}")
                    return True
                return False
        
        except Exception as e:
            logger.error(f"Ошибка удаления учетных данных: {e}", exc_info=True)
            return False
    
    def has_credentials(self, user_id: int, site: str = "chefmarket") -> bool:
        """Проверить, есть ли сохраненные учетные данные"""
        try:
            with get_db_session() as session:
                exists = session.query(UserCredentialsDB).filter(
                    UserCredentialsDB.user_id == user_id,
                    UserCredentialsDB.site == site
                ).first() is not None
                
                return exists
        
        except Exception as e:
            logger.error(f"Ошибка проверки учетных данных: {e}", exc_info=True)
            return False

