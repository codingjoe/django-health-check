from io import StringIO

import pytest
from django.core.management import call_command

from health_check.backends import HealthCheck
from health_check.conf import HEALTH_CHECK
from health_check.plugins import plugin_dir


class FailPlugin(HealthCheck):
    def check_status(self):
        self.add_error("Oops")


class OkPlugin(HealthCheck):
    def check_status(self):
        pass


class TestCommand:
    @pytest.fixture(autouse=True)
    def setup(self):
        plugin_dir.reset()
        plugin_dir.register(FailPlugin)
        plugin_dir.register(OkPlugin)
        yield
        plugin_dir.reset()

    def test_command_endpoint_ok(self, monkeypatch):
        """Calling the management command with an endpoint should fetch JSON and print results."""
        stdout = StringIO()

        class DummyResponse:
            def __init__(self, data: bytes):
                self._data = data

            def read(self):
                return self._data

        monkeypatch.setattr(
            "health_check.management.commands.health_check.urllib.request.urlopen",
            lambda req: DummyResponse(b'{"Label": "OK"}'),
        )

        # Should not raise SystemExit for all-OK response
        call_command("health_check", "health_check:health_check_home", stdout=stdout, addrport="127.0.0.1:8000")
        stdout.seek(0)
        out = stdout.read()
        assert "Label" in out
        assert "OK" in out

    def test_command_endpoint_invalid_json(self, monkeypatch):
        """If the endpoint returns invalid JSON, the command should exit with an error."""
        stderr = StringIO()

        class DummyResponse:
            def __init__(self, data: bytes):
                self._data = data

            def read(self):
                return self._data

        monkeypatch.setattr(
            "health_check.management.commands.health_check.urllib.request.urlopen",
            lambda req: DummyResponse(b"not-json"),
        )

        with pytest.raises(SystemExit) as excinfo:
            call_command("health_check", "health_check:health_check_home", stderr=stderr, addrport="127.0.0.1:8000")
        stderr.seek(0)
        assert excinfo.value.code == 2
        assert "did not return valid JSON" in stderr.read()

    def test_command_endpoint_unreachable(self, monkeypatch):
        """If the endpoint is unreachable (URLError), the command should exit with an error and helpful message."""
        stderr = StringIO()

        def raise_url_error(req):
            import urllib.error

            raise urllib.error.URLError("fake unreachable")

        monkeypatch.setattr(
            "health_check.management.commands.health_check.urllib.request.urlopen",
            raise_url_error,
        )

        with pytest.raises(SystemExit) as excinfo:
            call_command("health_check", "health_check:health_check_home", stderr=stderr, addrport="127.0.0.1:8000")
        stderr.seek(0)
        assert excinfo.value.code == 2
        assert "is not reachable" in stderr.read()
