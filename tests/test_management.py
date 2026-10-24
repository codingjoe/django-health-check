"""Tests for health_check management command."""

import os
from io import StringIO
from unittest.mock import Mock, patch
from urllib.error import HTTPError
from urllib.parse import urlparse

import pytest
from django.core.management import call_command

from health_check.management.commands.health_check import Command


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

    def test_handle__default_forwarded_proto_is_https(self, live_server):
        """X-Forwarded-Proto header defaults to 'https'."""
        parsed = urlparse(live_server.url)
        addrport = f"{parsed.hostname}:{parsed.port}"

        stdout = StringIO()
        stderr = StringIO()

        with patch("urllib.request.urlopen") as mock_urlopen:
            mock_response = Mock()
            mock_response.read.return_value = b"OK"
            mock_urlopen.return_value = mock_response

            with patch("urllib.request.Request") as mock_request:
                call_command(
                    "health_check",
                    "health_check_test",
                    addrport,
                    stdout=stdout,
                    stderr=stderr,
                )
                # Verify that Request was called with X-Forwarded-Proto: https
                call_args = mock_request.call_args
                # Extract headers from kwargs, falling back to positional args
                if "headers" in call_args.kwargs:
                    headers = call_args.kwargs["headers"]
                else:
                    headers = call_args.args[1] if len(call_args.args) > 1 else {}
                assert headers.get("X-Forwarded-Proto") == "https"
                # Verify command completed successfully
                output = stdout.getvalue()
                assert "OK" in output

    def test_handle__verbosity_level_0(self, live_server):
        """Verbosity level 0 shows minimal output."""
        parsed = urlparse(live_server.url)
        addrport = f"{parsed.hostname}:{parsed.port}"

        stdout = StringIO()
        stderr = StringIO()
        call_command(
            "health_check",
            "health_check_test",
            addrport,
            verbosity=0,
            stdout=stdout,
            stderr=stderr,
        )
        output = stdout.getvalue()
        # At verbosity 0, should still show results but no debug info
        assert "Checking health endpoint" not in output

    def test_handle__verbosity_level_2(self, live_server):
        """Verbosity level 2 shows debug information."""
        parsed = urlparse(live_server.url)
        addrport = f"{parsed.hostname}:{parsed.port}"

        stdout = StringIO()
        stderr = StringIO()
        call_command(
            "health_check",
            "health_check_test",
            addrport,
            auth_token="test-token",
            verbosity=2,
            stdout=stdout,
            stderr=stderr,
        )
        output = stdout.getvalue()
        # At verbosity 2, should show debug info about the request
        assert "Checking health endpoint" in output
        assert "with headers:" in output
        assert "test-token" not in output

    def test_handle__http_400_error(self, live_server):
        """Return exit code 2 and helpful message for HTTP 400 errors."""
        parsed = urlparse(live_server.url)
        addrport = f"{parsed.hostname}:{parsed.port}"

        stdout = StringIO()
        stderr = StringIO()

        with patch("urllib.request.urlopen") as mock_urlopen:
            mock_urlopen.side_effect = HTTPError(
                url=f"http://{addrport}/health/test/",
                code=400,
                msg="Bad Request",
                hdrs={},
                fp=None,
            )

            with pytest.raises(SystemExit) as exc_info:
                call_command(
                    "health_check",
                    "health_check_test",
                    addrport,
                    stdout=stdout,
                    stderr=stderr,
                )

            assert exc_info.value.code == 2
            error_output = stderr.getvalue()
            assert "not reachable" in error_output
            # Should suggest checking ALLOWED_HOSTS or using --forwarded-host
            assert "ALLOWED_HOSTS" in error_output
            assert "forwarded-host" in error_output

    def test_handle__unexpected_http_error(self, live_server):
        """Return exit code 2 and helpful message for unexpected HTTP errors."""
        parsed = urlparse(live_server.url)
        addrport = f"{parsed.hostname}:{parsed.port}"

        stdout = StringIO()
        stderr = StringIO()

        with patch("urllib.request.urlopen") as mock_urlopen:
            mock_urlopen.side_effect = HTTPError(
                url=f"http://{addrport}/health/test/",
                code=404,
                msg="Not Found",
                hdrs={},
                fp=None,
            )

            with pytest.raises(SystemExit) as exc_info:
                call_command(
                    "health_check",
                    "health_check_test",
                    addrport,
                    stdout=stdout,
                    stderr=stderr,
                )

            assert exc_info.value.code == 2
            error_output = stderr.getvalue()
            assert "Unexpected HTTP error" in error_output
            assert "invalid endpoint" in error_output

    def test_handle__timeout_error(self, live_server):
        """Return exit code 2 when request times out."""
        parsed = urlparse(live_server.url)
        addrport = f"{parsed.hostname}:{parsed.port}"

        stdout = StringIO()
        stderr = StringIO()

        with patch("urllib.request.urlopen") as mock_urlopen:
            mock_urlopen.side_effect = TimeoutError("Connection timed out")

            with pytest.raises(SystemExit) as exc_info:
                call_command(
                    "health_check",
                    "health_check_test",
                    addrport,
                    timeout=1,
                    stdout=stdout,
                    stderr=stderr,
                )

            assert exc_info.value.code == 2
            error_output = stderr.getvalue()
            assert "Timeout" in error_output

    def test_handle__invalid_endpoint(self):
        """Return exit code 2 when endpoint name is invalid."""
        stdout = StringIO()
        stderr = StringIO()

        with pytest.raises(SystemExit) as exc_info:
            call_command(
                "health_check",
                "nonexistent_endpoint",
                "localhost:8000",
                stdout=stdout,
                stderr=stderr,
            )

        assert exc_info.value.code == 2
        error_output = stderr.getvalue()
        assert "Could not resolve endpoint" in error_output
        assert "nonexistent_endpoint" in error_output

    def test_handle__default_addrport_from_env(self, live_server):
        """Default addrport uses HOST and PORT environment variables."""
        parsed = urlparse(live_server.url)

        # Set environment variables
        env_vars = {
            "HOST": parsed.hostname,
            "PORT": str(parsed.port),
        }

        stdout = StringIO()
        stderr = StringIO()

        with patch.dict(os.environ, env_vars):
            # Call command without addrport argument to use default
            call_command(
                "health_check",
                "health_check_test",
                stdout=stdout,
                stderr=stderr,
            )
            output = stdout.getvalue()
            assert "OK" in output or "working" in output

    @pytest.mark.django_db
    def test_handle__no_html_success(self):
        """Run checks directly without HTTP server when --no-http is provided."""
        stdout = StringIO()
        stderr = StringIO()
        with pytest.raises(SystemExit) as exc_info:
            call_command(
                "health_check",
                "health_check_test",
                use_http=False,
                stdout=stdout,
                stderr=stderr,
            )
        assert exc_info.value.code == 0
        output = stdout.getvalue()
        # Check that output contains health check results
        assert "Database" in output or "Cache" in output
        assert "OK" in output or "working" in output

    def test_handle__no_html_failure(self):
        """Return exit code 1 when checks fail with --no-http."""
        stdout = StringIO()
        stderr = StringIO()
        with pytest.raises(SystemExit) as exc_info:
            call_command(
                "health_check",
                "health_check_fail",
                use_http=False,
                stdout=stdout,
                stderr=stderr,
            )
        assert exc_info.value.code == 1
        output = stdout.getvalue()
        # Should display the error message from the failing check
        assert "Test failure" in output or "AlwaysFailingCheck" in output

    def test_handle__html_flag_uses_http_server(self, live_server):
        """Run checks via HTTP server when --http is explicitly provided."""
        parsed = urlparse(live_server.url)
        addrport = f"{parsed.hostname}:{parsed.port}"

        stdout = StringIO()
        stderr = StringIO()

        with patch("urllib.request.urlopen") as mock_urlopen:
            mock_response = Mock()
            mock_response.read.return_value = (
                b"Database(alias='default'): OK\nCache(alias='default'): OK\n"
            )
            mock_urlopen.return_value = mock_response

            call_command(
                "health_check",
                "health_check_test",
                addrport,
                use_http=True,
                stdout=stdout,
                stderr=stderr,
            )

            mock_urlopen.assert_called_once()
            output = stdout.getvalue()
            assert "OK" in output or "working" in output

    def test_handle__token_authenticates(self, live_server):
        """Send a bearer token when --auth-token is provided."""
        parsed = urlparse(live_server.url)
        addrport = f"{parsed.hostname}:{parsed.port}"

        stdout = StringIO()
        stderr = StringIO()
        call_command(
            "health_check",
            "health_check_auth",
            addrport,
            auth_token="test-token",
            stdout=stdout,
            stderr=stderr,
        )
        output = stdout.getvalue()
        assert "Database" in output or "Cache" in output
        assert "OK" in output or "working" in output

    def test_handle__missing_token_exits_2(self, live_server):
        """Return exit code 2 and an auth hint when the token is missing."""
        parsed = urlparse(live_server.url)
        addrport = f"{parsed.hostname}:{parsed.port}"

        stdout = StringIO()
        stderr = StringIO()
        with (
            patch.dict(os.environ, {"HEALTH_CHECK_AUTH_TOKEN": ""}),
            pytest.raises(SystemExit) as exc_info,
        ):
            call_command(
                "health_check",
                "health_check_auth",
                addrport,
                stdout=stdout,
                stderr=stderr,
            )
        assert exc_info.value.code == 2
        error_output = stderr.getvalue()
        assert "requires authentication" in error_output
        assert "--auth-token" in error_output
        assert "HEALTH_CHECK_AUTH_TOKEN" in error_output

    def test_handle__token_from_environment(self, live_server):
        """Use HEALTH_CHECK_AUTH_TOKEN from the environment as the default token."""
        parsed = urlparse(live_server.url)
        addrport = f"{parsed.hostname}:{parsed.port}"

        stdout = StringIO()
        stderr = StringIO()
        with patch.dict(os.environ, {"HEALTH_CHECK_AUTH_TOKEN": "test-token"}):
            call_command(
                "health_check",
                "health_check_auth",
                addrport,
                stdout=stdout,
                stderr=stderr,
            )
        output = stdout.getvalue()
        assert "OK" in output or "working" in output

    def test_build_headers__auth_token(self):
        """Set the Authorization header only when a token is provided."""
        headers = Command._build_headers({"auth_token": "test-token"})
        assert headers["Authorization"] == "Bearer test-token"

        assert "Authorization" not in Command._build_headers({"auth_token": None})
        assert "Authorization" not in Command._build_headers({"auth_token": ""})

    def test_redact_headers(self):
        """Mask the Authorization value without mutating the input headers."""
        headers = {"Accept": "text/plain", "Authorization": "Bearer test-token"}
        redacted = Command._redact_headers(headers)
        assert redacted == {
            "Accept": "text/plain",
            "Authorization": "Bearer ******",
        }
        assert redacted is not headers
        assert headers["Authorization"] == "Bearer test-token"

        public_headers = {"Accept": "text/plain"}
        assert Command._redact_headers(public_headers) is public_headers
