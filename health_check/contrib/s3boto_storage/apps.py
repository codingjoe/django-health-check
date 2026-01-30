import warnings

from django.apps import AppConfig

from health_check.plugins import plugin_dir


class HealthCheckConfig(AppConfig):
    name = "health_check.contrib.s3boto_storage"

    def ready(self):
        from .backends import S3BotoStorageHealthCheck

        warnings.warn(
            "The app is deprecated and will be removed in the next major release."
            " Use the new view based health checks instead: https://codingjoe.dev/django-health-check/",
            DeprecationWarning,
        )

        plugin_dir.register(S3BotoStorageHealthCheck)
