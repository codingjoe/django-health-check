from django.core.cache.backends.base import CacheKeyWarning
from health_check.backends.base import BaseHealthCheckBackend, ServiceUnavailable, ServiceReturnedUnexpectedResult
from health_check.plugins import plugin_dir
from django.core.cache import cache


class CacheBackend(BaseHealthCheckBackend):

    def check_status(self):
        try:
            cache.set('djangohealtcheck_test', 'itworks', 1)
            if not cache.get("djangohealtcheck_test") == "itworks":
                raise ServiceUnavailable("Cache key does not match")
        except CacheKeyWarning as e:
            raise ServiceReturnedUnexpectedResult("Cache key warning") from e
        except ValueError as e:
            raise ServiceReturnedUnexpectedResult("ValueError") from e

plugin_dir.register(CacheBackend)