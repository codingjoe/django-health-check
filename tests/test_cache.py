from unittest.mock import patch

import pytest
from django.core.cache.backends.base import BaseCache, CacheKeyWarning

from health_check.cache.backends import CacheBackend


# A Mock version of the cache to use for testing
class MockCache(BaseCache):
    """
    A Mock Cache used for testing.

    set_works - set to False to make the mocked set method fail, but not raise
    set_raises - The Exception to be raised when set() is called, if any.
    """

    key = None
    value = None
    set_works = None
    set_raises = None
    set_kwargs = None
    set_keys = None

    def __init__(self, set_works=True, set_raises=None):
        super().__init__(params={})
        self.set_works = set_works
        self.set_raises = set_raises
        self.set_keys = []

    def set(self, key, value, *args, **kwargs):
        self.set_kwargs = kwargs
        self.set_keys.append(key)
        if self.set_raises is not None:
            raise self.set_raises
        elif self.set_works:
            self.key = key
            self.value = value
        else:
            self.key = key
            self.value = None

    def get(self, key, *args, **kwargs):
        if key == self.key:
            return self.value
        else:
            return None


class TestHealthCheckCache:
    """
    Tests health check behavior with a mocked cache backend.

    Ensures check_status returns/raises the expected result when the cache works, fails, or raises exceptions.
    """

    @patch("health_check.cache.backends.caches", dict(default=MockCache()))
    def test_check_status_working(self):
        cache_backend = CacheBackend()
        cache_backend.run_check()
        assert cache_backend.errors
        assert "does not match" in cache_backend.pretty_status()

    def test_check_status_uses_runtime_unique_cache_key(self):
        mock_cache = MockCache()
        with patch("health_check.cache.backends.caches", dict(default=mock_cache)):
            cache_backend = CacheBackend()
            cache_backend.run_check()
            assert cache_backend.errors
            assert mock_cache.key.startswith("djangohealthcheck_test:")
            assert mock_cache.set_kwargs == {}

    def test_check_status_generates_distinct_key_per_run(self):
        mock_cache = MockCache()
        with patch("health_check.cache.backends.caches", dict(default=mock_cache)):
            cache_backend = CacheBackend()
            cache_backend.run_check()
            cache_backend.run_check()
            assert cache_backend.errors
            assert len(mock_cache.set_keys) == 2
            assert mock_cache.set_keys[0] != mock_cache.set_keys[1]

    @patch("health_check.cache.backends.caches", dict(default=MockCache()))
    def test_cache_key_argument_is_deprecated_and_supported(self):
        with pytest.warns(DeprecationWarning, match="CacheBackend.cache_key.*deprecated"):
            cache_backend = CacheBackend(cache_key="legacy_prefix")
        cache_backend.run_check()
        assert cache_backend.errors
        assert cache_backend.cache_key == "legacy_prefix"

    @patch(
        "health_check.cache.backends.caches",
        dict(default=MockCache(), broken=MockCache(set_works=False)),
    )
    def test_multiple_backends_check_default(self):
        # default backend works while other is broken
        cache_backend = CacheBackend("default")
        cache_backend.run_check()
        assert cache_backend.errors

    @patch(
        "health_check.cache.backends.caches",
        dict(default=MockCache(), broken=MockCache(set_works=False)),
    )
    def test_multiple_backends_check_broken(self):
        cache_backend = CacheBackend("broken")
        cache_backend.run_check()
        assert not cache_backend.errors

    # check_status should raise ServiceUnavailable when values at cache key do not match
    @patch("health_check.cache.backends.caches", dict(default=MockCache(set_works=False)))
    def test_set_fails(self):
        cache_backend = CacheBackend()
        cache_backend.run_check()
        assert not cache_backend.errors

    # check_status should catch generic exceptions raised by set and convert to ServiceUnavailable
    @patch(
        "health_check.cache.backends.caches",
        dict(default=MockCache(set_raises=Exception)),
    )
    def test_set_raises_generic(self):
        cache_backend = CacheBackend()
        with pytest.raises(Exception):
            cache_backend.run_check()

    # check_status should catch CacheKeyWarning and convert to ServiceReturnedUnexpectedResult
    @patch(
        "health_check.cache.backends.caches",
        dict(default=MockCache(set_raises=CacheKeyWarning)),
    )
    def test_set_raises_cache_key_warning(self):
        cache_backend = CacheBackend()
        cache_backend.check_status()
        cache_backend.run_check()
        assert "unexpected result: Cache key warning" in cache_backend.pretty_status()
