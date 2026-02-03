"""Tests for health_check management command."""

from io import StringIO
from urllib.parse import urlparse

import pytest
import pytest_django.live_server_helper
from django.core.management import call_command


class TestHealthCheckCommand:
    """Test health_check management command."""

    @pytest.mark.django_db
    def test_handle__success(self):
        """Return exit code 0 when all checks pass."""
        stdout = StringIO()
        stderr = StringIO()
        call_command(
            "health_check",
            "health_check_test",
            stdout=stdout,
            stderr=stderr,
        )
        output = stdout.getvalue()
        # Check that output contains health check results
        assert "Database" in output and "Cache" in output
        assert "OK" in output or "working" in output

    def test_handle__error(self):
        """Return exit code 1 when checks fail."""
        stdout = StringIO()
        stderr = StringIO()
        with pytest.raises(SystemExit) as exc_info:
            call_command(
                "health_check",
                "health_check_fail",
                stdout=stdout,
                stderr=stderr,
            )
        assert exc_info.value.code == 1
        output = stdout.getvalue()
        # Should display the error message from the failing check
        assert "Test failure" in output and "AlwaysFailingCheck" in output

    def test_handle__endpoint__success(
        self,
        live_server: pytest_django.live_server_helper.LiveServer,
    ):
        """Return exit code 0 when all checks pass when making http call."""
        parsed = urlparse(live_server.url)
        addrport = f"{parsed.hostname}:{parsed.port}"

        stdout = StringIO()
        stderr = StringIO()
        call_command(
            "health_check",
            "health_check_test",
            addrport,
            "--make-http-request-directly",
            stdout=stdout,
            stderr=stderr,
        )
        output = stdout.getvalue()
        # Check that output contains health check results
        assert "Database" in output and "Cache" in output
        assert "OK" in output or "working" in output

    def test_handle__endpoint__http_error(
        self,
        live_server: pytest_django.live_server_helper.LiveServer,
    ):
        """Return exit code 1 when checks fail with HTTP 500."""
        parsed = urlparse(live_server.url)
        addrport = f"{parsed.hostname}:{parsed.port}"

        stdout = StringIO()
        stderr = StringIO()
        with pytest.raises(SystemExit) as exc_info:
            call_command(
                "health_check",
                "health_check_fail",
                addrport,
                "--make-http-request-directly",
                stdout=stdout,
                stderr=stderr,
            )
        assert exc_info.value.code == 1
        output = stdout.getvalue()
        # Should display the error message from the failing check
        assert "Test failure" in output or "AlwaysFailingCheck" in output

    def test_handle__endpoint__url_error__connection_refused(self):
        """Return exit code 2 when URL cannot be reached (connection refused)."""
        stdout = StringIO()
        stderr = StringIO()
        with pytest.raises(SystemExit) as exc_info:
            call_command(
                "health_check",
                "health_check_test",
                "localhost:9999",
                "--make-http-request-directly",
                stdout=stdout,
                stderr=stderr,
            )
        assert exc_info.value.code == 2
        error_output = stderr.getvalue()
        assert "not reachable" in error_output
