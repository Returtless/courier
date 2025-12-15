"""
Unit-тесты для UserSettingsService
"""
import pytest
from unittest.mock import patch
from src.services.user_settings_service import UserSettingsService
from src.models.order import UserSettingsDB


@pytest.mark.unit
class TestUserSettingsService:
    """Тесты сервиса настроек пользователя"""
    
    def test_get_settings_default(self, test_db_session):
        """Получение дефолтных настроек для нового пользователя"""
        settings_service = UserSettingsService()
        user_id = 1001
        
        with patch('src.services.user_settings_service.get_db_session') as mock_session:
            mock_session.return_value.__enter__.return_value = test_db_session
            
            settings = settings_service.get_settings(user_id)
            
            # Проверяем дефолтные значения
            assert settings.call_advance_minutes == 10
            assert settings.service_time_minutes == 10
            assert settings.call_max_attempts == 3
            assert settings.call_retry_interval_minutes == 2
    
    def test_get_settings_existing(self, test_db_session):
        """Получение существующих настроек"""
        settings_service = UserSettingsService()
        user_id = 1002
        
        # Создаем настройки
        user_settings = UserSettingsDB(
            user_id=user_id,
            call_advance_minutes=30,
            service_time_minutes=15
        )
        
        test_db_session.add(user_settings)
        test_db_session.commit()
        
        with patch('src.services.user_settings_service.get_db_session') as mock_session:
            mock_session.return_value.__enter__.return_value = test_db_session
            
            settings = settings_service.get_settings(user_id)
            
            assert settings.call_advance_minutes == 30
            assert settings.service_time_minutes == 15
    
    def test_update_settings(self, test_db_session):
        """Обновление настроек"""
        settings_service = UserSettingsService()
        user_id = 1003
        
        # Создаем начальные настройки
        user_settings = UserSettingsDB(
            user_id=user_id,
            call_advance_minutes=10
        )
        
        test_db_session.add(user_settings)
        test_db_session.commit()
        
        with patch('src.services.user_settings_service.get_db_session') as mock_session:
            mock_session.return_value.__enter__.return_value = test_db_session
            
            # Обновляем через kwargs
            settings_service.update_settings(
                user_id,
                call_advance_minutes=25,
                service_time_minutes=20
            )
            
            # Проверяем
            updated = test_db_session.query(UserSettingsDB).filter_by(
                user_id=user_id
            ).first()
            
            assert updated.call_advance_minutes == 25
            assert updated.service_time_minutes == 20


@pytest.mark.unit
class TestUserSettingsMultipleUsers:
    """Тесты изоляции настроек разных пользователей"""
    
    def test_different_users_different_settings(self, test_db_session):
        """У разных пользователей разные настройки"""
        settings_service = UserSettingsService()
        
        user1_id = 2001
        user2_id = 2002
        
        # Создаем настройки для двух пользователей
        settings1 = UserSettingsDB(
            user_id=user1_id,
            call_advance_minutes=30
        )
        
        settings2 = UserSettingsDB(
            user_id=user2_id,
            call_advance_minutes=50
        )
        
        test_db_session.add_all([settings1, settings2])
        test_db_session.commit()
        
        with patch('src.services.user_settings_service.get_db_session') as mock_session:
            mock_session.return_value.__enter__.return_value = test_db_session
            
            # Получаем настройки для каждого
            user1_settings = settings_service.get_settings(user1_id)
            user2_settings = settings_service.get_settings(user2_id)
            
            # Проверяем изоляцию
            assert user1_settings.call_advance_minutes == 30
            assert user2_settings.call_advance_minutes == 50
            assert user1_settings.call_advance_minutes != user2_settings.call_advance_minutes
