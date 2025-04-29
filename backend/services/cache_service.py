from django.core.cache import cache
from django.core.cache import caches
from backend.constants import DEFAULT_CACHE_KEY_EXPIRY_SECONDS

class CacheService:

    CACHE_DB_CELERY_WORKFLOW_CACHE = "celery_workflow_cache"
    CACHE_DB_WORKFLOW_STATUS_CACHE = "workflow_status_cache"
    DEFAULT_KEY_EXPIRY_SECONDS = DEFAULT_CACHE_KEY_EXPIRY_SECONDS

    def __init__(self, cache_db=None):
        if cache_db:
            self.cache = caches[cache_db]
        else:
            self.cache = cache

    def get(self, key, default=None):
        """
        Retrieves a value from the cache.
        """
        return self.cache.get(key, default)

    def set(self, key, value, timeout=None):
        """
        Stores a key,value in the cache.
        """
        self.cache.set(key, value, timeout)

    def delete(self, key):
        """
        Deletes a key from the cache.
        """
        self.cache.delete(key)

    def clear(self):
        """
        Clears the entire cache. Use cautiously.
        """
        self.cache.clear()

    def hget(self, name, key):
        """
        Retrieves a value from a hash in the cache.
        """
        with self.cache.client.get_client() as client:
            return client.hget(name, key)

    def hset(self, name, key, value, expiry=None):
        """
        Sets a value in a hash in the cache.
        """
        with self.cache.client.get_client() as client:
            result = client.hset(name, key, value)
            if expiry is not None:
                client.expire(name, expiry)
            return result

    def hgetall(self, name):
        """
        Retrieves all fields and values of a hash.
        """
        with self.cache.client.get_client() as client:
            return client.hgetall(name)
        
    def hsetnx(self, name, key, value, expiry=None):
        """
        Sets a field in a hash only if it does not already exist.
        Equivalent to Redis HSETNX.
        """
        with self.cache.client.get_client() as client:
            result = client.hsetnx(name, key, value)
            if expiry is not None:
                client.expire(name, expiry)
            return result

    def keys(self, pattern):
        """
        Retrieve all keys matching a pattern.
        Equivalent to Redis KEYS command.
        """
        with self.cache.client.get_client() as client:
            return client.keys(pattern)
