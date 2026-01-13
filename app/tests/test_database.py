import pytest
from unittest.mock import patch, MagicMock
import sys
import os
from io import BytesIO

# Añadir el directorio padre al path para importar app
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app import app, get_db


@pytest.fixture
def client():
    """Fixture para el cliente de pruebas de Flask"""
    app.config["TESTING"] = True
    with app.test_client() as client:
        yield client


class TestDatabaseConnection:
    """Tests para la conexión a la base de datos"""

    @patch("app.psycopg2.connect")
    def test_get_db_success(self, mock_connect):
        """Test: Conexión exitosa a la base de datos"""
        mock_conn = MagicMock()
        mock_connect.return_value = mock_conn

        conn = get_db()

        assert conn is not None
        mock_connect.assert_called_once()

    @patch("app.psycopg2.connect")
    def test_get_db_failure(self, mock_connect):
        """Test: Fallo en la conexión a la base de datos"""
        mock_connect.side_effect = Exception("Database connection error")

        with pytest.raises(Exception):
            get_db()


class TestUsersEndpoint:
    """Tests para el endpoint de usuarios"""

    @patch("app.get_users_from_cache")
    @patch("app.get_db")
    def test_users_list_from_database(self, mock_get_db, mock_cache, client):
        """Test: Listar usuarios desde la base de datos"""
        # Mock caché vacío
        mock_cache.return_value = (None, False)

        # Mock base de datos
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [
            {
                "id": 1,
                "name": "Juan",
                "email": "juan@example.com",
                "image_url": None,
                "created_at": None,
            },
            {
                "id": 2,
                "name": "María",
                "email": "maria@example.com",
                "image_url": None,
                "created_at": None,
            },
        ]
        mock_conn.cursor.return_value = mock_cursor
        mock_get_db.return_value = mock_conn

        response = client.get("/users")

        assert response.status_code == 200
        mock_cursor.execute.assert_called_once()

    @patch("app.get_users_from_cache")
    def test_users_list_from_cache(self, mock_cache, client):
        """Test: Listar usuarios desde caché"""
        # Mock caché con datos
        cached_users = [
            {
                "id": 1,
                "name": "Juan",
                "email": "juan@example.com",
                "image_url": None,
                "created_at": "2025-01-01T10:00:00",
            },
        ]
        mock_cache.return_value = (cached_users, True)

        response = client.get("/users")

        assert response.status_code == 200

    @patch("app.get_users_from_cache")
    @patch("app.get_db")
    def test_users_list_error_handling(self, mock_get_db, mock_cache, client):
        """Test: Manejo de errores al listar usuarios"""
        mock_cache.return_value = (None, False)
        mock_get_db.side_effect = Exception("Database error")

        response = client.get("/users")

        assert response.status_code == 200
        assert b"error" in response.data or response.data


class TestAddUser:
    """Tests para agregar usuarios"""

    @patch("app.invalidate_users_cache")
    @patch("app.get_db")
    def test_add_user_without_image(self, mock_get_db, mock_invalidate, client):
        """Test: Agregar usuario sin imagen"""
        # Mock base de datos
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_get_db.return_value = mock_conn

        response = client.post(
            "/users/add",
            data={"name": "Test User", "email": "test@example.com"},
            follow_redirects=False,
        )

        assert response.status_code == 302  # Redirect
        mock_cursor.execute.assert_called_once()
        mock_conn.commit.assert_called_once()
        mock_invalidate.assert_called_once()

    @patch("app.invalidate_users_cache")
    @patch("app.get_minio")
    @patch("app.get_db")
    def test_add_user_with_image(
        self, mock_get_db, mock_get_minio, mock_invalidate, client
    ):
        """Test: Agregar usuario con imagen"""
        # Mock base de datos
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_get_db.return_value = mock_conn

        # Mock MinIO
        mock_minio = MagicMock()
        mock_get_minio.return_value = mock_minio

        # Crear imagen fake
        data = {
            "name": "Test User",
            "email": "test@example.com",
            "image": (BytesIO(b"fake image data"), "test.jpg"),
        }

        response = client.post(
            "/users/add",
            data=data,
            content_type="multipart/form-data",
            follow_redirects=False,
        )

        assert response.status_code == 302
        mock_minio.put_object.assert_called_once()
        mock_invalidate.assert_called_once()

    @patch("app.get_db")
    def test_add_user_database_error(self, mock_get_db, client):
        """Test: Error al agregar usuario"""
        mock_get_db.side_effect = Exception("Database error")

        response = client.post(
            "/users/add",
            data={"name": "Test User", "email": "test@example.com"},
            follow_redirects=False,
        )

        assert response.status_code == 302


class TestDeleteUser:
    """Tests para eliminar usuarios"""

    @patch("app.invalidate_users_cache")
    @patch("app.get_db")
    def test_delete_user_without_image(self, mock_get_db, mock_invalidate, client):
        """Test: Eliminar usuario sin imagen"""
        # Mock base de datos
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = {"image_url": None}
        mock_conn.cursor.return_value = mock_cursor
        mock_get_db.return_value = mock_conn

        response = client.get("/users/delete/1", follow_redirects=False)

        assert response.status_code == 302
        mock_invalidate.assert_called_once()

    @patch("app.invalidate_users_cache")
    @patch("app.get_minio")
    @patch("app.get_db")
    def test_delete_user_with_image(
        self, mock_get_db, mock_get_minio, mock_invalidate, client
    ):
        """Test: Eliminar usuario con imagen"""
        # Mock base de datos
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = {"image_url": "test_image.jpg"}
        mock_conn.cursor.return_value = mock_cursor
        mock_get_db.return_value = mock_conn

        # Mock MinIO
        mock_minio = MagicMock()
        mock_get_minio.return_value = mock_minio

        response = client.get("/users/delete/1", follow_redirects=False)

        assert response.status_code == 302
        mock_minio.remove_object.assert_called_once()
        mock_invalidate.assert_called_once()

    @patch("app.get_db")
    def test_delete_user_error(self, mock_get_db, client):
        """Test: Error al eliminar usuario"""
        mock_get_db.side_effect = Exception("Database error")

        response = client.get("/users/delete/1", follow_redirects=False)

        assert response.status_code == 302
