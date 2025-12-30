"""
Redis Client Module
Handles connection to Redis for caching.
"""
from __future__ import annotations

import os
import json
from typing import Any, Optional
import redis
from dotenv import load_dotenv
import numpy as np

load_dotenv()


class NumpyEncoder(json.JSONEncoder):
    """Custom JSON encoder that handles numpy types."""
    def default(self, obj):
        if isinstance(obj, np.integer):
            return int(obj)
        elif isinstance(obj, np.floating):
            return float(obj)
        elif isinstance(obj, np.ndarray):
            return obj.tolist()
        elif isinstance(obj, np.bool_):
            return bool(obj)
        elif hasattr(obj, 'isoformat'):  # datetime-like objects
            return obj.isoformat()
        return super().default(obj)

class RedisClient:
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(RedisClient, cls).__new__(cls)
            cls._instance._init_redis()
        return cls._instance
    
    def _init_redis(self):
        """Initialize Redis connection."""
        self.host = os.getenv("REDIS_HOST", "localhost")
        self.port = int(os.getenv("REDIS_PORT", "6379"))
        self.password = os.getenv("REDIS_PASSWORD", "iniadalahpasswordredis")
        
        try:
            self.client = redis.Redis(
                host=self.host,
                port=self.port,
                password=self.password,
                decode_responses=True,
                socket_connect_timeout=2
            )
            # Test connection
            self.client.ping()
            print(f"OK: Connected to Redis at {self.host}:{self.port}")
            self.is_connected = True
        except (redis.ConnectionError, redis.TimeoutError, redis.RedisError) as e:
            print(f"FAIL: Redis connection failed (running without cache): {e}")
            self.is_connected = False
            self.client = None

    def set(self, key: str, value: Any, expire_seconds: int = 3600) -> bool:
        """Set a value in Redis."""
        if not self.is_connected:
            return False
        try:
            # Use NumpyEncoder to handle numpy types from pandas DataFrames
            val_str = json.dumps(value, cls=NumpyEncoder) if isinstance(value, (dict, list)) else str(value)
            self.client.setex(key, expire_seconds, val_str)
            return True
        except Exception as e:
            print(f"Redis Set Error: {e}")
            return False

    def get(self, key: str) -> Optional[Any]:
        """Get a value from Redis."""
        if not self.is_connected:
            return None
        try:
            val = self.client.get(key)
            if val is None:
                return None
            try:
                return json.loads(val)
            except json.JSONDecodeError:
                return val
        except Exception as e:
            print(f"Redis Get Error: {e}")
            return None

    def delete(self, key: str) -> bool:
        """Delete a key."""
        if not self.is_connected:
            return False
        try:
            self.client.delete(key)
            return True
        except Exception:
            return False
            
    def flush_prefix(self, prefix: str) -> int:
        """Delete all keys starting with prefix."""
        if not self.is_connected:
            return 0
        try:
            keys = self.client.keys(f"{prefix}*")
            if keys:
                return self.client.delete(*keys)
            return 0
        except Exception:
            return 0

# Global instance
redis_client = RedisClient()
