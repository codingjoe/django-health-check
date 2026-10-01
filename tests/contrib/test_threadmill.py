"""Tests for threadmill health check."""

import asyncio
import datetime
import uuid

import pytest

pytest.importorskip("threadmill")
pytest.importorskip("redis")

import redis.asyncio
from django.tasks import task_backends
from django.tasks.backends.immediate import ImmediateBackend
from django.test import override_settings
from redis.exceptions import ConnectionError as RedisConnectionError
from redis.exceptions import TimeoutError as RedisTimeoutError
from threadmill.backends.base import (
    BackendTelemetry,
    QueueCounts,
    QueueRates,
    QueueStats,
    ThreadmillTaskBackend,
)
from threadmill.backends.redis import RedisTaskBackend

from health_check.contrib.threadmill import Threadmill as ThreadmillHealthCheck
from health_check.exceptions import ServiceUnavailable, ServiceWarning

BROKER_ERROR = "Unable to connect to threadmill task broker"


def build_telemetry(**queues):
    """Build backend telemetry from a mapping of queue names to queue counts."""
    return BackendTelemetry(
        queues={
            name: QueueStats(
                counts=QueueCounts(
                    ready=counts.get("ready", 0),
                    running=counts.get("running", 0),
                    deferred=counts.get("deferred", 0),
                    successful=counts.get("successful", 0),
                    failed=counts.get("failed", 0),
                ),
                rates=QueueRates(
                    interval=datetime.timedelta(seconds=60), ingress=0, egress=0
                ),
            )
            for name, counts in queues.items()
        }
    )


def build_backend_path(backend):
    """Return the dotted path of a task backend class for `TASKS` settings."""
    return f"{backend.__module__}.{backend.__qualname__}"


class StubTaskBackend(ThreadmillTaskBackend):
    """In-memory threadmill backend stub serving canned telemetry."""

    def enqueue(self, task, args=None, kwargs=None):
        """Reject work; the check under test never enqueues."""
        raise NotImplementedError

    async def queue_stats(self, *, interval=datetime.timedelta(seconds=60)):
        """Serve canned telemetry, raise a canned error, or hang forever."""
        if self.options.get("block"):
            await asyncio.Event().wait()
        if error := self.options.get("error"):
            raise error
        return self.options["telemetry"]


def stub_tasks(queues=("default",), **options):
    """Return a `TASKS` override serving stub telemetry on the default alias."""
    return override_settings(
        TASKS={
            "default": {
                "BACKEND": build_backend_path(StubTaskBackend),
                "QUEUES": list(queues),
                "OPTIONS": options,
            }
        }
    )


def redis_tasks(alias, redis_url):
    """Return a `TASKS` override for a Redis threadmill backend on the alias."""
    return override_settings(
        TASKS={
            alias: {
                "BACKEND": build_backend_path(RedisTaskBackend),
                "REDIS_URL": redis_url,
            }
        }
    )


def pending_task():
    """Task function used to put work on a queue."""


@pytest.fixture
def threadmill_tasks(redis_url):
    """Configure a `TASKS` alias backed by the Redis container."""
    alias = f"threadmill-{uuid.uuid4().hex}"
    with redis_tasks(alias, redis_url):
        yield alias


def enqueue_tasks(backend, count=1):
    """Enqueue tasks into the default queue of a real threadmill backend."""
    for _ in range(count):
        backend.enqueue(backend.task_class(func=pending_task, backend=backend.alias))


class TestThreadmill:
    """Test threadmill health check."""

    @pytest.mark.asyncio
    async def test_run__healthy(self):
        """Stay healthy below the backlog limit and with failures unlimited."""
        with stub_tasks(
            telemetry=build_telemetry(default={"ready": 2, "deferred": 1, "failed": 5})
        ):
            result = await ThreadmillHealthCheck().get_result()
        assert result.error is None

    @pytest.mark.asyncio
    async def test_run__pending_tasks_exceed_limit(self):
        """Fail when ready and deferred tasks exceed max_pending_tasks."""
        with stub_tasks(
            telemetry=build_telemetry(
                default={"ready": 7, "deferred": 4, "running": 100}
            )
        ):
            result = await ThreadmillHealthCheck(max_pending_tasks=10).get_result()
        assert isinstance(result.error, ServiceUnavailable)
        assert result.error.message == "11 pending tasks exceed max_pending_tasks of 10"

    @pytest.mark.asyncio
    async def test_run__pending_tasks_at_limit(self):
        """Stay healthy when the backlog is exactly at max_pending_tasks."""
        with stub_tasks(telemetry=build_telemetry(default={"ready": 6, "deferred": 4})):
            result = await ThreadmillHealthCheck(max_pending_tasks=10).get_result()
        assert result.error is None

    @pytest.mark.asyncio
    async def test_run__pending_tasks_limit_disabled(self):
        """Stay healthy with a backlog when max_pending_tasks is disabled."""
        with stub_tasks(telemetry=build_telemetry(default={"ready": 10_000})):
            result = await ThreadmillHealthCheck(max_pending_tasks=None).get_result()
        assert result.error is None

    @pytest.mark.asyncio
    async def test_run__failed_tasks_exceed_limit(self):
        """Warn when failed tasks exceed max_failed_tasks."""
        with stub_tasks(telemetry=build_telemetry(default={"failed": 3})):
            check = ThreadmillHealthCheck(max_pending_tasks=None, max_failed_tasks=2)
            result = await check.get_result()
        assert isinstance(result.error, ServiceWarning)
        assert result.error.message == "3 failed tasks exceed max_failed_tasks of 2"

    @pytest.mark.asyncio
    async def test_run__failed_tasks_at_limit(self):
        """Stay healthy when failed tasks are exactly at max_failed_tasks."""
        with stub_tasks(telemetry=build_telemetry(default={"failed": 2})):
            result = await ThreadmillHealthCheck(max_failed_tasks=2).get_result()
        assert result.error is None

    @pytest.mark.asyncio
    async def test_run__failed_tasks_limit_disabled(self):
        """Stay healthy with failing tasks when max_failed_tasks is disabled."""
        with stub_tasks(telemetry=build_telemetry(default={"failed": 10_000})):
            result = await ThreadmillHealthCheck(max_failed_tasks=None).get_result()
        assert result.error is None

    @pytest.mark.asyncio
    async def test_run__queue_selection_ignores_other_queues(self):
        """Judge the selected queue only, not the rest of the backend."""
        with stub_tasks(
            ("default", "emails"),
            telemetry=build_telemetry(default={"ready": 5_000}, emails={"ready": 1}),
        ):
            check = ThreadmillHealthCheck(queue_name="emails", max_pending_tasks=10)
            result = await check.get_result()
        assert result.error is None

    @pytest.mark.asyncio
    async def test_run__queue_selection_reports_selected_counts(self):
        """Report the counts of the selected queue only."""
        with stub_tasks(
            ("default", "emails"),
            telemetry=build_telemetry(default={"ready": 100}, emails={"ready": 4}),
        ):
            check = ThreadmillHealthCheck(queue_name="emails", max_pending_tasks=3)
            result = await check.get_result()
        assert isinstance(result.error, ServiceUnavailable)
        assert result.error.message == "4 pending tasks exceed max_pending_tasks of 3"

    @pytest.mark.asyncio
    async def test_run__unknown_queue(self):
        """Fail when the selected queue is not configured on the backend."""
        with stub_tasks():
            result = await ThreadmillHealthCheck(queue_name="emails").get_result()
        assert isinstance(result.error, ServiceUnavailable)
        assert result.error.message == "Task queue does not exist"

    @pytest.mark.asyncio
    async def test_run__unknown_backend_alias(self):
        """Fail when the configured backend alias does not exist."""
        with stub_tasks(telemetry=build_telemetry(default={"ready": 1})):
            result = await ThreadmillHealthCheck(alias="missing").get_result()
        assert isinstance(result.error, ServiceUnavailable)
        assert result.error.message == "Task backend alias does not exist"

    @pytest.mark.asyncio
    async def test_run__backend_without_queue_telemetry(self):
        """Fail when the backend does not support queue telemetry."""
        with override_settings(
            TASKS={"default": {"BACKEND": build_backend_path(ImmediateBackend)}}
        ):
            result = await ThreadmillHealthCheck().get_result()
        assert isinstance(result.error, ServiceUnavailable)
        assert result.error.message == "Task backend does not support queue telemetry"

    @pytest.mark.asyncio
    async def test_run__redis_error(self):
        """Fail when the broker raises a Redis error."""
        with stub_tasks(error=RedisConnectionError("refused")):
            result = await ThreadmillHealthCheck().get_result()
        assert isinstance(result.error, ServiceUnavailable)
        assert result.error.message == BROKER_ERROR

    @pytest.mark.asyncio
    async def test_run__redis_timeout_error(self):
        """Fail when the broker raises a Redis timeout, not an asyncio one."""
        with stub_tasks(error=RedisTimeoutError("timed out")):
            result = await ThreadmillHealthCheck().get_result()
        assert isinstance(result.error, ServiceUnavailable)
        assert result.error.message == BROKER_ERROR

    @pytest.mark.asyncio
    async def test_run__os_error(self):
        """Fail when the broker connection fails with an OS error."""
        with stub_tasks(error=OSError("unreachable")):
            result = await ThreadmillHealthCheck().get_result()
        assert isinstance(result.error, ServiceUnavailable)
        assert result.error.message == BROKER_ERROR

    @pytest.mark.asyncio
    async def test_run__telemetry_timeout(self):
        """Fail when queue telemetry does not arrive within the timeout."""
        with stub_tasks(block=True):
            check = ThreadmillHealthCheck(timeout=datetime.timedelta(milliseconds=10))
            result = await check.get_result()
        assert isinstance(result.error, ServiceUnavailable)
        assert result.error.message == "Threadmill queue telemetry timed out"

    @pytest.mark.asyncio
    async def test_run__releases_probe_client(self, monkeypatch):
        """Release the probe's own client once the telemetry probe is done."""
        closed = []

        async def record_close(client):
            closed.append(client)

        monkeypatch.setattr(redis.asyncio.Redis, "aclose", record_close)
        alias = f"threadmill-{uuid.uuid4().hex}"
        with redis_tasks(alias, "redis://127.0.0.1:1/0"):
            cached = task_backends[alias]
            result = await ThreadmillHealthCheck(alias=alias).get_result()
        assert isinstance(result.error, ServiceUnavailable)
        assert result.error.message == BROKER_ERROR
        assert closed and closed[0] is not cached.async_client

    def test_labels__alias_and_queue(self):
        """Label the backend alias and queue, but never the limits."""
        check = ThreadmillHealthCheck(
            alias="tasks",
            queue_name="emails",
            max_pending_tasks=10,
            max_failed_tasks=5,
        )
        assert check.labels == {
            "check": "Threadmill",
            "alias": "tasks",
            "queue_name": "emails",
        }


class TestThreadmillIntegration:
    """Test threadmill health check against a real Redis broker."""

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_run__backlog_exceeds_limit(self, threadmill_tasks):
        """Read telemetry of a real backend and fail on a growing backlog."""
        check = ThreadmillHealthCheck(alias=threadmill_tasks, max_pending_tasks=3)
        enqueue_tasks(task_backends[threadmill_tasks])
        result = await check.get_result()
        assert result.error is None

        enqueue_tasks(task_backends[threadmill_tasks], 3)
        result = await check.get_result()
        assert isinstance(result.error, ServiceUnavailable)
        assert result.error.message == "4 pending tasks exceed max_pending_tasks of 3"

    @pytest.mark.integration
    def test_run__reuse_across_event_loops(self, threadmill_tasks):
        """Serve consecutive probes, each from its own event loop."""
        check = ThreadmillHealthCheck(alias=threadmill_tasks)
        assert asyncio.run(check.get_result()).error is None
        assert asyncio.run(check.get_result()).error is None

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_run__unreachable_broker(self):
        """Fail when the configured Redis broker is unreachable."""
        alias = f"threadmill-{uuid.uuid4().hex}"
        with redis_tasks(alias, "redis://127.0.0.1:1/0"):
            result = await ThreadmillHealthCheck(alias=alias).get_result()
        assert isinstance(result.error, ServiceUnavailable)
        assert result.error.message == BROKER_ERROR
