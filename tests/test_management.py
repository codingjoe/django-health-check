"""Tests for health_check management command."""

import json
import urllib.error
from io import StringIO
from unittest import mock

import pytest
from django.core.management import call_command
from django.test import TestCase


class TestHealthCheckCommand(TestCase):
    """Test health_check management command."""

    def test_handle__success(self):
        """Return exit code 0 when all checks pass."""
        mock_response_data = {
            "Cache": "OK",
            "Database": "OK",
            "Disk": "OK",
        }

        with mock.patch("urllib.request.urlopen") as mock_urlopen:
            mock_response = mock.MagicMock()
            mock_response.read.return_value = json.dumps(mock_response_data).encode(
                "utf-8"
            )
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
            assert "Cache" in output, "Should display Cache check"
            assert "Database" in output, "Should display Database check"
            assert "Disk" in output, "Should display Disk check"
            assert "OK" in output, "Should show OK status"

    def test_handle__with_error(self):
        """Return exit code 1 when checks fail."""
        mock_response_data = {
            "Cache": "OK",
            "Database": "unavailable: Connection failed",
        }

        with mock.patch("urllib.request.urlopen") as mock_urlopen:
            mock_response = mock.MagicMock()
            mock_response.read.return_value = json.dumps(mock_response_data).encode(
                "utf-8"
            )
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
            assert exc_info.value.code == 1, "Should exit with code 1 on errors"
            output = stdout.getvalue()
            assert "Database" in output, "Should display failed check"

    def test_handle__custom_host_port(self):
        """Accept custom host and port."""
        mock_response_data = {"Cache": "OK"}

        with (
            mock.patch("urllib.request.urlopen") as mock_urlopen,
            mock.patch("django.urls.reverse", return_value="/health/"),
        ):
            mock_response = mock.MagicMock()
            mock_response.read.return_value = json.dumps(mock_response_data).encode(
                "utf-8"
            )
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
            assert "9000" in call_args.full_url, "Should use custom port"

    def test_handle__custom_host_only(self):
        """Accept custom host without port."""
        mock_response_data = {"Cache": "OK"}

        with (
            mock.patch("urllib.request.urlopen") as mock_urlopen,
            mock.patch("django.urls.reverse", return_value="/health/"),
        ):
            mock_response = mock.MagicMock()
            mock_response.read.return_value = json.dumps(mock_response_data).encode(
                "utf-8"
            )
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
            assert "192.168.1.1" in call_args.full_url, "Should use custom host"

    def test_handle__malformed_response_data(self):
        """Handle case when response contains non-string JSON values."""
        mock_response_data = {
            "Cache": "OK",
            "Database": {"error": "Complex object"},
        }

        with mock.patch("urllib.request.urlopen") as mock_urlopen:
            mock_response = mock.MagicMock()
            mock_response.read.return_value = json.dumps(mock_response_data).encode(
                "utf-8"
            )
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
            assert exc_info.value.code == 1, "Should exit with code 1 on error"
            output = stdout.getvalue()
            assert "Cache" in output, "Should display Cache check"

    def test_handle__invalid_json_response(self):
        """Return exit code 2 when response is not valid JSON."""
        with mock.patch("urllib.request.urlopen") as mock_urlopen:
            mock_response = mock.MagicMock()
            mock_response.read.return_value = b"This is not JSON"
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
            assert exc_info.value.code == 2, "Should exit with code 2 on invalid JSON"
            error_output = stderr.getvalue()
            assert "valid JSON" in error_output, "Should indicate JSON is invalid"

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
            assert exc_info.value.code == 2, "Should exit with code 2 on URLError"
            error_output = stderr.getvalue()
            assert "not reachable" in error_output, (
                "Should indicate URL is not reachable"
            )
            assert "ALLOWED_HOSTS" in error_output, (
                "Should suggest checking ALLOWED_HOSTS"
            )

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
            assert exc_info.value.code == 2, (
                "Should exit with code 2 on name resolution failure"
            )
            error_output = stderr.getvalue()
            assert "not reachable" in error_output, (
                "Should indicate URL is not reachable"
            )

    def test_handle__http_error_response(self):
        """Handle HTTP error responses with valid error JSON."""
        error_response_data = {
            "Database": "unavailable: Connection failed",
        }

        with mock.patch(
            "health_check.management.commands.health_check.urllib.request.urlopen"
        ) as mock_urlopen:
            http_error_obj = mock.MagicMock()
            http_error_obj.read.return_value = json.dumps(error_response_data).encode(
                "utf-8"
            )
            mock_urlopen.side_effect = urllib.error.HTTPError(
                "http://localhost:8000/health/", 500, "Server Error", {}, None
            )
            mock_urlopen.side_effect.read = lambda: json.dumps(
                error_response_data
            ).encode("utf-8")

            stdout = StringIO()
            stderr = StringIO()
            with pytest.raises(SystemExit) as exc_info:
                call_command(
                    "health_check",
                    "health_check",
                    stdout=stdout,
                    stderr=stderr,
                )
            assert exc_info.value.code == 1, (
                "Should exit with code 1 when database error"
            )

    def test_handle__multiple_checks_all_ok(self):
        """Display all checks when they all pass."""
        mock_response_data = {
            "Cache": "OK",
            "Database": "OK",
            "Disk": "OK",
            "Memory": "OK",
            "Mail": "OK",
        }

        with mock.patch("urllib.request.urlopen") as mock_urlopen:
            mock_response = mock.MagicMock()
            mock_response.read.return_value = json.dumps(mock_response_data).encode(
                "utf-8"
            )
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
            assert output.count("OK") == 5, "Should display 5 OK statuses"

    def test_handle__multiple_checks_with_mixed_status(self):
        """Display all checks with mixed success and error status."""
        mock_response_data = {
            "Cache": "OK",
            "Database": "unavailable: Connection failed",
            "Disk": "OK",
            "Memory": "warning: Memory usage high",
        }

        with mock.patch("urllib.request.urlopen") as mock_urlopen:
            mock_response = mock.MagicMock()
            mock_response.read.return_value = json.dumps(mock_response_data).encode(
                "utf-8"
            )
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
            assert exc_info.value.code == 1, "Should exit with code 1 on any error"
            output = stdout.getvalue()
            assert "Cache" in output and "OK" in output, "Should show successful checks"
            assert "Database" in output and "unavailable" in output, (
                "Should show failed checks"
            )

    def test_handle__default_localhost(self):
        """Use default localhost:8000 when no address provided."""
        mock_response_data = {"Cache": "OK"}

        with (
            mock.patch("urllib.request.urlopen") as mock_urlopen,
            mock.patch("django.urls.reverse", return_value="/health/"),
        ):
            mock_response = mock.MagicMock()
            mock_response.read.return_value = json.dumps(mock_response_data).encode(
                "utf-8"
            )
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
            assert "localhost:8000" in call_args.full_url, (
                "Should default to localhost:8000"
            )

    def test_handle__json_accept_header(self):
        """Send Accept: application/json header."""
        mock_response_data = {"Cache": "OK"}

        with mock.patch("urllib.request.urlopen") as mock_urlopen:
            mock_response = mock.MagicMock()
            mock_response.read.return_value = json.dumps(mock_response_data).encode(
                "utf-8"
            )
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
            assert "application/json" in call_args.headers["Accept"], (
                "Should send JSON Accept header"
            )
