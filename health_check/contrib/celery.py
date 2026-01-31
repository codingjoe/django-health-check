"""Celery health check."""

import dataclasses
import datetime

from celery.app import default_app as app

from health_check.base import HealthCheck
from health_check.exceptions import ServiceUnavailable


@dataclasses.dataclass
class Ping(HealthCheck):
    """
    Check Celery worker availability using the ping control command.

    Args:
        timeout: Timeout duration for the ping command.
        limit: Maximum number of workers to wait for before returning. If not
            specified, waits for the full timeout duration. When set, returns
            immediately after receiving responses from this many workers.

    """

    CORRECT_PING_RESPONSE = {"ok": "pong"}
    timeout: datetime.timedelta = dataclasses.field(
        default=datetime.timedelta(seconds=1), repr=False
    )
    limit: int | None = dataclasses.field(default=None, repr=False)

    def check_status(self):
        try:
            ping_kwargs = {"timeout": self.timeout.total_seconds()}
            if self.limit is not None:
                ping_kwargs["limit"] = self.limit
            ping_result = app.control.ping(**ping_kwargs)
        except OSError as e:
            raise ServiceUnavailable("IOError") from e
        except NotImplementedError as e:
            raise ServiceUnavailable(
                "NotImplementedError: Make sure CELERY_RESULT_BACKEND is set"
            ) from e
        except BaseException as e:
            raise ServiceUnavailable("Unknown error") from e
        else:
            if not ping_result:
                raise ServiceUnavailable("Celery workers unavailable")
            else:
                self._check_ping_result(ping_result)

    def _check_ping_result(self, ping_result):
        active_workers = []

        for result in ping_result:
            worker, response = list(result.items())[0]
            if response != self.CORRECT_PING_RESPONSE:
                raise ServiceUnavailable(
                    f"Celery worker {worker} response was incorrect"
                )
            active_workers.append(worker)

        if not self.errors:
            self._check_active_queues(active_workers)

    def _check_active_queues(self, active_workers):
        defined_queues = getattr(app.conf, "task_queues", None) or getattr(
            app.conf, "CELERY_QUEUES", None
        )

        defined_queues = {queue.name for queue in defined_queues}
        active_queues = set()

        for queues in app.control.inspect(active_workers).active_queues().values():
            active_queues.update([queue.get("name") for queue in queues])

        for queue in defined_queues.difference(active_queues):
            raise ServiceUnavailable(f"No worker for Celery task queue {queue}")
