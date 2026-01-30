import dataclasses
import datetime

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
class Cache(HealthCheck):
    """
    Check that the cache backend is able to set and get a value.

    Args:
        alias: The cache alias to test against.

    """

    alias: str = dataclasses.field(default="default")
    cache_key: str = dataclasses.field(default="djangohealthcheck_test", repr=False)

    def __post_init__(self):
        # Override cache_key from settings if not explicitly provided
        if self.cache_key == "djangohealthcheck_test" and hasattr(settings, "HEALTHCHECK_CACHE_KEY"):
            object.__setattr__(self, "cache_key", settings.HEALTHCHECK_CACHE_KEY)

    def check_status(self):
        cache = caches[self.alias]
        ts = datetime.datetime.now().timestamp()
        try:
            cache.set(self.cache_key, f"itworks-{ts}")
            if not cache.get(self.cache_key) == f"itworks-{ts}":
                raise ServiceUnavailable(f"Cache key {self.cache_key} does not match")
        except CacheKeyWarning as e:
            self.add_error(ServiceReturnedUnexpectedResult("Cache key warning"), e)
        except ValueError as e:
            self.add_error(ServiceReturnedUnexpectedResult("ValueError"), e)
        except (ConnectionError, RedisError) as e:
            self.add_error(ServiceReturnedUnexpectedResult("Connection Error"), e)
