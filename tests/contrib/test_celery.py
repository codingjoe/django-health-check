"""Tests for Celery health check."""

from unittest import mock

import pytest

pytest.importorskip("celery")

from health_check.contrib.celery import Ping as CeleryPingHealthCheck
from health_check.exceptions import ServiceUnavailable


class TestCelery:
    """Test Celery ping health check."""

    @pytest.mark.asyncio
    async def test_check_status__success(self):
        """Report healthy when workers respond correctly."""
        mock_result = {"celery@worker1": {"ok": "pong"}}

        with mock.patch("health_check.contrib.celery.default_app") as mock_app:
            mock_app.control.ping.return_value = [mock_result]

            check = CeleryPingHealthCheck()
            result = await check.result
            assert result.error is None

    @pytest.mark.asyncio
    async def test_check_status__no_workers(self):
        """Raise ServiceUnavailable when no workers respond."""
        with mock.patch("health_check.contrib.celery.default_app") as mock_app:
            mock_app.control.ping.return_value = {}

            check = CeleryPingHealthCheck()
            result = await check.result
            assert result.error is not None
            assert isinstance(result.error, ServiceUnavailable)
            assert "unavailable" in str(result.error).lower()

    @pytest.mark.asyncio
    async def test_check_status__unexpected_response(self):
        """Raise ServiceUnavailable when worker response is incorrect."""
        mock_result = {"celery@worker1": {"bad": "response"}}

        with mock.patch("health_check.contrib.celery.default_app") as mock_app:
            mock_app.control.ping.return_value = [mock_result]

            check = CeleryPingHealthCheck()
            result = await check.result
            assert result.error is not None
            assert isinstance(result.error, ServiceUnavailable)
            assert "incorrect" in str(result.error).lower()

    @pytest.mark.asyncio
    async def test_check_status__oserror(self):
        """Raise ServiceUnavailable on OS error."""
        with mock.patch("health_check.contrib.celery.default_app") as mock_app:
            mock_app.control.ping.side_effect = OSError("os error")

            check = CeleryPingHealthCheck()
            result = await check.result
            assert result.error is not None
            assert isinstance(result.error, ServiceUnavailable)

    @pytest.mark.asyncio
    async def test_check_status__not_implemented_error(self):
        """Raise ServiceUnavailable when result backend is not configured."""
        with mock.patch("health_check.contrib.celery.default_app") as mock_app:
            mock_app.control.ping.side_effect = NotImplementedError("no result backend")

            check = CeleryPingHealthCheck()
            result = await check.result
            assert result.error is not None
            assert isinstance(result.error, ServiceUnavailable)

    @pytest.mark.asyncio
    async def test_check_status__unknown_error(self):
        """Raise ServiceUnavailable for unexpected exceptions."""
        with mock.patch("health_check.contrib.celery.default_app") as mock_app:
            mock_app.control.ping.side_effect = RuntimeError("unexpected")

            check = CeleryPingHealthCheck()
            result = await check.result
            assert result.error is not None
            assert isinstance(result.error, ServiceUnavailable)

    @pytest.mark.asyncio
    async def test_check_status__missing_queue_worker(self):
        """Raise ServiceUnavailable when a defined queue has no active workers."""
        mock_result = {"celery@worker1": {"ok": "pong"}}

        with mock.patch("health_check.contrib.celery.default_app") as mock_app:
            mock_app.control.ping.return_value = [mock_result]
            mock_queue = mock.MagicMock()
            mock_queue.name = "missing_queue"
            mock_app.conf.task_queues = [mock_queue]
            mock_inspect = mock.MagicMock()
            mock_inspect.active_queues.return_value = {
                "celery@worker1": [{"name": "celery"}]
            }
            mock_app.control.inspect.return_value = mock_inspect

            check = CeleryPingHealthCheck()
            result = await check.result
            assert result.error is not None
            assert isinstance(result.error, ServiceUnavailable)
            assert "missing_queue" in str(result.error)
