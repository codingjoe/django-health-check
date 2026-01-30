"""Tests for contrib modules to improve coverage."""

from io import StringIO
from unittest import mock

import pytest
from django.core.management import call_command
from django.test import TestCase


class TestRedisHealthCheckEdgeCases(TestCase):
    """Test edge cases in Redis health check."""

    @pytest.mark.skipif(
        not pytest.importorskip("redis", minversion=None), reason="redis not installed"
    )
    def test_redis_with_options(self):
        """Test Redis check with connection options."""
        from redis.exceptions import ConnectionError as RedisConnectionError

        from health_check.contrib.redis import Redis

        check = Redis(
            url="redis://localhost:9999/", options={"socket_connect_timeout": 0.01}
        )
        with mock.patch("health_check.contrib.redis.from_url") as mock_from_url:
            mock_from_url.side_effect = RedisConnectionError("Connection error")

            check.check_status()
            assert len(check.errors) > 0
            assert "Unable to connect to Redis" in str(check.errors[0])


class TestManagementCommandEdgeCases:
    """Test edge cases in management command."""

    def test_command_endpoint_http_error(self, monkeypatch):
        """Test command with HTTP error response containing error JSON."""
        import urllib.error
        from io import BytesIO

        stdout = StringIO()

        class DummyResponse:
            def read(self):
                return b'{"Cache": "unavailable: error"}'

        def mock_urlopen(req):
            error = urllib.error.HTTPError(
                "http://localhost:8000/health",
                500,
                "Internal Server Error",
                {},
                BytesIO(b'{"Cache": "unavailable: error"}'),
            )
            raise error

        monkeypatch.setattr(
            "health_check.management.commands.health_check.urllib.request.urlopen",
            mock_urlopen,
        )

        with pytest.raises(SystemExit) as exc_info:
            call_command(
                "health_check",
                "health_check:health_check_home",
                stdout=stdout,
                addrport="127.0.0.1:8000",
            )
        # Should exit with code 1 because there are errors
        assert exc_info.value.code == 1

    def test_command_endpoint_url_error(self, monkeypatch):
        """Test command with URL error (unreachable host)."""
        import urllib.error

        stderr = StringIO()

        def mock_urlopen(req):
            raise urllib.error.URLError("Name or service not known")

        monkeypatch.setattr(
            "health_check.management.commands.health_check.urllib.request.urlopen",
            mock_urlopen,
        )

        with pytest.raises(SystemExit) as exc_info:
            call_command(
                "health_check",
                "health_check:health_check_home",
                stderr=stderr,
                addrport="127.0.0.1:8000",
            )
        assert exc_info.value.code == 2

    def test_command_endpoint_with_errors(self, monkeypatch):
        """Test command when endpoint returns errors."""
        stdout = StringIO()

        class DummyResponse:
            def __init__(self, data: bytes):
                self._data = data

            def read(self):
                return self._data

        monkeypatch.setattr(
            "health_check.management.commands.health_check.urllib.request.urlopen",
            lambda req: DummyResponse(
                b'{"Cache": "unavailable: Connection refused", "Database": "OK"}'
            ),
        )

        with pytest.raises(SystemExit) as exc_info:
            call_command(
                "health_check",
                "health_check:health_check_home",
                stdout=stdout,
                addrport="127.0.0.1:8000",
            )
        assert exc_info.value.code == 1

    def test_command_endpoint_addrport_with_port(self, monkeypatch):
        """Test command with explicit port in addrport."""
        stdout = StringIO()

        class DummyResponse:
            def read(self):
                return b'{"Label": "OK"}'

        monkeypatch.setattr(
            "health_check.management.commands.health_check.urllib.request.urlopen",
            lambda req: DummyResponse(),
        )

        call_command(
            "health_check",
            "health_check:health_check_home",
            stdout=stdout,
            addrport="127.0.0.1:8000",
        )
        stdout.seek(0)
        out = stdout.read()
        assert "Label" in out

    def test_command_endpoint_addrport_without_port(self, monkeypatch):
        """Test command without explicit port in addrport."""
        stdout = StringIO()

        class DummyResponse:
            def read(self):
                return b'{"Label": "OK"}'

        monkeypatch.setattr(
            "health_check.management.commands.health_check.urllib.request.urlopen",
            lambda req: DummyResponse(),
        )

        call_command(
            "health_check",
            "health_check:health_check_home",
            stdout=stdout,
            addrport="127.0.0.1",
        )
        stdout.seek(0)
        out = stdout.read()
        assert "Label" in out
