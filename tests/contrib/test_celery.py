"""Tests for Celery health check."""

import datetime
import logging
from unittest import mock

import pytest

pytest.importorskip("celery")

from kombu import Queue

from health_check.contrib.celery import Ping as CeleryPingHealthCheck
from health_check.exceptions import ServiceUnavailable
from tests.testapp.celery import app as celery_app

logger = logging.getLogger(__name__)


class TestCelery:
    """Test Celery ping health check."""

    @pytest.mark.asyncio
    async def test_check_status__unexpected_response(self):
        """Raise ServiceUnavailable when worker response is incorrect."""
        mock_app = mock.MagicMock()
        mock_app.control.ping.return_value = [{"celery@worker1": {"bad": "response"}}]
        check = CeleryPingHealthCheck()
        check.app = mock_app

        result = await check.get_result()
        assert result.error is not None
        assert isinstance(result.error, ServiceUnavailable)
        assert "incorrect" in str(result.error).lower()

    @pytest.mark.asyncio
    async def test_check_status__oserror(self):
        """Raise ServiceUnavailable on OS error."""
        mock_app = mock.MagicMock()
        mock_app.control.ping.side_effect = OSError("os error")
        check = CeleryPingHealthCheck()
        check.app = mock_app

        result = await check.get_result()
        assert result.error is not None
        assert isinstance(result.error, ServiceUnavailable)

    @pytest.mark.asyncio
    async def test_check_status__not_implemented_error(self):
        """Raise ServiceUnavailable when result backend is not configured."""
        mock_app = mock.MagicMock()
        mock_app.control.ping.side_effect = NotImplementedError("no result backend")
        check = CeleryPingHealthCheck()
        check.app = mock_app

        result = await check.get_result()
        assert result.error is not None
        assert isinstance(result.error, ServiceUnavailable)
        assert "CELERY_RESULT_BACKEND" in str(result.error)

    @pytest.mark.asyncio
    async def test_check_status__unknown_error(self):
        """Raise ServiceUnavailable for unexpected exceptions."""
        with mock.patch("celery.app.default_app") as mock_app:
            mock_app.control.ping.side_effect = RuntimeError("unexpected")

            check = CeleryPingHealthCheck()
            result = await check.get_result()
            assert result.error is not None
            assert isinstance(result.error, ServiceUnavailable)

    @pytest.mark.asyncio
    async def test_check_status__success(self):
        """Report healthy when using real Celery app with configured queues."""
        default_queue = Queue("default", routing_key="default")
        celery_app.conf.task_queues = [default_queue]
        celery_app.conf.task_default_queue = "default"

        check = CeleryPingHealthCheck(app=celery_app)

        # Mock the control methods directly on the app before get_result runs
        mock_ping = mock.MagicMock(return_value=[{"celery@worker1": {"ok": "pong"}}])
        mock_inspect_obj = mock.MagicMock()
        mock_inspect_obj.active_queues.return_value = {
            "celery@worker1": [{"name": "default"}]
        }
        mock_inspect = mock.MagicMock(return_value=mock_inspect_obj)

        original_ping = check.app.control.ping
        original_inspect = check.app.control.inspect

        try:
            check.app.control.ping = mock_ping
            check.app.control.inspect = mock_inspect

            result = await check.get_result()
            assert result.error is None
        finally:
            check.app.control.ping = original_ping
            check.app.control.inspect = original_inspect

    @pytest.mark.asyncio
    async def test_check_status__no_workers(self):
        """Raise ServiceUnavailable when real app receives no worker response."""
        default_queue = Queue("default", routing_key="default")
        celery_app.conf.task_queues = [default_queue]
        celery_app.conf.task_default_queue = "default"

        check = CeleryPingHealthCheck(
            app=celery_app,
            timeout=datetime.timedelta(milliseconds=100),
        )
        result = await check.get_result()

        assert result.error is not None
        assert isinstance(result.error, ServiceUnavailable)
        assert "unavailable" in str(result.error).lower()

    @pytest.mark.asyncio
    async def test_check_status__missing_queue_worker(self):
        """Verify queue validation with real Celery app configuration."""
        multiple_queues = [
            Queue("default", routing_key="default"),
            Queue("integration_queue", routing_key="integration_queue"),
        ]
        celery_app.conf.task_queues = multiple_queues
        celery_app.conf.task_default_queue = "default"

        ping_response = [{"celery@worker1": {"ok": "pong"}}]
        inspect_response = {"celery@worker1": [{"name": "default"}]}

        check = CeleryPingHealthCheck(app=celery_app)
        check.app.control.ping = lambda **kwargs: ping_response
        check.app.control.inspect = lambda *args: mock.MagicMock(
            active_queues=lambda: inspect_response
        )

        result = await check.get_result()
        assert result.error is not None
        assert isinstance(result.error, ServiceUnavailable)
        assert "integration_queue" in str(result.error)

    @pytest.mark.asyncio
    async def test_check_status__raise_type_error__default_queue(self):
        """Verify that default queue is checked when task_queues is None."""
        mock_app = mock.MagicMock()
        mock_app.conf.task_queues = None
        mock_app.conf.task_default_queue = "default"
        mock_app.control.ping.return_value = [{"celery@worker1": {"ok": "pong"}}]
        mock_inspect = mock.MagicMock()
        mock_inspect.active_queues.return_value = {
            "celery@worker1": [{"name": "default"}]
        }
        mock_app.control.inspect.return_value = mock_inspect

        check = CeleryPingHealthCheck()
        check.app = mock_app

        result = await check.get_result()
        assert result.error is None
