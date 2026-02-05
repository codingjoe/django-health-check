"""Tests for health_check management command."""

from io import StringIO
from urllib.parse import urlparse

import pytest
from django.core.management import call_command


class TestHealthCheckCommand:
    """Test health_check management command."""

    def test_handle__success(self, live_server):
        """Return exit code 0 when all checks pass."""
        parsed = urlparse(live_server.url)
        addrport = f"{parsed.hostname}:{parsed.port}"

        stdout = StringIO()
        stderr = StringIO()
        call_command(
            "health_check",
            "health_check_test",
            addrport,
            stdout=stdout,
            stderr=stderr,
        )
        output = stdout.getvalue()
        # Check that output contains health check results
        assert "Database" in output or "Cache" in output
        assert "OK" in output or "working" in output

    def test_handle__http_error(self, live_server):
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
                stdout=stdout,
                stderr=stderr,
            )
        assert exc_info.value.code == 1
        output = stdout.getvalue()
        # Should display the error message from the failing check
        assert "Test failure" in output or "AlwaysFailingCheck" in output

    def test_handle__url_error__connection_refused(self):
        """Return exit code 2 when URL cannot be reached (connection refused)."""
        stdout = StringIO()
        stderr = StringIO()
        with pytest.raises(SystemExit) as exc_info:
            call_command(
                "health_check",
                "health_check_test",
                "localhost:9999",
                stdout=stdout,
                stderr=stderr,
            )
        assert exc_info.value.code == 2
        error_output = stderr.getvalue()
        assert "not reachable" in error_output

    def test_handle__forwarded_host(self, live_server):
        """Set X-Forwarded-Host header when --forwarded-host is provided."""
        parsed = urlparse(live_server.url)
        addrport = f"{parsed.hostname}:{parsed.port}"

        stdout = StringIO()
        stderr = StringIO()
        call_command(
            "health_check",
            "health_check_test",
            addrport,
            forwarded_host="example.com",
            stdout=stdout,
            stderr=stderr,
        )
        output = stdout.getvalue()
        assert "OK" in output or "working" in output

    def test_handle__forwarded_proto(self, live_server):
        """Set X-Forwarded-Proto header when --forwarded-proto is provided."""
        parsed = urlparse(live_server.url)
        addrport = f"{parsed.hostname}:{parsed.port}"

        stdout = StringIO()
        stderr = StringIO()
        call_command(
            "health_check",
            "health_check_test",
            addrport,
            forwarded_proto="https",
            stdout=stdout,
            stderr=stderr,
        )
        output = stdout.getvalue()
        assert "OK" in output or "working" in output
