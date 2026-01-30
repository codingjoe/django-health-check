import warnings

from django.apps import AppConfig

from health_check.plugins import plugin_dir


class HealthCheckConfig(AppConfig):
    name = "health_check.contrib.redis"

    def ready(self):
        from .backends import RedisHealthCheck as Redis

        warnings.warn(
            "The `health_check.contrib.redis` app is deprecated: checks are now configured via `HealthCheckView`. Action: remove this sub-app from `INSTALLED_APPS` and add `health_check.contrib.redis.Redis` to your `HealthCheckView.checks`. See migration guide: https://codingjoe.dev/django-health-check/migrate-to-v4/ (docs/migrate-to-v4.md).",
            DeprecationWarning,
        )

        plugin_dir.register(Redis)
