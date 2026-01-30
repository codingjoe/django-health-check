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

    def test_command(self):
        stdout = StringIO()
        with pytest.raises(SystemExit):
            call_command("health_check", stdout=stdout)
        stdout.seek(0)
        output = stdout.read()
        assert "Oops" in output
        assert "OK" in output

    def test_command_with_subset(self):
        SUBSET_NAME_1 = "subset-1"
        SUBSET_NAME_2 = "subset-2"
        HEALTH_CHECK["SUBSETS"] = {
            SUBSET_NAME_1: ["OkPlugin"],
            SUBSET_NAME_2: ["OkPlugin", "FailPlugin"],
        }

        stdout = StringIO()
        call_command("health_check", f"--subset={SUBSET_NAME_1}", stdout=stdout)
        stdout.seek(0)
        output = stdout.read()
        assert "OK" in output

    def test_command_with_failed_check_subset(self):
        SUBSET_NAME = "subset-2"
        HEALTH_CHECK["SUBSETS"] = {SUBSET_NAME: ["OkPlugin", "FailPlugin"]}

        stdout = StringIO()
        with pytest.raises(SystemExit):
            call_command("health_check", f"--subset={SUBSET_NAME}", stdout=stdout)
        stdout.seek(0)
        output = stdout.read()
        assert "FailPlugin" in output
        assert "unknown error: Oops" in output
        assert "OkPlugin" in output
        assert "OK" in output

    def test_command_with_non_existence_subset(self):
        SUBSET_NAME = "subset-2"
        NON_EXISTENCE_SUBSET_NAME = "abcdef12"
        HEALTH_CHECK["SUBSETS"] = {SUBSET_NAME: ["OkPlugin"]}

        stdout = StringIO()
        with pytest.raises(SystemExit):
            call_command("health_check", f"--subset={NON_EXISTENCE_SUBSET_NAME}", stdout=stdout)
        stdout.seek(0)
        assert stdout.read() == (f"Subset: '{NON_EXISTENCE_SUBSET_NAME}' does not exist.\n")

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
        stdout = StringIO()

        class DummyResponse:
            def __init__(self, data: bytes):
                self._data = data

            def read(self):
                return self._data

        monkeypatch.setattr(
            "health_check.management.commands.health_check.urllib.request.urlopen",
            lambda req: DummyResponse(b"not-json"),
        )

        with pytest.raises(SystemExit):
            call_command("health_check", "health_check:health_check_home", stdout=stdout, addrport="127.0.0.1:8000")
        stdout.seek(0)
        assert "did not return valid JSON" in stdout.read()

    def test_command_endpoint_unreachable(self, monkeypatch):
        """If the endpoint is unreachable (URLError), the command should exit with an error and helpful message."""
        stdout = StringIO()

        def raise_url_error(req):
            import urllib.error

            raise urllib.error.URLError("fake unreachable")

        monkeypatch.setattr(
            "health_check.management.commands.health_check.urllib.request.urlopen",
            raise_url_error,
        )

        with pytest.raises(SystemExit):
            call_command("health_check", "health_check:health_check_home", stdout=stdout, addrport="127.0.0.1:8000")
        stdout.seek(0)
        assert "is not reachable" in stdout.read()
