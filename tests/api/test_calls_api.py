"""
Тесты для REST API звонков
"""
import pytest
from datetime import date, datetime, time
from fastapi.testclient import TestClient
from unittest.mock import Mock, MagicMock, patch, ANY
from sqlalchemy.orm import Session

from src.api.main import app
from src.models.order import CallStatusDB
from src.application.dto.call_dto import CallStatusDTO


@pytest.fixture
def client():
    """Тестовый клиент FastAPI"""
    return TestClient(app)


@pytest.fixture
def sample_call_status_dto():
    """Пример статуса звонка в формате DTO"""
    return CallStatusDTO(
        id=1,
        user_id=123,
        order_number="ORDER123",
        call_date=date.today(),
        call_time=datetime.combine(date.today(), time(10, 0)),
        arrival_time=datetime.combine(date.today(), time(10, 15)),
        phone="+79111234567",
        customer_name="Иван Иванов",
        status="pending",
        attempts=0,
        is_manual_call=False,
        is_manual_arrival=False
    )


class TestCallsAPI:
    """Тесты для Calls API"""
    
    @patch('src.api.routes.calls.get_container')
    @patch('src.api.routes.calls.get_current_user')
    @patch('src.api.routes.calls.get_db')
    def test_get_call_schedule_success(
        self,
        mock_get_db,
        mock_get_current_user,
        mock_get_container,
        client,
        sample_call_status_dto
    ):
        """Тест успешного получения графика звонков"""
        from src.api.auth import User
        mock_get_current_user.return_value = User(user_id=123)
        
        # Мокаем контейнер и CallService
        mock_container = MagicMock()
        mock_call_service = MagicMock()
        mock_call_service.get_call_statuses_by_date.return_value = [sample_call_status_dto]
        mock_container.call_service.return_value = mock_call_service
        mock_get_container.return_value = mock_container
        
        mock_db = MagicMock()
        mock_get_db.return_value = mock_db
        
        response = client.get(
            "/api/calls",
            headers={"Authorization": "Bearer 123"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert len(data["calls"]) == 1
        assert data["calls"][0]["order_number"] == "ORDER123"
        assert data["calls"][0]["status"] == "pending"
    
    @patch('src.api.routes.calls.get_container')
    @patch('src.api.routes.calls.get_current_user')
    @patch('src.api.routes.calls.get_db')
    def test_get_call_schedule_empty(
        self,
        mock_get_db,
        mock_get_current_user,
        mock_get_container,
        client
    ):
        """Тест получения пустого графика звонков"""
        from src.api.auth import User
        mock_get_current_user.return_value = User(user_id=123)
        
        # Мокаем контейнер и CallService
        mock_container = MagicMock()
        mock_call_service = MagicMock()
        mock_call_service.get_call_statuses_by_date.return_value = []
        mock_container.call_service.return_value = mock_call_service
        mock_get_container.return_value = mock_container
        
        mock_db = MagicMock()
        mock_get_db.return_value = mock_db
        
        response = client.get(
            "/api/calls",
            headers={"Authorization": "Bearer 123"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 0
        assert len(data["calls"]) == 0
    
    @patch('src.api.routes.calls.get_container')
    @patch('src.api.routes.calls.get_current_user')
    @patch('src.api.routes.calls.get_db')
    def test_get_call_status_success(
        self,
        mock_get_db,
        mock_get_current_user,
        mock_get_container,
        client,
        sample_call_status_dto
    ):
        """Тест успешного получения статуса звонка по ID"""
        from src.api.auth import User
        mock_get_current_user.return_value = User(user_id=123)
        
        # Мокаем контейнер и CallService
        mock_container = MagicMock()
        mock_call_service = MagicMock()
        mock_call_service.get_call_status_by_id.return_value = sample_call_status_dto
        mock_container.call_service.return_value = mock_call_service
        mock_get_container.return_value = mock_container
        
        mock_db = MagicMock()
        mock_get_db.return_value = mock_db
        
        response = client.get(
            "/api/calls/1",
            headers={"Authorization": "Bearer 123"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == 1
        assert data["order_number"] == "ORDER123"
        assert data["status"] == "pending"
    
    @patch('src.api.routes.calls.get_container')
    @patch('src.api.routes.calls.get_current_user')
    @patch('src.api.routes.calls.get_db')
    def test_get_call_status_not_found(
        self,
        mock_get_db,
        mock_get_current_user,
        mock_get_container,
        client
    ):
        """Тест получения несуществующего статуса звонка"""
        from src.api.auth import User
        mock_get_current_user.return_value = User(user_id=123)
        
        # Мокаем контейнер и CallService
        mock_container = MagicMock()
        mock_call_service = MagicMock()
        mock_call_service.get_call_status_by_id.return_value = None
        mock_container.call_service.return_value = mock_call_service
        mock_get_container.return_value = mock_container
        
        mock_db = MagicMock()
        mock_get_db.return_value = mock_db
        
        response = client.get(
            "/api/calls/999",
            headers={"Authorization": "Bearer 123"}
        )
        
        assert response.status_code == 404
        assert "не найден" in response.json()["detail"].lower()
    
    @patch('src.api.routes.calls.get_container')
    @patch('src.api.routes.calls.get_current_user')
    @patch('src.api.routes.calls.get_db')
    def test_get_call_status_forbidden(
        self,
        mock_get_db,
        mock_get_current_user,
        mock_get_container,
        client,
        sample_call_status_dto
    ):
        """Тест получения статуса звонка другого пользователя"""
        from src.api.auth import User
        mock_get_current_user.return_value = User(user_id=123)
        
        # Создаем статус для другого пользователя
        other_user_call = sample_call_status_dto.model_copy(update={
            "user_id": 456  # Другой пользователь
        })
        
        # Мокаем контейнер и CallService
        mock_container = MagicMock()
        mock_call_service = MagicMock()
        mock_call_service.get_call_status_by_id.return_value = other_user_call
        mock_container.call_service.return_value = mock_call_service
        mock_get_container.return_value = mock_container
        
        mock_db = MagicMock()
        mock_get_db.return_value = mock_db
        
        response = client.get(
            "/api/calls/1",
            headers={"Authorization": "Bearer 123"}
        )
        
        assert response.status_code == 403
        assert "запрещен" in response.json()["detail"].lower()
    
    @patch('src.api.routes.calls.get_container')
    @patch('src.api.routes.calls.get_current_user')
    @patch('src.api.routes.calls.get_db')
    def test_confirm_call_success(
        self,
        mock_get_db,
        mock_get_current_user,
        mock_get_container,
        client,
        sample_call_status_dto
    ):
        """Тест успешного подтверждения звонка"""
        from src.api.auth import User
        mock_get_current_user.return_value = User(user_id=123)
        
        # Подтвержденный звонок
        confirmed_call = sample_call_status_dto.model_copy(update={
            "status": "confirmed",
            "confirmation_comment": "Подтверждено"
        })
        
        # Мокаем контейнер и CallService
        mock_container = MagicMock()
        mock_call_service = MagicMock()
        mock_call_service.confirm_call.return_value = True
        mock_call_service.get_call_status_by_id.return_value = confirmed_call
        mock_container.call_service.return_value = mock_call_service
        mock_get_container.return_value = mock_container
        
        mock_db = MagicMock()
        mock_get_db.return_value = mock_db
        
        request_data = {
            "comment": "Подтверждено"
        }
        
        response = client.post(
            "/api/calls/1/confirm",
            json=request_data,
            headers={"Authorization": "Bearer 123"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "confirmed"
        # Проверяем вызов с использованием ANY для session (реальный объект Session из FastAPI)
        mock_call_service.confirm_call.assert_called_once_with(
            user_id=123,
            call_status_id=1,
            comment="Подтверждено",
            session=ANY
        )
    
    @patch('src.api.routes.calls.get_container')
    @patch('src.api.routes.calls.get_current_user')
    @patch('src.api.routes.calls.get_db')
    def test_confirm_call_not_found(
        self,
        mock_get_db,
        mock_get_current_user,
        mock_get_container,
        client
    ):
        """Тест подтверждения несуществующего звонка"""
        from src.api.auth import User
        mock_get_current_user.return_value = User(user_id=123)
        
        # Мокаем контейнер и CallService
        mock_container = MagicMock()
        mock_call_service = MagicMock()
        mock_call_service.confirm_call.return_value = False
        mock_container.call_service.return_value = mock_call_service
        mock_get_container.return_value = mock_container
        
        mock_db = MagicMock()
        mock_get_db.return_value = mock_db
        
        request_data = {
            "comment": "Подтверждено"
        }
        
        response = client.post(
            "/api/calls/999/confirm",
            json=request_data,
            headers={"Authorization": "Bearer 123"}
        )
        
        assert response.status_code == 404
        assert "не найден" in response.json()["detail"].lower()
    
    @patch('src.api.routes.calls.get_container')
    @patch('src.api.routes.calls.get_current_user')
    @patch('src.api.routes.calls.get_db')
    def test_reject_call_success(
        self,
        mock_get_db,
        mock_get_current_user,
        mock_get_container,
        client,
        sample_call_status_dto
    ):
        """Тест успешного отклонения звонка"""
        from src.api.auth import User
        mock_get_current_user.return_value = User(user_id=123)
        
        # Отклоненный звонок
        rejected_call = sample_call_status_dto.model_copy(update={
            "status": "rejected",
            "attempts": 1
        })
        
        # Мокаем контейнер и CallService
        mock_container = MagicMock()
        mock_call_service = MagicMock()
        mock_call_service.reject_call.return_value = True
        mock_call_service.get_call_status_by_id.return_value = rejected_call
        mock_container.call_service.return_value = mock_call_service
        mock_get_container.return_value = mock_container
        
        mock_db = MagicMock()
        mock_get_db.return_value = mock_db
        
        request_data = {
            "reason": "Занят"
        }
        
        response = client.post(
            "/api/calls/1/reject",
            json=request_data,
            headers={"Authorization": "Bearer 123"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "rejected"
        assert data["attempts"] == 1
        # Проверяем вызов с использованием ANY для session (реальный объект Session из FastAPI)
        mock_call_service.reject_call.assert_called_once_with(
            user_id=123,
            call_status_id=1,
            session=ANY
        )
    
    @patch('src.api.routes.calls.get_container')
    @patch('src.api.routes.calls.get_current_user')
    @patch('src.api.routes.calls.get_db')
    def test_reject_call_not_found(
        self,
        mock_get_db,
        mock_get_current_user,
        mock_get_container,
        client
    ):
        """Тест отклонения несуществующего звонка"""
        from src.api.auth import User
        mock_get_current_user.return_value = User(user_id=123)
        
        # Мокаем контейнер и CallService
        mock_container = MagicMock()
        mock_call_service = MagicMock()
        mock_call_service.reject_call.return_value = False
        mock_container.call_service.return_value = mock_call_service
        mock_get_container.return_value = mock_container
        
        mock_db = MagicMock()
        mock_get_db.return_value = mock_db
        
        request_data = {
            "reason": "Занят"
        }
        
        response = client.post(
            "/api/calls/999/reject",
            json=request_data,
            headers={"Authorization": "Bearer 123"}
        )
        
        assert response.status_code == 404
        assert "не найден" in response.json()["detail"].lower()
    
    def test_get_call_schedule_unauthorized(self, client):
        """Тест получения графика звонков без авторизации"""
        response = client.get("/api/calls")
        
        assert response.status_code == 403

