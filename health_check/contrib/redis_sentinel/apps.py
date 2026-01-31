from django.apps import AppConfig

from health_check.plugins import plugin_dir


class HealthCheckConfig(AppConfig):
    name = "health_check.contrib.redis_sentinel"

    def ready(self):
        from .backends import RedisSentinelHealthCheck

        plugin_dir.register(RedisSentinelHealthCheck)
