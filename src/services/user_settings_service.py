import logging
from typing import Optional
from src.database.connection import get_db_session
from src.models.order import UserSettingsDB, UserSettings

logger = logging.getLogger(__name__)


class UserSettingsService:
    """Сервис для управления настройками пользователей"""
    
    def get_settings(self, user_id: int) -> UserSettings:
        """
        Получить настройки пользователя.
        Если настроек нет - создать с дефолтными значениями.
        """
        with get_db_session() as session:
            settings_db = session.query(UserSettingsDB).filter(
                UserSettingsDB.user_id == user_id
            ).first()
            
            if not settings_db:
                # Создаем настройки по умолчанию
                settings_db = UserSettingsDB(user_id=user_id)
                session.add(settings_db)
                session.commit()
                session.refresh(settings_db)
                logger.info(f"✨ Созданы настройки по умолчанию для user_id={user_id}")
            
            return UserSettings.model_validate(settings_db)
    
    def update_setting(self, user_id: int, setting_name: str, value: int) -> bool:
        """
        Обновить одну настройку пользователя.
        
        Args:
            user_id: ID пользователя
            setting_name: Имя настройки (например, 'call_advance_minutes')
            value: Новое значение
            
        Returns:
            True если обновление прошло успешно, False иначе
        """
        try:
            with get_db_session() as session:
                settings_db = session.query(UserSettingsDB).filter(
                    UserSettingsDB.user_id == user_id
                ).first()
                
                if not settings_db:
                    # Создаем настройки, если их нет
                    settings_db = UserSettingsDB(user_id=user_id)
                    session.add(settings_db)
                
                # Проверяем, что такая настройка существует
                if not hasattr(settings_db, setting_name):
                    logger.warning(f"Неизвестная настройка: {setting_name}")
                    return False
                
                # Обновляем значение
                setattr(settings_db, setting_name, value)
                session.commit()
                
                logger.info(f"✅ Обновлена настройка {setting_name}={value} для user_id={user_id}")
                return True
                
        except Exception as e:
            logger.error(f"Ошибка обновления настройки: {e}", exc_info=True)
            return False
    
    def update_settings(self, user_id: int, **kwargs) -> bool:
        """
        Обновить несколько настроек пользователя.
        
        Args:
            user_id: ID пользователя
            **kwargs: Настройки для обновления (например, call_advance_minutes=15)
            
        Returns:
            True если обновление прошло успешно, False иначе
        """
        try:
            with get_db_session() as session:
                settings_db = session.query(UserSettingsDB).filter(
                    UserSettingsDB.user_id == user_id
                ).first()
                
                if not settings_db:
                    # Создаем настройки, если их нет
                    settings_db = UserSettingsDB(user_id=user_id)
                    session.add(settings_db)
                
                # Обновляем все переданные настройки
                for key, value in kwargs.items():
                    if hasattr(settings_db, key):
                        setattr(settings_db, key, value)
                    else:
                        logger.warning(f"Неизвестная настройка: {key}")
                
                session.commit()
                logger.info(f"✅ Обновлены настройки для user_id={user_id}: {kwargs}")
                return True
                
        except Exception as e:
            logger.error(f"Ошибка обновления настроек: {e}", exc_info=True)
            return False
    
    def reset_settings(self, user_id: int) -> bool:
        """
        Сбросить настройки пользователя к значениям по умолчанию.
        
        Args:
            user_id: ID пользователя
            
        Returns:
            True если сброс прошел успешно, False иначе
        """
        try:
            with get_db_session() as session:
                settings_db = session.query(UserSettingsDB).filter(
                    UserSettingsDB.user_id == user_id
                ).first()
                
                if settings_db:
                    # Удаляем текущие настройки
                    session.delete(settings_db)
                
                # Создаем новые настройки с дефолтными значениями
                new_settings = UserSettingsDB(user_id=user_id)
                session.add(new_settings)
                session.commit()
                
                logger.info(f"🔄 Настройки сброшены к значениям по умолчанию для user_id={user_id}")
                return True
                
        except Exception as e:
            logger.error(f"Ошибка сброса настроек: {e}", exc_info=True)
            return False
    
    def get_setting_description(self, setting_name: str) -> str:
        """Получить описание настройки на русском языке"""
        descriptions = {
            'call_advance_minutes': '⏱️ Время звонка до приезда (минут)',
            'call_retry_interval_minutes': '🔄 Интервал между повторными звонками (минут)',
            'call_max_attempts': '📞 Максимальное количество попыток дозвона',
            'service_time_minutes': '⏰ Время нахождения на точке (минут)',
            'parking_time_minutes': '🚗 Время на парковку и подход (минут)',
            'traffic_check_interval_minutes': '🚦 Интервал проверки пробок (минут)',
            'traffic_threshold_percent': '⚠️ Порог уведомления о пробках (%)',
        }
        return descriptions.get(setting_name, setting_name)

