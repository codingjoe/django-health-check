import dataclasses
import json
from unittest.mock import Mock

import pytest
from django.db import DatabaseError
from django.urls import reverse

from health_check.backends import HealthCheck
from health_check.conf import HEALTH_CHECK
from health_check.exceptions import ServiceWarning
from health_check.plugins import plugin_dir
from health_check.views import HealthCheckView, MediaType


class TestMediaType:
    def test_lt(self):
        assert not MediaType("*/*") < MediaType("*/*")
        assert not MediaType("*/*") < MediaType("*/*", 0.9)
        assert MediaType("*/*", 0.9) < MediaType("*/*")

    def test_str(self):
        assert str(MediaType("*/*")) == "*/*; q=1.0"
        assert str(MediaType("image/*", 0.6)) == "image/*; q=0.6"

    def test_repr(self):
        assert repr(MediaType("*/*")) == "MediaType: */*; q=1.0"

    def test_eq(self):
        assert MediaType("*/*") == MediaType("*/*")
        assert MediaType("*/*", 0.9) != MediaType("*/*")

    valid_strings = [
        ("*/*", MediaType("*/*")),
        ("*/*; q=0.9", MediaType("*/*", 0.9)),
        ("*/*; q=0", MediaType("*/*", 0.0)),
        ("*/*; q=0.0", MediaType("*/*", 0.0)),
        ("*/*; q=0.1", MediaType("*/*", 0.1)),
        ("*/*; q=0.12", MediaType("*/*", 0.12)),
        ("*/*; q=0.123", MediaType("*/*", 0.123)),
        ("*/*; q=1.000", MediaType("*/*", 1.0)),
        ("*/*; q=1", MediaType("*/*", 1.0)),
        ("*/*;q=0.9", MediaType("*/*", 0.9)),
        ("*/* ;q=0.9", MediaType("*/*", 0.9)),
        ("*/* ; q=0.9", MediaType("*/*", 0.9)),
        ("*/* ;   q=0.9", MediaType("*/*", 0.9)),
        ("*/*;v=b3", MediaType("*/*")),
        ("*/*; q=0.5; v=b3", MediaType("*/*", 0.5)),
    ]

    @pytest.mark.parametrize("type, expected", valid_strings)
    def test_from_valid_strings(self, type, expected):
        assert MediaType.from_string(type) == expected

    invalid_strings = [
        "*/*;0.9",
        'text/html;z=""',
        "text/html; xxx",
        "text/html;  =a",
    ]

    @pytest.mark.parametrize("type", invalid_strings)
    def test_from_invalid_strings(self, type):
        with pytest.raises(ValueError) as e:
            MediaType.from_string(type)
        expected_error = f'"{type}" is not a valid media type'
        assert expected_error in str(e.value)

    def test_parse_header(self):
        assert list(MediaType.parse_header()) == [
            MediaType("*/*"),
        ]
        assert list(MediaType.parse_header("text/html; q=0.1, application/xhtml+xml; q=0.1 ,application/json")) == [
            MediaType("application/json"),
            MediaType("text/html", 0.1),
            MediaType("application/xhtml+xml", 0.1),
        ]


class TestMainView:
    url = reverse("health_check:health_check_home")

    def test_success(self, client):
        response = client.get(self.url)
        assert response.status_code == 200, response.content.decode("utf-8")
        assert response["content-type"] == "text/html; charset=utf-8"

    def test_error(self, client):
        class MyBackend(HealthCheck):
            def check_status(self):
                self.add_error("Super Fail!")

        plugin_dir.reset()
        plugin_dir.register(MyBackend)
        response = client.get(self.url)
        assert response.status_code == 500, response.content.decode("utf-8")
        assert response["content-type"] == "text/html; charset=utf-8"
        assert b"Super Fail!" in response.content

    def test_warning(self, client, monkeypatch):
        class MyBackend(HealthCheck):
            def check_status(self):
                raise ServiceWarning("so so")

        plugin_dir.reset()
        plugin_dir.register(MyBackend)
        response = client.get(self.url)
        assert response.status_code == 500, response.content.decode("utf-8")
        assert b"so so" in response.content, response.content

        monkeypatch.setattr("health_check.mixins.CheckMixin.warnings_as_errors", False)

        response = client.get(self.url)
        assert response.status_code == 200, response.content.decode("utf-8")
        assert response["content-type"] == "text/html; charset=utf-8"
        assert b"so so" in response.content, response.content

    def test_non_critical(self, client):
        class MyBackend(HealthCheck):
            critical_service = False

            def check_status(self):
                self.add_error("Super Fail!")

        plugin_dir.reset()
        plugin_dir.register(MyBackend)
        response = client.get(self.url)
        assert response.status_code == 200, "Should be 200 OK for non-critical services"
        assert response["content-type"] == "text/html; charset=utf-8"
        assert b"Super Fail!" in response.content

    def test_success_accept_json(self, client):
        class JSONSuccessBackend(HealthCheck):
            def run_check(self):
                pass

        plugin_dir.reset()
        plugin_dir.register(JSONSuccessBackend)
        response = client.get(self.url, HTTP_ACCEPT="application/json")
        assert response["content-type"] == "application/json"
        assert response.status_code == 200

    def test_success_prefer_json(self, client):
        class JSONSuccessBackend(HealthCheck):
            def run_check(self):
                pass

        plugin_dir.reset()
        plugin_dir.register(JSONSuccessBackend)
        response = client.get(self.url, HTTP_ACCEPT="application/json; q=0.8, text/html; q=0.5")
        assert response["content-type"] == "application/json"
        assert response.status_code == 200

    def test_success_accept_xhtml(self, client):
        class SuccessBackend(HealthCheck):
            def run_check(self):
                pass

        plugin_dir.reset()
        plugin_dir.register(SuccessBackend)
        response = client.get(self.url, HTTP_ACCEPT="application/xhtml+xml")
        assert response["content-type"] == "text/html; charset=utf-8"
        assert response.status_code == 200

    def test_success_unsupported_accept(self, client):
        class SuccessBackend(HealthCheck):
            def run_check(self):
                pass

        plugin_dir.reset()
        plugin_dir.register(SuccessBackend)
        response = client.get(self.url, HTTP_ACCEPT="application/octet-stream")
        assert response["content-type"] == "text/plain"
        assert response.status_code == 406
        assert response.content == b"Not Acceptable: Supported content types: text/html, application/json"

    def test_success_unsupported_and_supported_accept(self, client):
        class SuccessBackend(HealthCheck):
            def run_check(self):
                pass

        plugin_dir.reset()
        plugin_dir.register(SuccessBackend)
        response = client.get(self.url, HTTP_ACCEPT="application/octet-stream, application/json; q=0.9")
        assert response["content-type"] == "application/json"
        assert response.status_code == 200

    def test_success_accept_order(self, client):
        class JSONSuccessBackend(HealthCheck):
            def run_check(self):
                pass

        plugin_dir.reset()
        plugin_dir.register(JSONSuccessBackend)
        response = client.get(
            self.url,
            HTTP_ACCEPT="text/html, application/xhtml+xml, application/json; q=0.9, */*; q=0.1",
        )
        assert response["content-type"] == "text/html; charset=utf-8"
        assert response.status_code == 200

    def test_success_accept_order__reverse(self, client):
        class JSONSuccessBackend(HealthCheck):
            def run_check(self):
                pass

        plugin_dir.reset()
        plugin_dir.register(JSONSuccessBackend)
        response = client.get(
            self.url,
            HTTP_ACCEPT="text/html; q=0.1, application/xhtml+xml; q=0.1, application/json",
        )
        assert response["content-type"] == "application/json"
        assert response.status_code == 200

    def test_format_override(self, client):
        class JSONSuccessBackend(HealthCheck):
            def run_check(self):
                pass

        plugin_dir.reset()
        plugin_dir.register(JSONSuccessBackend)
        response = client.get(self.url + "?format=json", HTTP_ACCEPT="text/html")
        assert response["content-type"] == "application/json"
        assert response.status_code == 200

    def test_format_no_accept_header(self, client):
        class JSONSuccessBackend(HealthCheck):
            def run_check(self):
                pass

        plugin_dir.reset()
        plugin_dir.register(JSONSuccessBackend)
        response = client.get(self.url)
        assert response.status_code == 200, response.content.decode("utf-8")
        assert response["content-type"] == "text/html; charset=utf-8"

    def test_error_accept_json(self, client):
        class JSONErrorBackend(HealthCheck):
            def run_check(self):
                self.add_error("JSON Error")

        plugin_dir.reset()
        plugin_dir.register(JSONErrorBackend)
        response = client.get(self.url, HTTP_ACCEPT="application/json")
        assert response.status_code == 500, response.content.decode("utf-8")
        assert response["content-type"] == "application/json"
        assert "JSON Error" in json.loads(response.content.decode("utf-8"))[repr(JSONErrorBackend())]

    def test_success_param_json(self, client):
        @dataclasses.dataclass
        class JSONSuccessBackend(HealthCheck):
            def run_check(self):
                pass

        plugin_dir.reset()
        plugin_dir.register(JSONSuccessBackend)
        response = client.get(self.url, {"format": "json"})
        assert response.status_code == 200, response.content.decode("utf-8")
        assert response["content-type"] == "application/json"
        assert json.loads(response.content.decode("utf-8")) == {
            repr(JSONSuccessBackend()): JSONSuccessBackend().pretty_status()
        }

    def test_success_subset_define(self, client):
        class SuccessOneBackend(HealthCheck):
            def run_check(self):
                pass

        class SuccessTwoBackend(HealthCheck):
            def run_check(self):
                pass

        plugin_dir.reset()
        plugin_dir.register(SuccessOneBackend)
        plugin_dir.register(SuccessTwoBackend)

        HEALTH_CHECK["SUBSETS"] = {
            "startup-probe": ["SuccessOneBackend", "SuccessTwoBackend"],
            "liveness-probe": ["SuccessTwoBackend"],
        }

        response_startup_probe = client.get(self.url + "startup-probe/", {"format": "json"})
        assert response_startup_probe.status_code == 200, response_startup_probe.content.decode("utf-8")
        assert response_startup_probe["content-type"] == "application/json"
        assert json.loads(response_startup_probe.content.decode("utf-8")) == {
            repr(SuccessOneBackend()): SuccessOneBackend().pretty_status(),
            repr(SuccessTwoBackend()): SuccessTwoBackend().pretty_status(),
        }

        response_liveness_probe = client.get(self.url + "liveness-probe/", {"format": "json"})
        assert response_liveness_probe.status_code == 200, response_liveness_probe.content.decode("utf-8")
        assert response_liveness_probe["content-type"] == "application/json"
        assert json.loads(response_liveness_probe.content.decode("utf-8")) == {
            repr(SuccessTwoBackend()): SuccessTwoBackend().pretty_status(),
        }

    def test_error_subset_not_found(self, client):
        plugin_dir.reset()
        response = client.get(self.url + "liveness-probe/", {"format": "json"})
        print(f"content: {response.content}")
        print(f"code: {response.status_code}")
        assert response.status_code == 404, response.content.decode("utf-8")

    def test_error_param_json(self, client):
        @dataclasses.dataclass
        class JSONErrorBackend(HealthCheck):
            def run_check(self):
                self.add_error("JSON Error")

        plugin_dir.reset()
        plugin_dir.register(JSONErrorBackend)
        response = client.get(self.url, {"format": "json"})
        assert response.status_code == 500, response.content.decode("utf-8")
        assert response["content-type"] == "application/json"
        assert "JSON Error" in json.loads(response.content.decode("utf-8"))[repr(JSONErrorBackend())]

    @pytest.mark.django_db(transaction=True)
    def test_non_native_atomic_request(self, settings, monkeypatch, client):
        # See also: https://github.com/codingjoe/django-health-check/pull/469
        settings.DATABASES["default"]["ATOMIC_REQUESTS"] = True
        # disable the ensure_connection
        monkeypatch.setattr(
            "django.db.backends.base.base.BaseDatabaseWrapper.ensure_connection", Mock(side_effect=DatabaseError())
        )
        response = client.get(self.url)
        assert response.status_code == 500
        assert b"System status" in response.content


class TestHealthCheckView:
    def test_checks__default(self):
        """
        Default checks should be the registered plugins.

        Regression test for https://github.com/codingjoe/django-health-check/issues/625
        """
        view = HealthCheckView()
        assert next(view.get_plugins())

    def test_checks__empty(self):
        """
        Checks can be overridden with an empty list.

        Regression test for https://github.com/codingjoe/django-health-check/issues/625
        """
        view = HealthCheckView(checks=[])
        assert not list(view.get_plugins())

    def test_as_view__return_callable(self):
        """Return a callable view function."""
        view = HealthCheckView.as_view()
        assert callable(view)

    def test_as_view__warn_warnings_as_errors(self):
        """Emit deprecation warning when warnings_as_errors is passed."""
        with pytest.warns(DeprecationWarning, match=r"`warnings_as_errors` argument is deprecated"):
            view = HealthCheckView.as_view(warnings_as_errors=True)
        assert callable(view)

    def test_as_view__warn_use_threading(self):
        """Emit deprecation warning when use_threading is passed."""
        with pytest.warns(DeprecationWarning, match=r"`use_threading` argument is deprecated"):
            view = HealthCheckView.as_view(use_threading=True)
        assert callable(view)
