import dataclasses
import json

import pytest
from django.test import RequestFactory

from health_check.base import HealthCheck
from health_check.exceptions import ServiceWarning
from health_check.views import HealthCheckView, MediaType


class TestMediaType:
    def test_lt__equal_weight(self):
        """Equal weights do not satisfy less-than comparison."""
        assert not MediaType("*/*") < MediaType("*/*"), (
            "Equal weights should not be less than"
        )
        assert not MediaType("*/*") < MediaType("*/*", 0.9), (
            "Different mime types with same weight should not be less than"
        )

    def test_lt__lesser_weight(self):
        """Lesser weight satisfies less-than comparison."""
        assert MediaType("*/*", 0.9) < MediaType("*/*"), (
            "Lower weight should be less than higher weight"
        )

    def test_str__default_weight(self):
        """Format string with default weight of 1.0."""
        assert str(MediaType("*/*")) == "*/*; q=1.0", (
            "Should format with default weight 1.0"
        )

    def test_str__custom_weight(self):
        """Format string with custom weight."""
        assert str(MediaType("image/*", 0.6)) == "image/*; q=0.6", (
            "Should format with custom weight"
        )

    def test_repr__description(self):
        """Return descriptive representation."""
        assert repr(MediaType("*/*")) == "MediaType: */*; q=1.0", (
            "Should include class name in repr"
        )

    def test_eq__matching_values(self):
        """Equal media types compare as equal."""
        assert MediaType("*/*") == MediaType("*/*"), "Same values should be equal"

    def test_eq__different_weights(self):
        """Different weights make media types unequal."""
        assert MediaType("*/*", 0.9) != MediaType("*/*"), (
            "Different weights should be unequal"
        )

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
    def test_from_string__valid(self, type, expected):
        """Parse valid media type strings."""
        assert MediaType.from_string(type) == expected, f"Should parse {type} correctly"

    invalid_strings = [
        "*/*;0.9",
        'text/html;z=""',
        "text/html; xxx",
        "text/html;  =a",
    ]

    @pytest.mark.parametrize("type", invalid_strings)
    def test_from_string__invalid(self, type):
        """Raise ValueError for invalid media type strings."""
        with pytest.raises(ValueError) as e:
            MediaType.from_string(type)
        expected_error = f'"{type}" is not a valid media type'
        assert expected_error in str(e.value), (
            "Should include invalid type in error message"
        )

    def test_parse_header__default(self):
        """Parse default accept header."""
        assert list(MediaType.parse_header()) == [
            MediaType("*/*"),
        ], "Default header should parse to wildcard"

    def test_parse_header__multiple_types(self):
        """Parse multiple types and sort by weight."""
        assert list(
            MediaType.parse_header(
                "text/html; q=0.1, application/xhtml+xml; q=0.1 ,application/json"
            )
        ) == [
            MediaType("application/json"),
            MediaType("text/html", 0.1),
            MediaType("application/xhtml+xml", 0.1),
        ], "Should sort by weight descending"


class TestHealthCheckView:
    def test_get__success(self, health_check_view):
        """Return 200 with HTML content when all checks pass."""

        class SuccessBackend(HealthCheck):
            def check_status(self):
                pass

        response = health_check_view([SuccessBackend])
        assert response.status_code == 200, "Should return 200 OK"
        assert response["content-type"] == "text/html; charset=utf-8", (
            "Should return HTML"
        )

    def test_get__error(self, health_check_view):
        """Return 500 with error message when check fails."""

        class FailingBackend(HealthCheck):
            def check_status(self):
                self.add_error("Super Fail!")

        response = health_check_view([FailingBackend])
        assert response.status_code == 500, "Should return 500 error"
        assert response["content-type"] == "text/html; charset=utf-8", (
            "Should return HTML"
        )
        assert b"Super Fail!" in response.content, "Should include error message"

    def test_get__warning_as_error(self, health_check_view):
        """Return 500 when warning raised and warnings_as_errors=True."""

        class WarningBackend(HealthCheck):
            def check_status(self):
                raise ServiceWarning("so so")

        factory = RequestFactory()
        request = factory.get("/")
        view = HealthCheckView.as_view(checks=[WarningBackend], warnings_as_errors=True)
        response = view(request)
        if hasattr(response, "render"):
            response.render()
        assert response.status_code == 500, "Should return 500 for warning"
        assert b"so so" in response.content, "Should include warning message"

    def test_get__warning_not_error(self, health_check_view):
        """Return 200 when warning raised and warnings_as_errors=False."""

        class WarningBackend(HealthCheck):
            def check_status(self):
                raise ServiceWarning("so so")

        factory = RequestFactory()
        request = factory.get("/")
        view = HealthCheckView.as_view(
            checks=[WarningBackend], warnings_as_errors=False
        )
        response = view(request)
        if hasattr(response, "render"):
            response.render()
        assert response.status_code == 200, "Should return 200 for warning"
        assert response["content-type"] == "text/html; charset=utf-8", (
            "Should return HTML"
        )
        assert b"so so" in response.content, "Should include warning message"

    def test_get__non_critical_service(self, health_check_view):
        """Return 200 even when non-critical service fails."""

        class NonCriticalBackend(HealthCheck):
            critical_service = False

            def check_status(self):
                self.add_error("Super Fail!")

        response = health_check_view([NonCriticalBackend])
        assert response.status_code == 200, "Non-critical failure should return 200"
        assert response["content-type"] == "text/html; charset=utf-8", (
            "Should return HTML"
        )
        assert b"Super Fail!" in response.content, "Should include error message"

    def test_get__json_accept_header(self, health_check_view):
        """Return JSON when Accept header requests it."""

        class SuccessBackend(HealthCheck):
            def check_status(self):
                pass

        response = health_check_view([SuccessBackend], accept_header="application/json")
        assert response["content-type"] == "application/json", "Should return JSON"
        assert response.status_code == 200, "Should return 200 OK"

    def test_get__json_preferred(self, health_check_view):
        """Return JSON when it is preferred in Accept header."""

        class SuccessBackend(HealthCheck):
            def check_status(self):
                pass

        response = health_check_view(
            [SuccessBackend],
            accept_header="application/json; q=0.8, text/html; q=0.5",
        )
        assert response["content-type"] == "application/json", (
            "Should return preferred JSON"
        )
        assert response.status_code == 200, "Should return 200 OK"

    def test_get__xhtml_fallback(self, health_check_view):
        """Return HTML when XHTML is requested (no XHTML support)."""

        class SuccessBackend(HealthCheck):
            def check_status(self):
                pass

        response = health_check_view(
            [SuccessBackend], accept_header="application/xhtml+xml"
        )
        assert response["content-type"] == "text/html; charset=utf-8", (
            "Should fallback to HTML for XHTML"
        )
        assert response.status_code == 200, "Should return 200 OK"

    def test_get__unsupported_accept(self, health_check_view):
        """Return 406 when Accept header is unsupported."""

        class SuccessBackend(HealthCheck):
            def check_status(self):
                pass

        response = health_check_view(
            [SuccessBackend], accept_header="application/octet-stream"
        )
        assert response["content-type"] == "text/plain", (
            "Should return plain text error"
        )
        assert response.status_code == 406, "Should return 406 Not Acceptable"
        assert (
            response.content
            == b"Not Acceptable: Supported content types: text/html, application/json"
        ), "Should list supported types"

    def test_get__unsupported_with_fallback(self, health_check_view):
        """Return supported format when unsupported format requested with fallback."""

        class SuccessBackend(HealthCheck):
            def check_status(self):
                pass

        response = health_check_view(
            [SuccessBackend],
            accept_header="application/octet-stream, application/json; q=0.9",
        )
        assert response["content-type"] == "application/json", (
            "Should return JSON fallback"
        )
        assert response.status_code == 200, "Should return 200 OK"

    def test_get__html_preferred(self, health_check_view):
        """Prefer HTML when both HTML and JSON are acceptable."""

        class SuccessBackend(HealthCheck):
            def check_status(self):
                pass

        response = health_check_view(
            [SuccessBackend],
            accept_header="text/html, application/xhtml+xml, application/json; q=0.9, */*; q=0.1",
        )
        assert response["content-type"] == "text/html; charset=utf-8", (
            "Should prefer HTML"
        )
        assert response.status_code == 200, "Should return 200 OK"

    def test_get__json_preferred_reverse_order(self, health_check_view):
        """Prefer JSON when it has higher weight."""

        class SuccessBackend(HealthCheck):
            def check_status(self):
                pass

        response = health_check_view(
            [SuccessBackend],
            accept_header="text/html; q=0.1, application/xhtml+xml; q=0.1, application/json",
        )
        assert response["content-type"] == "application/json", (
            "Should prefer JSON by weight"
        )
        assert response.status_code == 200, "Should return 200 OK"

    def test_get__format_parameter_override(self, health_check_view):
        """Format parameter overrides Accept header."""

        class SuccessBackend(HealthCheck):
            def check_status(self):
                pass

        response = health_check_view(
            [SuccessBackend], format_param="json", accept_header="text/html"
        )
        assert response["content-type"] == "application/json", (
            "Format param should override header"
        )
        assert response.status_code == 200, "Should return 200 OK"

    def test_get__html_without_accept_header(self, health_check_view):
        """Return HTML by default without Accept header."""

        class SuccessBackend(HealthCheck):
            def check_status(self):
                pass

        response = health_check_view([SuccessBackend])
        assert response.status_code == 200, "Should return 200 OK"
        assert response["content-type"] == "text/html; charset=utf-8", (
            "Should default to HTML"
        )

    def test_get__error_json_response(self, health_check_view):
        """Return JSON with error when Accept header requests JSON."""

        class FailingBackend(HealthCheck):
            def check_status(self):
                self.add_error("JSON Error")

        response = health_check_view([FailingBackend], accept_header="application/json")
        assert response.status_code == 500, "Should return 500 error"
        assert response["content-type"] == "application/json", "Should return JSON"
        assert (
            "JSON Error"
            in json.loads(response.content.decode("utf-8"))[repr(FailingBackend())]
        ), "Should include error in JSON response"

    def test_get__json_format_parameter(self, health_check_view):
        """Return JSON response when format parameter is 'json'."""

        @dataclasses.dataclass
        class SuccessBackend(HealthCheck):
            def check_status(self):
                pass

        response = health_check_view([SuccessBackend], format_param="json")
        assert response.status_code == 200, "Should return 200 OK"
        assert response["content-type"] == "application/json", "Should return JSON"
        assert json.loads(response.content.decode("utf-8")) == {
            repr(SuccessBackend()): SuccessBackend().pretty_status()
        }, "Should return correct JSON structure"

    def test_get__error_json_format_parameter(self, health_check_view):
        """Return JSON error response when format parameter is 'json'."""

        @dataclasses.dataclass
        class FailingBackend(HealthCheck):
            def check_status(self):
                self.add_error("JSON Error")

        response = health_check_view([FailingBackend], format_param="json")
        assert response.status_code == 500, "Should return 500 error"
        assert response["content-type"] == "application/json", "Should return JSON"
        assert (
            "JSON Error"
            in json.loads(response.content.decode("utf-8"))[repr(FailingBackend())]
        ), "Should include error in JSON response"
