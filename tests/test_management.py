"""Tests for health_check management command."""

import urllib.error
from io import StringIO
from unittest import mock

import pytest
from django.core.management import call_command


class TestHealthCheckCommand:
    """Test health_check management command."""

    def test_handle__success(self):
        """Return exit code 0 when all checks pass."""
        mock_response_data = "Cache: OK\nDatabase: OK\nDisk: OK\n"

        with mock.patch("urllib.request.urlopen") as mock_urlopen:
            mock_response = mock.MagicMock()
            mock_response.read.return_value = mock_response_data.encode("utf-8")
            mock_response.getcode.return_value = 200
            mock_urlopen.return_value = mock_response

            stdout = StringIO()
            stderr = StringIO()
            call_command(
                "health_check",
                "health_check",
                stdout=stdout,
                stderr=stderr,
            )
            output = stdout.getvalue()
            assert "Cache" in output
            assert "Database" in output
            assert "Disk" in output
            assert "OK" in output

    def test_handle__with_error(self):
        """Return exit code 1 when checks fail."""
        mock_response_data = "Cache: OK\nDatabase: unavailable: Connection failed\n"

        with mock.patch("urllib.request.urlopen") as mock_urlopen:
            mock_response = mock.MagicMock()
            mock_response.read.return_value = mock_response_data.encode("utf-8")
            mock_response.getcode.return_value = 500
            mock_urlopen.return_value = mock_response

            stdout = StringIO()
            stderr = StringIO()
            with pytest.raises(SystemExit) as exc_info:
                call_command(
                    "health_check",
                    "health_check",
                    stdout=stdout,
                    stderr=stderr,
                )
            assert exc_info.value.code == 1
            output = stdout.getvalue()
            assert "Database" in output

    def test_handle__custom_host_port(self):
        """Accept custom host and port."""
        mock_response_data = "Cache: OK\n"

        with mock.patch("urllib.request.urlopen") as mock_urlopen:
            mock_response = mock.MagicMock()
            mock_response.read.return_value = mock_response_data.encode("utf-8")
            mock_response.getcode.return_value = 200
            mock_urlopen.return_value = mock_response

            stdout = StringIO()
            stderr = StringIO()
            call_command(
                "health_check",
                "health_check",
                "localhost:9000",
                stdout=stdout,
                stderr=stderr,
            )
            call_args = mock_urlopen.call_args[0][0]
            assert "9000" in call_args.full_url

    def test_handle__custom_host_only(self):
        """Accept custom host without port."""
        mock_response_data = "Cache: OK\n"

        with mock.patch("urllib.request.urlopen") as mock_urlopen:
            mock_response = mock.MagicMock()
            mock_response.read.return_value = mock_response_data.encode("utf-8")
            mock_response.getcode.return_value = 200
            mock_urlopen.return_value = mock_response

            stdout = StringIO()
            stderr = StringIO()
            call_command(
                "health_check",
                "health_check",
                "192.168.1.1",
                stdout=stdout,
                stderr=stderr,
            )
            call_args = mock_urlopen.call_args[0][0]
            assert "192.168.1.1" in call_args.full_url

    def test_handle__malformed_response_data(self):
        """Handle case when response contains malformed lines."""
        mock_response_data = "Cache: OK\nInvalidLine\nDatabase: working\n"

        with mock.patch("urllib.request.urlopen") as mock_urlopen:
            mock_response = mock.MagicMock()
            mock_response.read.return_value = mock_response_data.encode("utf-8")
            mock_response.getcode.return_value = 200
            mock_urlopen.return_value = mock_response

            stdout = StringIO()
            stderr = StringIO()
            call_command(
                "health_check",
                "health_check",
                stdout=stdout,
                stderr=stderr,
            )
            output = stdout.getvalue()
            assert "Cache" in output

    def test_handle__invalid_json_response(self):
        """Handle response that doesn't follow expected format gracefully."""
        with mock.patch("urllib.request.urlopen") as mock_urlopen:
            mock_response = mock.MagicMock()
            mock_response.read.return_value = b"This is not health check format"
            mock_response.getcode.return_value = 200
            mock_urlopen.return_value = mock_response

            stdout = StringIO()
            stderr = StringIO()
            # Should not crash, just not output anything
            call_command(
                "health_check",
                "health_check",
                stdout=stdout,
                stderr=stderr,
            )
            # At minimum, should not raise an exception

    def test_handle__url_error__connection_refused(self):
        """Return exit code 2 when URL cannot be reached (connection refused)."""
        with mock.patch("urllib.request.urlopen") as mock_urlopen:
            mock_urlopen.side_effect = urllib.error.URLError("Connection refused")

            stdout = StringIO()
            stderr = StringIO()
            with pytest.raises(SystemExit) as exc_info:
                call_command(
                    "health_check",
                    "health_check",
                    "fake-host.invalid:9999",
                    stdout=stdout,
                    stderr=stderr,
                )
            assert exc_info.value.code == 2
            error_output = stderr.getvalue()
            assert "not reachable" in error_output
            assert "ALLOWED_HOSTS" in error_output

    def test_handle__url_error__name_resolution_failed(self):
        """Return exit code 2 when hostname cannot be resolved."""
        with mock.patch("urllib.request.urlopen") as mock_urlopen:
            mock_urlopen.side_effect = urllib.error.URLError(
                "Name or service not known"
            )

            stdout = StringIO()
            stderr = StringIO()
            with pytest.raises(SystemExit) as exc_info:
                call_command(
                    "health_check",
                    "health_check",
                    "unknown-domain-12345.invalid",
                    stdout=stdout,
                    stderr=stderr,
                )
            assert exc_info.value.code == 2
            error_output = stderr.getvalue()
            assert "not reachable" in error_output

    def test_handle__http_error_response(self):
        """Handle HTTP error responses with error text."""
        error_response_data = "Database: unavailable: Connection failed\n"

        with mock.patch(
            "health_check.management.commands.health_check.urllib.request.urlopen"
        ) as mock_urlopen:
            http_error = urllib.error.HTTPError(
                "http://localhost:8000/health/", 500, "Server Error", {}, None
            )
            http_error.read = lambda: error_response_data.encode("utf-8")
            http_error.code = 500
            mock_urlopen.side_effect = http_error

            stdout = StringIO()
            stderr = StringIO()
            with pytest.raises(SystemExit) as exc_info:
                call_command(
                    "health_check",
                    "health_check",
                    stdout=stdout,
                    stderr=stderr,
                )
            assert exc_info.value.code == 1

    def test_handle__multiple_checks_all_ok(self):
        """Display all checks when they all pass."""
        mock_response_data = "Cache: OK\nDatabase: OK\nDisk: OK\nMemory: OK\nMail: OK\n"

        with mock.patch("urllib.request.urlopen") as mock_urlopen:
            mock_response = mock.MagicMock()
            mock_response.read.return_value = mock_response_data.encode("utf-8")
            mock_response.getcode.return_value = 200
            mock_urlopen.return_value = mock_response

            stdout = StringIO()
            stderr = StringIO()
            call_command(
                "health_check",
                "health_check",
                stdout=stdout,
                stderr=stderr,
            )
            output = stdout.getvalue()
            assert output.count("OK") == 5

    def test_handle__multiple_checks_with_mixed_status(self):
        """Display all checks with mixed success and error status."""
        mock_response_data = (
            "Cache: OK\n"
            "Database: unavailable: Connection failed\n"
            "Disk: OK\n"
            "Memory: warning: Memory usage high\n"
        )

        with mock.patch("urllib.request.urlopen") as mock_urlopen:
            mock_response = mock.MagicMock()
            mock_response.read.return_value = mock_response_data.encode("utf-8")
            mock_response.getcode.return_value = 500
            mock_urlopen.return_value = mock_response

            stdout = StringIO()
            stderr = StringIO()
            with pytest.raises(SystemExit) as exc_info:
                call_command(
                    "health_check",
                    "health_check",
                    stdout=stdout,
                    stderr=stderr,
                )
            assert exc_info.value.code == 1
            output = stdout.getvalue()
            assert "Cache" in output and "OK" in output
            assert "Database" in output and "unavailable" in output

    def test_handle__default_localhost(self):
        """Use default localhost:8000 when no address provided."""
        mock_response_data = "Cache: OK\n"

        with mock.patch("urllib.request.urlopen") as mock_urlopen:
            mock_response = mock.MagicMock()
            mock_response.read.return_value = mock_response_data.encode("utf-8")
            mock_response.getcode.return_value = 200
            mock_urlopen.return_value = mock_response

            stdout = StringIO()
            stderr = StringIO()
            call_command(
                "health_check",
                "health_check",
                stdout=stdout,
                stderr=stderr,
            )
            call_args = mock_urlopen.call_args[0][0]
            assert "localhost:8000" in call_args.full_url

    def test_handle__text_accept_header(self):
        """Send Accept: text/plain header."""
        mock_response_data = "Cache: OK\n"

        with mock.patch("urllib.request.urlopen") as mock_urlopen:
            mock_response = mock.MagicMock()
            mock_response.read.return_value = mock_response_data.encode("utf-8")
            mock_response.getcode.return_value = 200
            mock_urlopen.return_value = mock_response

            stdout = StringIO()
            stderr = StringIO()
            call_command(
                "health_check",
                "health_check",
                stdout=stdout,
                stderr=stderr,
            )
            call_args = mock_urlopen.call_args[0][0]
            assert "text/plain" in call_args.headers["Accept"]
