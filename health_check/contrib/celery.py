"""Celery health check."""

import dataclasses
import datetime
import typing

import celery
from celery.app import app_or_default

from health_check.base import HealthCheck
from health_check.exceptions import ServiceUnavailable


@dataclasses.dataclass
class Ping(HealthCheck):
    """
    Check Celery worker availability using the ping control command.

    Args:
        app: Celery application instance to use for the health check, defaults to the [default Celery app][celery.app.default_app].
        custom_task_queue_names: Set of Celery queue names to be checked if set, defaults to [{}].
        timeout: Timeout duration for the ping command.
        limit: Maximum number of workers to wait for before returning. If not
            specified, waits for the full timeout duration. When set, returns
            immediately after receiving responses from this many workers.

    """

    CORRECT_PING_RESPONSE: typing.ClassVar[dict[str, str]] = {"ok": "pong"}
    app: celery.Celery = dataclasses.field(default_factory=app_or_default)
    custom_task_queue_names: set[str] | None = dataclasses.field(default=None, repr=False)
    timeout: datetime.timedelta = dataclasses.field(
        default=datetime.timedelta(seconds=1), repr=False
    )
    limit: int | None = dataclasses.field(default=None, repr=False)

    def run(self):
        try:
            ping_result = self.app.control.ping(
                timeout=self.timeout.total_seconds(), limit=self.limit
            )
        except OSError as e:
            raise ServiceUnavailable("IOError") from e
        except NotImplementedError as e:
            raise ServiceUnavailable(
                "NotImplementedError: Make sure CELERY_RESULT_BACKEND is set"
            ) from e
        else:
            if not ping_result:
                raise ServiceUnavailable("Celery workers unavailable")
            else:
                self.check_active_queues(*self.active_workers(ping_result))

    def active_workers(self, ping_result):
        for result in ping_result:
            worker, response = list(result.items())[0]
            if response != self.CORRECT_PING_RESPONSE:
                raise ServiceUnavailable(
                    f"Celery worker {worker} response was incorrect"
                )
            yield worker

    def check_active_queues(self, *active_workers):
        if self.custom_task_queue_names:
            defined_queues = self.custom_task_queue_names
        else:
            try:
                defined_queues = {queue.name for queue in self.app.conf.task_queues}
            except TypeError:
                # conf.task_queues may be None
                defined_queues = {self.app.conf.task_default_queue}

        active_queues = {
            queue.get("name")
            for queues in self.app.control.inspect(active_workers)
            .active_queues()
            .values()
            for queue in queues
        }

        for queue in defined_queues - active_queues:
            raise ServiceUnavailable(f"No worker for Celery task queue {queue}")
