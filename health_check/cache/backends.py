import dataclasses
import uuid
import warnings

from django.conf import settings
from django.core.cache import CacheKeyWarning, caches

from health_check.backends import HealthCheck
from health_check.exceptions import ServiceReturnedUnexpectedResult, ServiceUnavailable

try:
    # Exceptions thrown by Redis do not subclass builtin exceptions like ConnectionError.
    # Additionally, not only connection errors (ConnectionError -> RedisError) can be raised,
    # but also errors for time-outs (TimeoutError -> RedisError)
    # and if the backend is read-only (ReadOnlyError -> ResponseError -> RedisError).
    # Since we know what we are trying to do here, we are not picky and catch the global exception RedisError.
    from redis.exceptions import RedisError
except ModuleNotFoundError:
    # In case Redis is not installed and another cache backend is used.
    class RedisError(Exception):
        pass


@dataclasses.dataclass
class CacheBackend(HealthCheck):
    """
    Check that the cache backend is able to set and get a value.

    Args:
        alias: The cache alias to test against.

    """

    alias: str = dataclasses.field(default="default")
    key_prefix: str = dataclasses.field(default="djangohealthcheck_test", repr=False)
    cache_key: str | None = dataclasses.field(
        default=getattr(settings, "HEALTHCHECK_CACHE_KEY", "djangohealthcheck_test"), repr=False
    )

    def __post_init__(self):
        if self.cache_key:
            warnings.warn(
                "`CacheBackend.cache_key` is deprecated and will be removed in next major release. "
                "Use `CacheBackend.key_prefix` instead.",
                DeprecationWarning,
                stacklevel=2,
            )

    def check_status(self):
        self.cache_key = f"{self.key_prefix}:{uuid.uuid4().hex}"
        cache = caches[self.alias]
        try:
            cache.set(
                self.cache_key,
                "itworks",
            )
            if cache.get(self.cache_key):
                raise ServiceUnavailable(f"Cache key {self.cache_key!r} does not match")
        except CacheKeyWarning as e:
            self.add_error(ServiceReturnedUnexpectedResult("Cache key warning"), e)
        except ValueError as e:
            self.add_error(ServiceReturnedUnexpectedResult("ValueError"), e)
        except (ConnectionError, RedisError) as e:
            self.add_error(ServiceReturnedUnexpectedResult("Connection Error"), e)
