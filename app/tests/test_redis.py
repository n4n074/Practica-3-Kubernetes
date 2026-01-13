from unittest.mock import patch, MagicMock
import sys
import os
import json

# Añadir el directorio padre al path para importar app
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app import (
    get_redis,
    get_users_from_cache,
    save_users_to_cache,
    invalidate_users_cache,
    USERS_CACHE_KEY,
    CACHE_TTL,
)


class TestRedisConnection:
    """Tests para la conexión a Redis"""

    @patch("app.redis.Redis")
    def test_get_redis_success(self, mock_redis):
        """Test: Conexión exitosa a Redis"""
        mock_client = MagicMock()
        mock_redis.return_value = mock_client

        client = get_redis()

        assert client is not None
        mock_redis.assert_called_once()


class TestCacheOperations:
    """Tests para operaciones de caché"""

    @patch("app.get_redis")
    def test_get_users_from_cache_hit(self, mock_get_redis):
        """Test: Obtener usuarios desde caché (cache hit)"""
        # Mock Redis con datos en caché
        mock_redis = MagicMock()
        users_data = [
            {"id": 1, "name": "Juan", "email": "juan@example.com"},
            {"id": 2, "name": "María", "email": "maria@example.com"},
        ]
        mock_redis.get.return_value = json.dumps(users_data)
        mock_get_redis.return_value = mock_redis

        result, from_cache = get_users_from_cache()

        assert result == users_data
        assert from_cache is True
        mock_redis.get.assert_called_once_with(USERS_CACHE_KEY)

    @patch("app.get_redis")
    def test_get_users_from_cache_miss(self, mock_get_redis):
        """Test: Caché vacío (cache miss)"""
        # Mock Redis sin datos
        mock_redis = MagicMock()
        mock_redis.get.return_value = None
        mock_get_redis.return_value = mock_redis

        result, from_cache = get_users_from_cache()

        assert result is None
        assert from_cache is False

    @patch("app.get_redis")
    def test_get_users_from_cache_error(self, mock_get_redis):
        """Test: Error al obtener desde caché"""
        # Mock Redis con error
        mock_redis = MagicMock()
        mock_redis.get.side_effect = Exception("Redis error")
        mock_get_redis.return_value = mock_redis

        result, from_cache = get_users_from_cache()

        assert result is None
        assert from_cache is False

    @patch("app.get_redis")
    def test_save_users_to_cache_success(self, mock_get_redis):
        """Test: Guardar usuarios en caché exitosamente"""
        # Mock Redis
        mock_redis = MagicMock()
        mock_get_redis.return_value = mock_redis

        users_data = [{"id": 1, "name": "Juan", "email": "juan@example.com"}]

        save_users_to_cache(users_data)

        mock_redis.setex.assert_called_once_with(
            USERS_CACHE_KEY, CACHE_TTL, json.dumps(users_data)
        )

    @patch("app.get_redis")
    def test_save_users_to_cache_error(self, mock_get_redis):
        """Test: Error al guardar en caché (no debe lanzar excepción)"""
        # Mock Redis con error
        mock_redis = MagicMock()
        mock_redis.setex.side_effect = Exception("Redis error")
        mock_get_redis.return_value = mock_redis

        users_data = [{"id": 1, "name": "Juan"}]

        # No debe lanzar excepción
        save_users_to_cache(users_data)

    @patch("app.get_redis")
    def test_invalidate_users_cache_success(self, mock_get_redis):
        """Test: Invalidar caché exitosamente"""
        # Mock Redis
        mock_redis = MagicMock()
        mock_get_redis.return_value = mock_redis

        invalidate_users_cache()

        mock_redis.delete.assert_called_once_with(USERS_CACHE_KEY)

    @patch("app.get_redis")
    def test_invalidate_users_cache_error(self, mock_get_redis):
        """Test: Error al invalidar caché (no debe lanzar excepción)"""
        # Mock Redis con error
        mock_redis = MagicMock()
        mock_redis.delete.side_effect = Exception("Redis error")
        mock_get_redis.return_value = mock_redis

        # No debe lanzar excepción
        invalidate_users_cache()


class TestCacheIntegration:
    """Tests de integración para el flujo completo de caché"""

    @patch("app.get_redis")
    def test_cache_workflow(self, mock_get_redis):
        """Test: Flujo completo - guardar, obtener e invalidar"""
        # Mock Redis
        mock_redis = MagicMock()
        users_data = [{"id": 1, "name": "Test User", "email": "test@example.com"}]

        # Simular comportamiento de Redis
        cache_storage = {}

        def mock_setex(key, ttl, value):
            cache_storage[key] = value

        def mock_get(key):
            return cache_storage.get(key)

        def mock_delete(key):
            if key in cache_storage:
                del cache_storage[key]

        mock_redis.setex.side_effect = mock_setex
        mock_redis.get.side_effect = mock_get
        mock_redis.delete.side_effect = mock_delete
        mock_get_redis.return_value = mock_redis

        # 1. Guardar en caché
        save_users_to_cache(users_data)
        assert USERS_CACHE_KEY in cache_storage

        # 2. Obtener desde caché
        result, from_cache = get_users_from_cache()
        assert result == users_data
        assert from_cache is True

        # 3. Invalidar caché
        invalidate_users_cache()
        assert USERS_CACHE_KEY not in cache_storage

        # 4. Verificar que caché está vacío
        result, from_cache = get_users_from_cache()
        assert result is None
        assert from_cache is False

    @patch("app.get_redis")
    def test_cache_ttl_is_set(self, mock_get_redis):
        """Test: Verificar que se establece el TTL correcto"""
        mock_redis = MagicMock()
        mock_get_redis.return_value = mock_redis

        users_data = [{"id": 1, "name": "Test"}]
        save_users_to_cache(users_data)

        # Verificar que se llamó setex con el TTL correcto
        call_args = mock_redis.setex.call_args
        assert call_args[0][0] == USERS_CACHE_KEY
        assert call_args[0][1] == CACHE_TTL
        assert call_args[0][2] == json.dumps(users_data)
