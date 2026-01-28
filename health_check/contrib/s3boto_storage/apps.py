import warnings

from django.apps import AppConfig

from health_check.plugins import plugin_dir


class HealthCheckConfig(AppConfig):
    name = "health_check.contrib.s3boto_storage"

    def ready(self):
        from .backends import StorageHealthCheck

        warnings.warn(
            "The `health_check.contrib.s3boto_storage` app is deprecated: checks are now configured via `HealthCheckView`. Action: remove this sub-app from `INSTALLED_APPS` and add the corresponding storage check to `HealthCheckView.checks`. See migration guide: https://codingjoe.dev/django-health-check/migrate-to-v4/ (docs/migrate-to-v4.md).",
            DeprecationWarning,
        )

        plugin_dir.register(StorageHealthCheck)
