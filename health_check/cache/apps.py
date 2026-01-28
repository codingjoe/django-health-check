from django.apps import AppConfig
from django.conf import settings

from health_check.plugins import plugin_dir


class HealthCheckConfig(AppConfig):
    name = "health_check.cache"

    def ready(self):
        from .backends import CacheBackend

        for backend in settings.CACHES:
            plugin_dir.register(CacheBackend, alias=backend)
