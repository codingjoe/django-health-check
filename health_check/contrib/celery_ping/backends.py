import dataclasses
import datetime

from celery.app import default_app as app
from django.conf import settings

from health_check.backends import HealthCheck
from health_check.exceptions import ServiceUnavailable


@dataclasses.dataclass
class CeleryPingHealthCheck(HealthCheck):
    """
    Check Celery worker availability using the ping control command.

    Args:
        timeout: Timeout duration for the ping command.

    """

    CORRECT_PING_RESPONSE = {"ok": "pong"}
    timeout: datetime.timedelta = dataclasses.field(
        default_factory=lambda: datetime.timedelta(seconds=getattr(settings, "HEALTHCHECK_CELERY_PING_TIMEOUT", 1))
    )

    def check_status(self):
        try:
            ping_result = app.control.ping(timeout=self.timeout.total_seconds())
        except OSError as e:
            self.add_error(ServiceUnavailable("IOError"), e)
        except NotImplementedError as exc:
            self.add_error(
                ServiceUnavailable("NotImplementedError: Make sure CELERY_RESULT_BACKEND is set"),
                exc,
            )
        except BaseException as exc:
            self.add_error(ServiceUnavailable("Unknown error"), exc)
        else:
            if not ping_result:
                self.add_error(
                    ServiceUnavailable("Celery workers unavailable"),
                )
            else:
                self._check_ping_result(ping_result)

    def _check_ping_result(self, ping_result):
        active_workers = []

        for result in ping_result:
            worker, response = list(result.items())[0]
            if response != self.CORRECT_PING_RESPONSE:
                self.add_error(
                    ServiceUnavailable(f"Celery worker {worker} response was incorrect"),
                )
                continue
            active_workers.append(worker)

        if not self.errors:
            self._check_active_queues(active_workers)

    def _check_active_queues(self, active_workers):
        defined_queues = getattr(app.conf, "task_queues", None) or getattr(app.conf, "CELERY_QUEUES", None)

        if not defined_queues:
            return

        defined_queues = {queue.name for queue in defined_queues}
        active_queues = set()

        for queues in app.control.inspect(active_workers).active_queues().values():
            active_queues.update([queue.get("name") for queue in queues])

        for queue in defined_queues.difference(active_queues):
            self.add_error(
                ServiceUnavailable(f"No worker for Celery task queue {queue}"),
            )
