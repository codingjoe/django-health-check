import warnings

from celery import current_app
from django.apps import AppConfig
from django.conf import settings

from health_check.plugins import plugin_dir


class HealthCheckConfig(AppConfig):
    name = "health_check.contrib.celery"

    def ready(self):
        from .backends import CeleryHealthCheck

        warnings.warn(
            "The `health_check.contrib.celery` app is deprecated: checks are now configured via `HealthCheckView`. Action: remove this sub-app from `INSTALLED_APPS` and add the Celery check(s) to your `HealthCheckView.checks`. See migration guide: https://codingjoe.dev/django-health-check/migrate-to-v4/ (docs/migrate-to-v4.md).",
            DeprecationWarning,
        )

        if hasattr(settings, "HEALTHCHECK_CELERY_TIMEOUT"):
            warnings.warn(
                "`HEALTHCHECK_CELERY_TIMEOUT` setting is deprecated: it was split into separate timeouts. Action: replace it with `HEALTHCHECK_CELERY_RESULT_TIMEOUT` and `HEALTHCHECK_CELERY_QUEUE_TIMEOUT`. See migration guide: https://codingjoe.dev/django-health-check/migrate-to-v4/ (docs/migrate-to-v4.md).",
                DeprecationWarning,
            )

        for queue in current_app.amqp.queues:
            celery_class_name = "CeleryHealthCheck" + queue.title()

            celery_class = type(celery_class_name, (CeleryHealthCheck,), {"queue": queue})
            plugin_dir.register(celery_class)
