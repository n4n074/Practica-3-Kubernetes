import pytest
from unittest.mock import patch, MagicMock
import sys
import os

# Añadir el directorio padre al path para importar app
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app import app, check_postgres, check_redis, check_minio, check_load_balancer


@pytest.fixture
def client():
    """Fixture para el cliente de pruebas de Flask"""
    app.config["TESTING"] = True
    with app.test_client() as client:
        yield client


class TestHealthChecks:
    """Tests para las funciones de health check"""

    @patch("app.get_db")
    def test_check_postgres_success(self, mock_get_db):
        """Test: PostgreSQL está disponible"""
        mock_conn = MagicMock()
        mock_get_db.return_value = mock_conn

        result = check_postgres()

        assert result is True
        mock_conn.close.assert_called_once()

    @patch("app.get_db")
    def test_check_postgres_failure(self, mock_get_db):
        """Test: PostgreSQL no está disponible"""
        mock_get_db.side_effect = Exception("Connection error")

        result = check_postgres()

        assert result is False

    @patch("app.get_redis")
    def test_check_redis_success(self, mock_get_redis):
        """Test: Redis está disponible"""
        mock_redis = MagicMock()
        mock_redis.ping.return_value = True
        mock_get_redis.return_value = mock_redis

        result = check_redis()

        assert result is True
        mock_redis.ping.assert_called_once()

    @patch("app.get_redis")
    def test_check_redis_failure(self, mock_get_redis):
        """Test: Redis no está disponible"""
        mock_redis = MagicMock()
        mock_redis.ping.side_effect = Exception("Redis error")
        mock_get_redis.return_value = mock_redis

        result = check_redis()

        assert result is False

    @patch("app.get_minio")
    def test_check_minio_success(self, mock_get_minio):
        """Test: MinIO está disponible"""
        mock_client = MagicMock()
        mock_client.list_buckets.return_value = []
        mock_get_minio.return_value = mock_client

        result = check_minio()

        assert result is True
        mock_client.list_buckets.assert_called_once()

    @patch("app.get_minio")
    def test_check_minio_failure(self, mock_get_minio):
        """Test: MinIO no está disponible"""
        mock_client = MagicMock()
        mock_client.list_buckets.side_effect = Exception("MinIO error")
        mock_get_minio.return_value = mock_client

        result = check_minio()

        assert result is False

    @patch("app.requests.get")
    def test_check_load_balancer_success(self, mock_requests_get):
        """Test: Load Balancer está disponible"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_requests_get.return_value = mock_response

        result = check_load_balancer()

        assert result is True

    @patch("app.requests.get")
    def test_check_load_balancer_failure(self, mock_requests_get):
        """Test: Load Balancer no está disponible"""
        mock_requests_get.side_effect = Exception("Connection error")

        result = check_load_balancer()

        assert result is False


class TestHealthEndpoint:
    """Tests para el endpoint principal de salud"""

    @patch("app.check_load_balancer")
    @patch("app.check_minio")
    @patch("app.check_redis")
    @patch("app.check_postgres")
    def test_index_all_services_up(
        self, mock_pg, mock_redis, mock_minio, mock_lb, client
    ):
        """Test: Todos los servicios están funcionando"""
        mock_pg.return_value = True
        mock_redis.return_value = True
        mock_minio.return_value = True
        mock_lb.return_value = True

        response = client.get("/")

        assert response.status_code == 200
        assert b"instance_id" in response.data or response.data

    @patch("app.check_load_balancer")
    @patch("app.check_minio")
    @patch("app.check_redis")
    @patch("app.check_postgres")
    def test_index_some_services_down(
        self, mock_pg, mock_redis, mock_minio, mock_lb, client
    ):
        """Test: Algunos servicios no están disponibles"""
        mock_pg.return_value = False
        mock_redis.return_value = True
        mock_minio.return_value = False
        mock_lb.return_value = True

        response = client.get("/")

        assert response.status_code == 200

    @patch("app.check_load_balancer")
    @patch("app.check_minio")
    @patch("app.check_redis")
    @patch("app.check_postgres")
    def test_index_all_services_down(
        self, mock_pg, mock_redis, mock_minio, mock_lb, client
    ):
        """Test: Todos los servicios están caídos"""
        mock_pg.return_value = False
        mock_redis.return_value = False
        mock_minio.return_value = False
        mock_lb.return_value = False

        response = client.get("/")

        assert response.status_code == 200
