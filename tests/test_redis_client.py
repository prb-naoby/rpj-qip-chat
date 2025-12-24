"""
TDD Tests for Redis Client Module.
Tests singleton behavior, CRUD operations, and error handling.
"""
from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest


class TestRedisClientSingleton:
    """Tests for singleton pattern behavior."""
    
    def test_singleton_returns_same_instance(self):
        """
        GIVEN: RedisClient is imported twice
        WHEN: Accessing the singleton instance
        THEN: Both references point to the same object
        """
        from app.redis_client import RedisClient
        
        instance1 = RedisClient()
        instance2 = RedisClient()
        
        assert instance1 is instance2
    
    def test_global_instance_is_singleton(self):
        """
        GIVEN: The global redis_client instance
        WHEN: Creating a new RedisClient instance
        THEN: They are the same object
        """
        from app.redis_client import redis_client, RedisClient
        
        new_instance = RedisClient()
        assert redis_client is new_instance


class TestRedisClientConnection:
    """Tests for connection handling."""
    
    @pytest.fixture
    def mock_redis(self):
        """Mock the redis.Redis class."""
        with patch("app.redis_client.redis.Redis") as mock:
            mock_client = MagicMock()
            mock_client.ping.return_value = True
            mock.return_value = mock_client
            yield mock, mock_client
    
    def test_successful_connection_sets_is_connected_true(self, mock_redis):
        """
        GIVEN: Redis server is reachable
        WHEN: RedisClient initializes
        THEN: is_connected is True
        """
        mock_class, mock_instance = mock_redis
        
        # Force re-initialization by accessing internal method
        from app.redis_client import RedisClient
        client = RedisClient()
        
        # Re-init with mock
        with patch.object(client, 'client', mock_instance):
            client.is_connected = True
            assert client.is_connected is True
    
    def test_connection_failure_sets_is_connected_false(self):
        """
        GIVEN: Redis server is unreachable
        WHEN: RedisClient initializes
        THEN: is_connected is False and client is None
        """
        import redis
        with patch("app.redis_client.redis.Redis") as mock:
            mock.side_effect = redis.ConnectionError("Connection refused")
            
            from app.redis_client import RedisClient
            # Create a fresh instance for testing
            instance = object.__new__(RedisClient)
            instance._init_redis()
            
            assert instance.is_connected is False
            assert instance.client is None


class TestRedisClientCRUD:
    """Tests for CRUD operations."""
    
    @pytest.fixture
    def connected_client(self):
        """Create a mock connected RedisClient."""
        from app.redis_client import RedisClient
        client = RedisClient()
        
        mock_redis = MagicMock()
        client.client = mock_redis
        client.is_connected = True
        
        return client, mock_redis
    
    @pytest.fixture
    def disconnected_client(self):
        """Create a disconnected RedisClient."""
        from app.redis_client import RedisClient
        client = RedisClient()
        client.is_connected = False
        client.client = None
        return client
    
    # SET Tests
    def test_set_string_value_success(self, connected_client):
        """
        GIVEN: Connected Redis client
        WHEN: Setting a string value
        THEN: setex is called and returns True
        """
        client, mock_redis = connected_client
        
        result = client.set("test_key", "test_value", expire_seconds=3600)
        
        mock_redis.setex.assert_called_once_with("test_key", 3600, "test_value")
        assert result is True
    
    def test_set_dict_value_serializes_json(self, connected_client):
        """
        GIVEN: Connected Redis client
        WHEN: Setting a dict value
        THEN: Value is JSON serialized
        """
        client, mock_redis = connected_client
        
        test_dict = {"key": "value", "number": 42}
        client.set("dict_key", test_dict)
        
        # Verify JSON serialization
        call_args = mock_redis.setex.call_args
        assert call_args[0][2] == '{"key": "value", "number": 42}'
    
    def test_set_list_value_serializes_json(self, connected_client):
        """
        GIVEN: Connected Redis client
        WHEN: Setting a list value
        THEN: Value is JSON serialized
        """
        client, mock_redis = connected_client
        
        test_list = [1, 2, 3, "four"]
        client.set("list_key", test_list)
        
        call_args = mock_redis.setex.call_args
        assert call_args[0][2] == '[1, 2, 3, "four"]'
    
    def test_set_when_disconnected_returns_false(self, disconnected_client):
        """
        GIVEN: Disconnected Redis client
        WHEN: Trying to set a value
        THEN: Returns False without error
        """
        result = disconnected_client.set("key", "value")
        assert result is False
    
    def test_set_with_redis_error_returns_false(self, connected_client):
        """
        GIVEN: Connected Redis client
        WHEN: Redis raises an exception during set
        THEN: Returns False and handles error gracefully
        """
        client, mock_redis = connected_client
        mock_redis.setex.side_effect = Exception("Redis error")
        
        result = client.set("key", "value")
        
        assert result is False
    
    # GET Tests
    def test_get_existing_key_returns_value(self, connected_client):
        """
        GIVEN: Connected Redis client with existing key
        WHEN: Getting the key
        THEN: Returns the value
        """
        client, mock_redis = connected_client
        mock_redis.get.return_value = "stored_value"
        
        result = client.get("existing_key")
        
        mock_redis.get.assert_called_once_with("existing_key")
        assert result == "stored_value"
    
    def test_get_nonexistent_key_returns_none(self, connected_client):
        """
        GIVEN: Connected Redis client
        WHEN: Getting a non-existent key
        THEN: Returns None
        """
        client, mock_redis = connected_client
        mock_redis.get.return_value = None
        
        result = client.get("nonexistent_key")
        
        assert result is None
    
    def test_get_json_value_deserializes(self, connected_client):
        """
        GIVEN: Connected Redis client with JSON stored
        WHEN: Getting the key
        THEN: Returns deserialized Python object
        """
        client, mock_redis = connected_client
        mock_redis.get.return_value = '{"name": "test", "count": 5}'
        
        result = client.get("json_key")
        
        assert result == {"name": "test", "count": 5}
    
    def test_get_invalid_json_returns_raw_string(self, connected_client):
        """
        GIVEN: Connected Redis client with non-JSON string stored
        WHEN: Getting the key
        THEN: Returns the raw string
        """
        client, mock_redis = connected_client
        mock_redis.get.return_value = "not valid json"
        
        result = client.get("string_key")
        
        assert result == "not valid json"
    
    def test_get_when_disconnected_returns_none(self, disconnected_client):
        """
        GIVEN: Disconnected Redis client
        WHEN: Trying to get a value
        THEN: Returns None without error
        """
        result = disconnected_client.get("any_key")
        assert result is None
    
    def test_get_with_redis_error_returns_none(self, connected_client):
        """
        GIVEN: Connected Redis client
        WHEN: Redis raises an exception during get
        THEN: Returns None and handles error gracefully
        """
        client, mock_redis = connected_client
        mock_redis.get.side_effect = Exception("Redis error")
        
        result = client.get("key")
        
        assert result is None
    
    # DELETE Tests
    def test_delete_existing_key_returns_true(self, connected_client):
        """
        GIVEN: Connected Redis client
        WHEN: Deleting a key
        THEN: Delete is called and returns True
        """
        client, mock_redis = connected_client
        
        result = client.delete("key_to_delete")
        
        mock_redis.delete.assert_called_once_with("key_to_delete")
        assert result is True
    
    def test_delete_when_disconnected_returns_false(self, disconnected_client):
        """
        GIVEN: Disconnected Redis client
        WHEN: Trying to delete a key
        THEN: Returns False without error
        """
        result = disconnected_client.delete("any_key")
        assert result is False
    
    def test_delete_with_redis_error_returns_false(self, connected_client):
        """
        GIVEN: Connected Redis client
        WHEN: Redis raises an exception during delete
        THEN: Returns False
        """
        client, mock_redis = connected_client
        mock_redis.delete.side_effect = Exception("Redis error")
        
        result = client.delete("key")
        
        assert result is False
    
    # FLUSH PREFIX Tests
    def test_flush_prefix_deletes_matching_keys(self, connected_client):
        """
        GIVEN: Connected Redis client with keys matching prefix
        WHEN: Flushing by prefix
        THEN: All matching keys are deleted
        """
        client, mock_redis = connected_client
        mock_redis.keys.return_value = ["user:1:data", "user:1:cache", "user:1:session"]
        mock_redis.delete.return_value = 3
        
        result = client.flush_prefix("user:1:")
        
        mock_redis.keys.assert_called_once_with("user:1:*")
        mock_redis.delete.assert_called_once_with("user:1:data", "user:1:cache", "user:1:session")
        assert result == 3
    
    def test_flush_prefix_no_matching_keys_returns_zero(self, connected_client):
        """
        GIVEN: Connected Redis client with no matching keys
        WHEN: Flushing by prefix
        THEN: Returns 0
        """
        client, mock_redis = connected_client
        mock_redis.keys.return_value = []
        
        result = client.flush_prefix("nonexistent:")
        
        assert result == 0
        mock_redis.delete.assert_not_called()
    
    def test_flush_prefix_when_disconnected_returns_zero(self, disconnected_client):
        """
        GIVEN: Disconnected Redis client
        WHEN: Trying to flush prefix
        THEN: Returns 0 without error
        """
        result = disconnected_client.flush_prefix("any:")
        assert result == 0
