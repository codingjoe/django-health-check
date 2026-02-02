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
