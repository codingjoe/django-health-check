import pytest

pytest.importorskip("celery")
from unittest.mock import patch

import pytest
from django.apps import apps
from django.conf import settings

from health_check.contrib.celery_ping.apps import HealthCheckConfig
from health_check.contrib.celery_ping.backends import CeleryPingHealthCheck


class TestCeleryPingHealthCheck:
    CELERY_APP_CONTROL_PING = "health_check.contrib.celery_ping.backends.app.control.ping"
    CELERY_APP_CONTROL_INSPECT_ACTIVE_QUEUES = (
        "health_check.contrib.celery_ping.backends.app.control.inspect.active_queues"
    )

    @pytest.fixture
    def health_check(self):
        return CeleryPingHealthCheck()

    def test_check_status_doesnt_add_errors_when_ping_successful(self, health_check):
        celery_worker = "celery@4cc150a7b49b"

        with (
            patch(
                self.CELERY_APP_CONTROL_PING,
                return_value=[
                    {celery_worker: CeleryPingHealthCheck.CORRECT_PING_RESPONSE},
                    {f"{celery_worker}-2": CeleryPingHealthCheck.CORRECT_PING_RESPONSE},
                ],
            ),
            patch(
                self.CELERY_APP_CONTROL_INSPECT_ACTIVE_QUEUES,
                return_value={celery_worker: [{"name": queue.name} for queue in settings.CELERY_QUEUES]},
            ),
        ):
            health_check.check_status()

            assert not health_check.errors

    def test_check_status_reports_errors_if_ping_responses_are_incorrect(self, health_check):
        with patch(
            self.CELERY_APP_CONTROL_PING,
            return_value=[
                {"celery1@4cc150a7b49b": CeleryPingHealthCheck.CORRECT_PING_RESPONSE},
                {"celery2@4cc150a7b49b": {}},
                {"celery3@4cc150a7b49b": {"error": "pong"}},
            ],
        ):
            health_check.check_status()

            assert len(health_check.errors) == 2

    def test_check_status_adds_errors_when_ping_successfull_but_not_all_defined_queues_have_consumers(
        self,
        health_check,
    ):
        celery_worker = "celery@4cc150a7b49b"
        queues = list(settings.CELERY_QUEUES)

        with (
            patch(
                self.CELERY_APP_CONTROL_PING,
                return_value=[{celery_worker: CeleryPingHealthCheck.CORRECT_PING_RESPONSE}],
            ),
            patch(
                self.CELERY_APP_CONTROL_INSPECT_ACTIVE_QUEUES,
                return_value={celery_worker: [{"name": queues.pop().name}]},
            ),
        ):
            health_check.check_status()

            assert len(health_check.errors) == len(queues)

    @pytest.mark.parametrize(
        "exception_to_raise",
        [
            IOError,
            TimeoutError,
        ],
    )
    def test_check_status_add_error_when_io_error_raised_from_ping(self, exception_to_raise, health_check):
        with patch(self.CELERY_APP_CONTROL_PING, side_effect=exception_to_raise):
            health_check.check_status()

            assert len(health_check.errors) == 1
            assert "ioerror" in health_check.errors[0].message.lower()

    @pytest.mark.parametrize("exception_to_raise", [ValueError, SystemError, IndexError, MemoryError])
    def test_check_status_add_error_when_any_exception_raised_from_ping(self, exception_to_raise, health_check):
        with patch(self.CELERY_APP_CONTROL_PING, side_effect=exception_to_raise):
            health_check.check_status()

            assert len(health_check.errors) == 1
            assert health_check.errors[0].message.lower() == "unknown error"

    def test_check_status_when_raised_exception_notimplementederror(self, health_check):
        expected_error_message = "notimplementederror: make sure celery_result_backend is set"

        with patch(self.CELERY_APP_CONTROL_PING, side_effect=NotImplementedError):
            health_check.check_status()

            assert len(health_check.errors) == 1
            assert health_check.errors[0].message.lower() == expected_error_message

    @pytest.mark.parametrize("ping_result", [None, list()])
    def test_check_status_add_error_when_ping_result_failed(self, ping_result, health_check):
        with patch(self.CELERY_APP_CONTROL_PING, return_value=ping_result):
            health_check.check_status()

            assert len(health_check.errors) == 1
            assert "workers unavailable" in health_check.errors[0].message.lower()


class TestCeleryPingHealthCheckApps:
    def test_apps(self):
        assert HealthCheckConfig.name == "health_check.contrib.celery_ping"

        celery_ping = apps.get_app_config("celery_ping")
        assert celery_ping.name == "health_check.contrib.celery_ping"
