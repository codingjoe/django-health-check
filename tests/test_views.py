import dataclasses
import json

import pytest
from django.test import RequestFactory

from health_check.backends import HealthCheck
from health_check.exceptions import ServiceWarning
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
        assert list(
            MediaType.parse_header(
                "text/html; q=0.1, application/xhtml+xml; q=0.1 ,application/json"
            )
        ) == [
            MediaType("application/json"),
            MediaType("text/html", 0.1),
            MediaType("application/xhtml+xml", 0.1),
        ]


class TestMainView:
    def test_success(self, health_check_view):
        # Use a simple empty backend for testing
        class SuccessBackend(HealthCheck):
            def run_check(self):
                pass

        response = health_check_view([SuccessBackend])
        assert response.status_code == 200
        assert response["content-type"] == "text/html; charset=utf-8"

    def test_error(self, health_check_view):
        class MyBackend(HealthCheck):
            def check_status(self):
                self.add_error("Super Fail!")

        response = health_check_view([MyBackend])
        assert response.status_code == 500
        assert response["content-type"] == "text/html; charset=utf-8"
        assert b"Super Fail!" in response.content

    def test_warning(self, health_check_view):
        class MyBackend(HealthCheck):
            def check_status(self):
                raise ServiceWarning("so so")

        # Test with warnings_as_errors=True (should return 500)
        factory = RequestFactory()
        request = factory.get("/")
        view = HealthCheckView.as_view(checks=[MyBackend], warnings_as_errors=True)
        response = view(request)
        if hasattr(response, "render"):
            response.render()
        assert response.status_code == 500
        assert b"so so" in response.content, response.content

        # Test with warnings_as_errors=False (should return 200)
        view = HealthCheckView.as_view(checks=[MyBackend], warnings_as_errors=False)
        response = view(request)
        if hasattr(response, "render"):
            response.render()
        assert response.status_code == 200
        assert response["content-type"] == "text/html; charset=utf-8"
        assert b"so so" in response.content, response.content

    def test_non_critical(self, health_check_view):
        class MyBackend(HealthCheck):
            critical_service = False

            def check_status(self):
                self.add_error("Super Fail!")

        response = health_check_view([MyBackend])
        assert response.status_code == 200, "Should be 200 OK for non-critical services"
        assert response["content-type"] == "text/html; charset=utf-8"
        assert b"Super Fail!" in response.content

    def test_success_accept_json(self, health_check_view):
        class JSONSuccessBackend(HealthCheck):
            def run_check(self):
                pass

        response = health_check_view(
            [JSONSuccessBackend], accept_header="application/json"
        )
        assert response["content-type"] == "application/json"
        assert response.status_code == 200

    def test_success_prefer_json(self, health_check_view):
        class JSONSuccessBackend(HealthCheck):
            def run_check(self):
                pass

        response = health_check_view(
            [JSONSuccessBackend],
            accept_header="application/json; q=0.8, text/html; q=0.5",
        )
        assert response["content-type"] == "application/json"
        assert response.status_code == 200

    def test_success_accept_xhtml(self, health_check_view):
        class SuccessBackend(HealthCheck):
            def run_check(self):
                pass

        response = health_check_view(
            [SuccessBackend], accept_header="application/xhtml+xml"
        )
        assert response["content-type"] == "text/html; charset=utf-8"
        assert response.status_code == 200

    def test_success_unsupported_accept(self, health_check_view):
        class SuccessBackend(HealthCheck):
            def run_check(self):
                pass

        response = health_check_view(
            [SuccessBackend], accept_header="application/octet-stream"
        )
        assert response["content-type"] == "text/plain"
        assert response.status_code == 406
        assert (
            response.content
            == b"Not Acceptable: Supported content types: text/html, application/json"
        )

    def test_success_unsupported_and_supported_accept(self, health_check_view):
        class SuccessBackend(HealthCheck):
            def run_check(self):
                pass

        response = health_check_view(
            [SuccessBackend],
            accept_header="application/octet-stream, application/json; q=0.9",
        )
        assert response["content-type"] == "application/json"
        assert response.status_code == 200

    def test_success_accept_order(self, health_check_view):
        class JSONSuccessBackend(HealthCheck):
            def run_check(self):
                pass

        response = health_check_view(
            [JSONSuccessBackend],
            accept_header="text/html, application/xhtml+xml, application/json; q=0.9, */*; q=0.1",
        )
        assert response["content-type"] == "text/html; charset=utf-8"
        assert response.status_code == 200

    def test_success_accept_order__reverse(self, health_check_view):
        class JSONSuccessBackend(HealthCheck):
            def run_check(self):
                pass

        response = health_check_view(
            [JSONSuccessBackend],
            accept_header="text/html; q=0.1, application/xhtml+xml; q=0.1, application/json",
        )
        assert response["content-type"] == "application/json"
        assert response.status_code == 200

    def test_format_override(self, health_check_view):
        class JSONSuccessBackend(HealthCheck):
            def run_check(self):
                pass

        response = health_check_view(
            [JSONSuccessBackend], format_param="json", accept_header="text/html"
        )
        assert response["content-type"] == "application/json"
        assert response.status_code == 200

    def test_format_no_accept_header(self, health_check_view):
        class JSONSuccessBackend(HealthCheck):
            def run_check(self):
                pass

        response = health_check_view([JSONSuccessBackend])
        assert response.status_code == 200
        assert response["content-type"] == "text/html; charset=utf-8"

    def test_error_accept_json(self, health_check_view):
        class JSONErrorBackend(HealthCheck):
            def run_check(self):
                self.add_error("JSON Error")

        response = health_check_view(
            [JSONErrorBackend], accept_header="application/json"
        )
        assert response.status_code == 500
        assert response["content-type"] == "application/json"
        assert (
            "JSON Error"
            in json.loads(response.content.decode("utf-8"))[repr(JSONErrorBackend())]
        )

    def test_success_param_json(self, health_check_view):
        @dataclasses.dataclass
        class JSONSuccessBackend(HealthCheck):
            def run_check(self):
                pass

        response = health_check_view([JSONSuccessBackend], format_param="json")
        assert response.status_code == 200
        assert response["content-type"] == "application/json"
        assert json.loads(response.content.decode("utf-8")) == {
            repr(JSONSuccessBackend()): JSONSuccessBackend().pretty_status()
        }

    def test_error_param_json(self, health_check_view):
        @dataclasses.dataclass
        class JSONErrorBackend(HealthCheck):
            def run_check(self):
                self.add_error("JSON Error")

        response = health_check_view([JSONErrorBackend], format_param="json")
        assert response.status_code == 500
        assert response["content-type"] == "application/json"
        assert (
            "JSON Error"
            in json.loads(response.content.decode("utf-8"))[repr(JSONErrorBackend())]
        )
