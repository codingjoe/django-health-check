"""Tests for Celery health check."""

from unittest import mock

import pytest

pytest.importorskip("celery")

from health_check.contrib.celery import Ping as CeleryPingHealthCheck
from health_check.exceptions import ServiceUnavailable


class TestCelery:
    """Test Celery ping health check."""

    def test_check_status__success(self):
        """Report healthy when workers respond correctly."""
        mock_result = {"celery@worker1": {"ok": "pong"}}

        with mock.patch("health_check.contrib.celery.app") as mock_app:
            mock_app.control.ping.return_value = [mock_result]

            check = CeleryPingHealthCheck()
            check.check_status()
            assert check.errors == [], "Should have no errors with correct response"

    def test_check_status__no_workers(self):
        """Add error when no workers respond."""
        with mock.patch("health_check.contrib.celery.app") as mock_app:
            mock_app.control.ping.return_value = {}

            check = CeleryPingHealthCheck()
            check.check_status()
            assert len(check.errors) == 1, "Should have one error"
            assert "unavailable" in str(check.errors[0]).lower(), (
                "Should indicate unavailability"
            )

    def test_check_status__unexpected_response(self):
        """Add error when worker response is incorrect."""
        mock_result = {"celery@worker1": {"bad": "response"}}

        with mock.patch("health_check.contrib.celery.app") as mock_app:
            mock_app.control.ping.return_value = [mock_result]

            check = CeleryPingHealthCheck()
            check.check_status()
            assert len(check.errors) == 1, "Should have one error"
            assert "incorrect" in str(check.errors[0]).lower(), (
                "Should indicate incorrect response"
            )

    def test_check_status__oserror(self):
        """Add error on OS error."""
        with mock.patch("health_check.contrib.celery.app") as mock_app:
            mock_app.control.ping.side_effect = OSError("os error")

            check = CeleryPingHealthCheck()
            check.check_status()
            assert len(check.errors) == 1, "Should have one error"
            assert isinstance(check.errors[0], ServiceUnavailable), (
                "Should be ServiceUnavailable"
            )

    def test_check_status__not_implemented_error(self):
        """Add error when result backend is not configured."""
        with mock.patch("health_check.contrib.celery.app") as mock_app:
            mock_app.control.ping.side_effect = NotImplementedError("no result backend")

            check = CeleryPingHealthCheck()
            check.check_status()
            assert len(check.errors) == 1, "Should have one error"
            assert isinstance(check.errors[0], ServiceUnavailable), (
                "Should indicate unavailability"
            )

    def test_check_status__unknown_error(self):
        """Add error for unexpected exceptions."""
        with mock.patch("health_check.contrib.celery.app") as mock_app:
            mock_app.control.ping.side_effect = RuntimeError("unexpected")

            check = CeleryPingHealthCheck()
            check.check_status()
            assert len(check.errors) == 1, "Should have one error"
            assert isinstance(check.errors[0], ServiceUnavailable), (
                "Should be ServiceUnavailable"
            )
