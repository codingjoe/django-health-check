from celery.exceptions import TaskRevokedError, TimeoutError
from django.conf import settings

from health_check.backends import HealthCheck
from health_check.deprecation import deprecated
from health_check.exceptions import ServiceReturnedUnexpectedResult, ServiceUnavailable

from .tasks import add


@deprecated(
    "`CeleryHealthCheck` is deprecated: use `health_check.contrib.celery.Ping` (or the new view-based Celery ping check) instead. Action: remove legacy CeleryHealthCheck subclasses and configure `HealthCheckView` with the new Celery ping check in your `checks` list. See migration guide: https://codingjoe.dev/django-health-check/migrate-to-v4/ (docs/migrate-to-v4.md)."
)
class CeleryHealthCheck(HealthCheck):
    def check_status(self):
        timeout = getattr(settings, "HEALTHCHECK_CELERY_TIMEOUT", 3)
        result_timeout = getattr(settings, "HEALTHCHECK_CELERY_RESULT_TIMEOUT", timeout)
        queue_timeout = getattr(settings, "HEALTHCHECK_CELERY_QUEUE_TIMEOUT", timeout)
        priority = getattr(settings, "HEALTHCHECK_CELERY_PRIORITY", None)

        try:
            result = add.apply_async(args=[4, 4], expires=queue_timeout, queue=self.queue, priority=priority)
            result.get(timeout=result_timeout)
            if result.result != 8:
                self.add_error(ServiceReturnedUnexpectedResult("Celery returned wrong result"))
        except OSError as e:
            self.add_error(ServiceUnavailable("IOError"), e)
        except NotImplementedError as e:
            self.add_error(
                ServiceUnavailable("NotImplementedError: Make sure CELERY_RESULT_BACKEND is set"),
                e,
            )
        except TaskRevokedError as e:
            self.add_error(
                ServiceUnavailable(
                    "TaskRevokedError: The task was revoked, likely because it spent too long in the queue"
                ),
                e,
            )
        except TimeoutError as e:
            self.add_error(
                ServiceUnavailable("TimeoutError: The task took too long to return a result"),
                e,
            )
        except BaseException as e:
            self.add_error(ServiceUnavailable("Unknown error"), e)
