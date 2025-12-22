"""
Тесты для REST API настроек пользователя
"""
import pytest
from datetime import date
from fastapi.testclient import TestClient
from unittest.mock import Mock, MagicMock, patch
from sqlalchemy.orm import Session

from src.api.main import app
from src.services.user_settings_service import UserSettings


@pytest.fixture
def client():
    """Тестовый клиент FastAPI"""
    return TestClient(app)


@pytest.fixture
def sample_settings():
    """Пример настроек пользователя"""
    settings = Mock(spec=UserSettings)
    settings.user_id = 123
    settings.call_advance_minutes = 10
    settings.call_retry_interval_minutes = 2
    settings.call_max_attempts = 3
    settings.service_time_minutes = 10
    settings.parking_time_minutes = 7
    settings.traffic_check_interval_minutes = 5
    settings.traffic_threshold_percent = 50
    return settings


class TestSettingsAPIGet:
    """Тесты для GET /api/settings"""
    
    @patch('src.api.routes.settings.UserSettingsService')
    @patch('src.api.routes.settings.get_current_user')
    @patch('src.api.routes.settings.get_db')
    def test_get_settings_success(
        self,
        mock_get_db,
        mock_get_current_user,
        mock_user_settings_service,
        client,
        sample_settings
    ):
        """Тест успешного получения настроек"""
        from src.api.auth import User
        mock_user = User(user_id=123)
        mock_user.id = 123  # Используется в settings.py
        mock_get_current_user.return_value = mock_user
        
        # Мокаем UserSettingsService
        mock_service_instance = MagicMock()
        mock_service_instance.get_settings.return_value = sample_settings
        mock_user_settings_service.return_value = mock_service_instance
        
        mock_db = MagicMock()
        mock_get_db.return_value = mock_db
        
        response = client.get(
            "/api/settings",
            headers={"Authorization": "Bearer 123"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["user_id"] == 123
        assert data["call_advance_minutes"] == 10
        assert data["call_retry_interval_minutes"] == 2
        assert data["call_max_attempts"] == 3
        assert data["service_time_minutes"] == 10
        assert data["parking_time_minutes"] == 7
        assert data["traffic_check_interval_minutes"] == 5
        assert data["traffic_threshold_percent"] == 50


class TestSettingsAPIUpdate:
    """Тесты для PUT /api/settings"""
    
    @patch('src.api.routes.settings.UserSettingsService')
    @patch('src.api.routes.settings.get_current_user')
    @patch('src.api.routes.settings.get_db')
    def test_update_settings_success(
        self,
        mock_get_db,
        mock_get_current_user,
        mock_user_settings_service,
        client,
        sample_settings
    ):
        """Тест успешного обновления настроек"""
        from src.api.auth import User
        mock_user = User(user_id=123)
        mock_user.id = 123  # Используется в settings.py
        mock_get_current_user.return_value = mock_user
        
        # Мокаем UserSettingsService
        mock_service_instance = MagicMock()
        
        # Обновленные настройки
        updated_settings = Mock(spec=UserSettings)
        updated_settings.user_id = 123
        updated_settings.call_advance_minutes = 15  # Изменено
        updated_settings.call_retry_interval_minutes = 2
        updated_settings.call_max_attempts = 3
        updated_settings.service_time_minutes = 10
        updated_settings.parking_time_minutes = 7
        updated_settings.traffic_check_interval_minutes = 5
        updated_settings.traffic_threshold_percent = 50
        
        mock_service_instance.update_settings.return_value = True
        mock_service_instance.get_settings.return_value = updated_settings
        mock_user_settings_service.return_value = mock_service_instance
        
        mock_db = MagicMock()
        mock_get_db.return_value = mock_db
        
        response = client.put(
            "/api/settings",
            json={
                "call_advance_minutes": 15
            },
            headers={"Authorization": "Bearer 123"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["call_advance_minutes"] == 15
        # Проверяем, что update_settings был вызван (первый аргумент - user_id, затем kwargs)
        mock_service_instance.update_settings.assert_called_once()
        # Проверяем, что передан user_id и kwargs
        call_args = mock_service_instance.update_settings.call_args
        assert call_args[0][0] == 123  # user_id (позиционный аргумент)
        assert "call_advance_minutes" in call_args[1]  # kwargs
        assert call_args[1]["call_advance_minutes"] == 15
    
    @patch('src.api.routes.settings.UserSettingsService')
    @patch('src.api.routes.settings.get_current_user')
    @patch('src.api.routes.settings.get_db')
    def test_update_settings_multiple_fields(
        self,
        mock_get_db,
        mock_get_current_user,
        mock_user_settings_service,
        client,
        sample_settings
    ):
        """Тест обновления нескольких полей настроек"""
        from src.api.auth import User
        mock_user = User(user_id=123)
        mock_user.id = 123
        mock_get_current_user.return_value = mock_user
        
        # Мокаем UserSettingsService
        mock_service_instance = MagicMock()
        
        updated_settings = Mock(spec=UserSettings)
        updated_settings.user_id = 123
        updated_settings.call_advance_minutes = 20
        updated_settings.call_retry_interval_minutes = 5
        updated_settings.call_max_attempts = 5
        updated_settings.service_time_minutes = 15
        updated_settings.parking_time_minutes = 10
        updated_settings.traffic_check_interval_minutes = 10
        updated_settings.traffic_threshold_percent = 75
        
        mock_service_instance.update_settings.return_value = True
        mock_service_instance.get_settings.return_value = updated_settings
        mock_user_settings_service.return_value = mock_service_instance
        
        mock_db = MagicMock()
        mock_get_db.return_value = mock_db
        
        response = client.put(
            "/api/settings",
            json={
                "call_advance_minutes": 20,
                "call_retry_interval_minutes": 5,
                "call_max_attempts": 5,
                "service_time_minutes": 15
            },
            headers={"Authorization": "Bearer 123"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["call_advance_minutes"] == 20
        assert data["call_retry_interval_minutes"] == 5
        assert data["call_max_attempts"] == 5
        assert data["service_time_minutes"] == 15
    
    @patch('src.api.routes.settings.UserSettingsService')
    @patch('src.api.routes.settings.get_current_user')
    @patch('src.api.routes.settings.get_db')
    def test_update_settings_empty(
        self,
        mock_get_db,
        mock_get_current_user,
        mock_user_settings_service,
        client
    ):
        """Тест обновления настроек без указания полей"""
        from src.api.auth import User
        mock_get_current_user.return_value = User(user_id=123, id=123)
        
        # Мокаем UserSettingsService
        mock_service_instance = MagicMock()
        mock_user_settings_service.return_value = mock_service_instance
        
        mock_db = MagicMock()
        mock_get_db.return_value = mock_db
        
        response = client.put(
            "/api/settings",
            json={},
            headers={"Authorization": "Bearer 123"}
        )
        
        assert response.status_code == 400
        data = response.json()
        assert "detail" in data
        assert "не указаны" in data["detail"].lower()


class TestSettingsAPIReset:
    """Тесты для POST /api/settings/reset"""
    
    @patch('src.api.routes.settings.UserSettingsService')
    @patch('src.api.routes.settings.get_current_user')
    @patch('src.api.routes.settings.get_db')
    def test_reset_settings_success(
        self,
        mock_get_db,
        mock_get_current_user,
        mock_user_settings_service,
        client,
        sample_settings
    ):
        """Тест успешного сброса настроек к значениям по умолчанию"""
        from src.api.auth import User
        mock_user = User(user_id=123)
        mock_user.id = 123
        mock_get_current_user.return_value = mock_user
        
        # Мокаем UserSettingsService
        mock_service_instance = MagicMock()
        
        # Настройки после сброса (значения по умолчанию)
        reset_settings = Mock(spec=UserSettings)
        reset_settings.user_id = 123
        reset_settings.call_advance_minutes = 10
        reset_settings.call_retry_interval_minutes = 2
        reset_settings.call_max_attempts = 3
        reset_settings.service_time_minutes = 10
        reset_settings.parking_time_minutes = 7
        reset_settings.traffic_check_interval_minutes = 5
        reset_settings.traffic_threshold_percent = 50
        
        mock_service_instance.reset_settings.return_value = True
        mock_service_instance.get_settings.return_value = reset_settings
        mock_user_settings_service.return_value = mock_service_instance
        
        mock_db = MagicMock()
        mock_get_db.return_value = mock_db
        
        response = client.post(
            "/api/settings/reset",
            headers={"Authorization": "Bearer 123"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["user_id"] == 123
        assert data["call_advance_minutes"] == 10
        # Проверяем, что reset_settings был вызван (используется current_user.id)
        mock_service_instance.reset_settings.assert_called_once()
