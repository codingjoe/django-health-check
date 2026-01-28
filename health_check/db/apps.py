import warnings

from django.apps import AppConfig

from health_check.plugins import plugin_dir


class HealthCheckConfig(AppConfig):
    default_auto_field = "django.db.models.AutoField"
    name = "health_check.db"

    def ready(self):
        from .backends import DatabaseBackend

        warnings.warn(
            "The `health_check.db` app is deprecated: it is superseded by view-based checks. Action: remove `health_check.db` from `INSTALLED_APPS` and use `HealthCheckView` with an explicit `checks` list. See migration guide: https://codingjoe.dev/django-health-check/migrate-to-v4/ (docs/migrate-to-v4.md).",
            DeprecationWarning,
        )

        plugin_dir.register(DatabaseBackend)
