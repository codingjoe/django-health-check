"""Threadmill health check."""

import asyncio
import dataclasses
import datetime

from django.tasks import task_backends
from django.tasks.exceptions import InvalidTaskBackend
from redis.exceptions import RedisError
from threadmill.backends.base import ThreadmillTaskBackend
from threadmill.backends.redis import RedisTaskBackend

from health_check.base import HealthCheck
from health_check.exceptions import ServiceUnavailable, ServiceWarning


@dataclasses.dataclass
class Threadmill(HealthCheck):
    """
    Check the queue telemetry of a threadmill task backend.

    Reports broker reachability along with queue backlog and failed task counts,
    so a stalled task pipeline becomes visible to the health endpoint. The probe
    only reads queue telemetry and never writes to a queue, so a stopped worker
    shows up as a backlog against `max_pending_tasks`, never as missing liveness.

    Args:
        alias: Alias of the `TASKS` backend to inspect.
        queue_name: Queue to inspect, or `None` to inspect every queue of the backend.
        max_pending_tasks: Maximum number of ready and deferred tasks before the check fails, or `None` to disable the limit.
        max_failed_tasks: Maximum number of failed tasks before the check warns, or `None` to disable the limit.
        timeout: Maximum duration of the telemetry request as a `datetime.timedelta`.

    """

    alias: str = "default"
    queue_name: str | None = None
    max_pending_tasks: int | None = dataclasses.field(default=1000, repr=False)
    max_failed_tasks: int | None = dataclasses.field(default=None, repr=False)
    timeout: datetime.timedelta = dataclasses.field(
        default=datetime.timedelta(seconds=5), repr=False
    )

    async def run(self) -> None:
        try:
            backend = task_backends[self.alias]
        except InvalidTaskBackend as e:
            raise ServiceUnavailable("Task backend alias does not exist") from e
        if not isinstance(backend, ThreadmillTaskBackend):
            raise ServiceUnavailable("Task backend does not support queue telemetry")
        if self.queue_name is not None and self.queue_name not in backend.queues:
            raise ServiceUnavailable("Task queue does not exist")
        # The handler caches a backend whose async client is bound to the event loop
        # that created it; probe a fresh instance and release it afterwards.
        probe = task_backends.create_connection(self.alias)
        try:
            telemetry = await asyncio.wait_for(
                probe.queue_stats(), timeout=self.timeout.total_seconds()
            )
        except TimeoutError as e:
            raise ServiceUnavailable(
                "Timed out fetching threadmill queue telemetry"
            ) from e
        except (RedisError, OSError) as e:
            raise ServiceUnavailable(
                "Unable to connect to threadmill task broker"
            ) from e
        finally:
            # RedisTaskBackend owns the only shipped client; use a backend
            # lifecycle hook once threadmill exposes one for other backends.
            if isinstance(probe, RedisTaskBackend):
                await probe.async_client.aclose()
        queue_counts = [
            stats.counts
            for name, stats in telemetry.queues.items()
            if self.queue_name is None or name == self.queue_name
        ]
        pending = sum(counts.ready + counts.deferred for counts in queue_counts)
        failed = sum(counts.failed for counts in queue_counts)
        if self.max_pending_tasks is not None and pending > self.max_pending_tasks:
            raise ServiceUnavailable(
                f"{pending} pending tasks exceed max_pending_tasks of {self.max_pending_tasks}"
            )
        if self.max_failed_tasks is not None and failed > self.max_failed_tasks:
            raise ServiceWarning(
                f"{failed} failed tasks exceed max_failed_tasks of {self.max_failed_tasks}"
            )
