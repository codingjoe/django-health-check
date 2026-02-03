import dataclasses
import json

import pytest

from health_check.base import HealthCheck
from health_check.exceptions import HealthCheckException, ServiceWarning
from health_check.views import HealthCheckView, MediaType


class TestMediaType:
    def test_lt__equal_weight(self):
        """Equal weights do not satisfy less-than comparison."""
        assert not MediaType("*/*") < MediaType("*/*")
        assert not MediaType("*/*") < MediaType("*/*", 0.9)

    def test_lt__lesser_weight(self):
        """Lesser weight satisfies less-than comparison."""
        assert MediaType("*/*", 0.9) < MediaType("*/*")

    def test_str__default_weight(self):
        """Format string with default weight of 1.0."""
        assert str(MediaType("*/*")) == "*/*; q=1.0"

    def test_str__custom_weight(self):
        """Format string with custom weight."""
        assert str(MediaType("image/*", 0.6)) == "image/*; q=0.6"

    def test_repr__description(self):
        """Return descriptive representation."""
        assert repr(MediaType("*/*")) == "MediaType: */*; q=1.0"

    def test_eq__matching_values(self):
        """Equal media types compare as equal."""
        assert MediaType("*/*") == MediaType("*/*")

    def test_eq__different_weights(self):
        """Different weights make media types unequal."""
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
    def test_from_string__valid(self, type, expected):
        """Parse valid media type strings."""
        assert MediaType.from_string(type) == expected

    @pytest.mark.parametrize(
        "mime_type",
        [
            "*/*;0.9",
            'text/html;z=""',
            "text/html; xxx",
            "text/html;  =a",
        ],
    )
    def test_from_string__invalid(self, mime_type):
        """Raise ValueError for invalid media type strings."""
        with pytest.raises(ValueError) as e:
            MediaType.from_string(mime_type)
        expected_error = f'"{mime_type}" is not a valid media type'
        assert expected_error in str(e.value)

    def test_parse_header__default(self):
        """Parse default accept header."""
        assert list(MediaType.parse_header()) == [
            MediaType("*/*"),
        ]

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
        ]


class TestHealthCheckView:
    @pytest.mark.asyncio
    async def test_get__success(self, health_check_view):
        """Return 200 with HTML content when all checks pass."""

        class SuccessBackend(HealthCheck):
            async def run(self):
                pass

        response = await health_check_view([SuccessBackend])
        assert response.status_code == 200
        assert response["content-type"] == "text/html; charset=utf-8"

    @pytest.mark.asyncio
    async def test_get__error(self, health_check_view):
        """Return 500 with error message when check fails."""

        class FailingBackend(HealthCheck):
            async def run(self):
                raise HealthCheckException("Super Fail!")

        response = await health_check_view([FailingBackend])
        assert response.status_code == 500
        assert response["content-type"] == "text/html; charset=utf-8"
        assert b"Super Fail!" in response.content

    @pytest.mark.asyncio
    async def test_get__warning(self, health_check_view):
        """Return 500 when warning is raised (warnings are treated as errors)."""

        class WarningBackend(HealthCheck):
            async def run(self):
                raise ServiceWarning("so so")

        response = await health_check_view([WarningBackend])
        assert response.status_code == 500
        assert b"so so" in response.content

    @pytest.mark.asyncio
    async def test_get__non_critical_service(self, health_check_view):
        """Return 500 when any service fails (all services are critical by default)."""

        class FailingBackend(HealthCheck):
            async def run(self):
                raise HealthCheckException("Super Fail!")

        response = await health_check_view([FailingBackend])
        assert response.status_code == 500
        assert response["content-type"] == "text/html; charset=utf-8"
        assert b"Super Fail!" in response.content

    @pytest.mark.asyncio
    async def test_get__json_accept_header(self, health_check_view):
        """Return JSON when Accept header requests it."""

        class SuccessBackend(HealthCheck):
            async def run(self):
                pass

        response = await health_check_view(
            [SuccessBackend], accept_header="application/json"
        )
        assert response["content-type"] == "application/json"
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_get__json_preferred(self, health_check_view):
        """Return JSON when it is preferred in Accept header."""

        class SuccessBackend(HealthCheck):
            async def run(self):
                pass

        response = await health_check_view(
            [SuccessBackend],
            accept_header="application/json; q=0.8, text/html; q=0.5",
        )
        assert response["content-type"] == "application/json"
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_get__xhtml_fallback(self, health_check_view):
        """Return HTML when XHTML is requested (no XHTML support)."""

        class SuccessBackend(HealthCheck):
            async def run(self):
                pass

        response = await health_check_view(
            [SuccessBackend], accept_header="application/xhtml+xml"
        )
        assert response["content-type"] == "text/html; charset=utf-8"
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_get__unsupported_accept(self, health_check_view):
        """Return 406 when Accept header is unsupported."""

        class SuccessBackend(HealthCheck):
            async def run(self):
                pass

        response = await health_check_view(
            [SuccessBackend], accept_header="application/octet-stream"
        )
        assert response["content-type"] == "text/plain"
        assert response.status_code == 406
        assert (
            response.content
            == b"Not Acceptable: Supported content types: text/plain, text/html, application/json, application/atom+xml, application/rss+xml, application/openmetrics-text"
        )

    @pytest.mark.asyncio
    async def test_get__unsupported_with_fallback(self, health_check_view):
        """Return supported format when unsupported format requested with fallback."""

        class SuccessBackend(HealthCheck):
            async def run(self):
                pass

        response = await health_check_view(
            [SuccessBackend],
            accept_header="application/octet-stream, application/json; q=0.9",
        )
        assert response["content-type"] == "application/json"
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_get__html_preferred(self, health_check_view):
        """Prefer HTML when both HTML and JSON are acceptable."""

        class SuccessBackend(HealthCheck):
            async def run(self):
                pass

        response = await health_check_view(
            [SuccessBackend],
            accept_header="text/html, application/xhtml+xml, application/json; q=0.9, */*; q=0.1",
        )
        assert response["content-type"] == "text/html; charset=utf-8"
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_get__json_preferred_reverse_order(self, health_check_view):
        """Prefer JSON when it has higher weight."""

        class SuccessBackend(HealthCheck):
            async def run(self):
                pass

        response = await health_check_view(
            [SuccessBackend],
            accept_header="text/html; q=0.1, application/xhtml+xml; q=0.1, application/json",
        )
        assert response["content-type"] == "application/json"
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_get__format_parameter_override(self, health_check_view):
        """Format parameter overrides Accept header."""

        class SuccessBackend(HealthCheck):
            async def run(self):
                pass

        response = await health_check_view(
            [SuccessBackend], format_param="json", accept_header="text/html"
        )
        assert response["content-type"] == "application/json"
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_get__html_without_accept_header(self, health_check_view):
        """Return HTML by default without Accept header."""

        class SuccessBackend(HealthCheck):
            async def run(self):
                pass

        response = await health_check_view([SuccessBackend])
        assert response.status_code == 200
        assert response["content-type"] == "text/html; charset=utf-8"

    @pytest.mark.asyncio
    async def test_get__error_json_response(self, health_check_view):
        """Return JSON with error when Accept header requests JSON."""

        class FailingBackend(HealthCheck):
            async def run(self):
                raise HealthCheckException("JSON Error")

        response = await health_check_view(
            [FailingBackend], accept_header="application/json"
        )
        assert response.status_code == 500
        assert response["content-type"] == "application/json"
        assert (
            "JSON Error"
            in json.loads(response.content.decode("utf-8"))[repr(FailingBackend())]
        )

    @pytest.mark.asyncio
    async def test_get__json_format_parameter(self, health_check_view):
        """Return JSON response when format parameter is 'json'."""

        @dataclasses.dataclass
        class SuccessBackend(HealthCheck):
            async def run(self):
                pass

        response = await health_check_view([SuccessBackend], format_param="json")
        assert response.status_code == 200
        assert response["content-type"] == "application/json"
        assert json.loads(response.content.decode("utf-8")) == {
            repr(SuccessBackend()): SuccessBackend().pretty_status()
        }

    @pytest.mark.asyncio
    async def test_get__error_json_format_parameter(self, health_check_view):
        """Return JSON error response when format parameter is 'json'."""

        @dataclasses.dataclass
        class FailingBackend(HealthCheck):
            async def run(self):
                raise HealthCheckException("JSON Error")

        response = await health_check_view([FailingBackend], format_param="json")
        assert response.status_code == 500
        assert response["content-type"] == "application/json"
        assert (
            "JSON Error"
            in json.loads(response.content.decode("utf-8"))[repr(FailingBackend())]
        )

    @pytest.mark.asyncio
    async def test_get__atom_format_parameter(self, health_check_view):
        """Return Atom feed when format parameter is 'atom'."""

        @dataclasses.dataclass
        class SuccessBackend(HealthCheck):
            async def run(self):
                pass

        response = await health_check_view([SuccessBackend], format_param="atom")
        assert response.status_code == 200
        assert "application/atom+xml" in response["content-type"]
        assert b"<feed" in response.content
        assert b'xmlns="http://www.w3.org/2005/Atom"' in response.content

    @pytest.mark.asyncio
    async def test_get__rss_format_parameter(self, health_check_view):
        """Return RSS feed when format parameter is 'rss'."""

        @dataclasses.dataclass
        class SuccessBackend(HealthCheck):
            async def run(self):
                pass

        response = await health_check_view([SuccessBackend], format_param="rss")
        assert response.status_code == 200
        assert "application/rss+xml" in response["content-type"]
        assert b"<rss" in response.content

    @pytest.mark.asyncio
    async def test_get__atom_accept_header(self, health_check_view):
        """Return Atom feed when Accept header requests it."""

        class SuccessBackend(HealthCheck):
            async def run(self):
                pass

        response = await health_check_view(
            [SuccessBackend], accept_header="application/atom+xml"
        )
        assert "application/atom+xml" in response["content-type"]
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_get__rss_accept_header(self, health_check_view):
        """Return RSS feed when Accept header requests it."""

        class SuccessBackend(HealthCheck):
            async def run(self):
                pass

        response = await health_check_view(
            [SuccessBackend], accept_header="application/rss+xml"
        )
        assert "application/rss+xml" in response["content-type"]
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_get__atom_format_parameter_error(self, health_check_view):
        """Return 200 with Atom feed even when health checks fail."""

        class FailingBackend(HealthCheck):
            async def run(self):
                raise HealthCheckException("Check failed")

        response = await health_check_view([FailingBackend], format_param="atom")
        assert response.status_code == 200
        assert "application/atom+xml" in response["content-type"]
        assert b"<feed" in response.content
        assert b"error" in response.content or b"unhealthy" in response.content

    @pytest.mark.asyncio
    async def test_get__rss_format_parameter_error(self, health_check_view):
        """Return 200 with RSS feed even when health checks fail."""

        class FailingBackend(HealthCheck):
            async def run(self):
                raise HealthCheckException("Check failed")

        response = await health_check_view([FailingBackend], format_param="rss")
        assert response.status_code == 200
        assert "application/rss+xml" in response["content-type"]
        assert b"<rss" in response.content
        assert b"error" in response.content or b"unhealthy" in response.content

    @pytest.mark.asyncio
    async def test_get__atom_accept_header_error(self, health_check_view):
        """Return 200 with Atom feed even when health checks fail via Accept header."""

        class FailingBackend(HealthCheck):
            async def run(self):
                raise HealthCheckException("Check failed")

        response = await health_check_view(
            [FailingBackend], accept_header="application/atom+xml"
        )
        assert response.status_code == 200
        assert "application/atom+xml" in response["content-type"]
        assert b"error" in response.content or b"unhealthy" in response.content

    @pytest.mark.asyncio
    async def test_get__rss_accept_header_error(self, health_check_view):
        """Return 200 with RSS feed even when health checks fail via Accept header."""

        class FailingBackend(HealthCheck):
            async def run(self):
                raise HealthCheckException("Check failed")

        response = await health_check_view(
            [FailingBackend], accept_header="application/rss+xml"
        )
        assert response.status_code == 200
        assert "application/rss+xml" in response["content-type"]
        assert b"error" in response.content or b"unhealthy" in response.content

    @pytest.mark.asyncio
    async def test_get_plugins__with_string_import(self):
        """Import check from string path."""
        from django.test import AsyncRequestFactory

        factory = AsyncRequestFactory()
        request = factory.get("/")
        view = HealthCheckView.as_view(
            checks=["health_check.Disk"],
        )
        response = await view(request)
        response.render()
        plugins = view.view_initkwargs["checks"]
        assert plugins == ["health_check.Disk"]

    @pytest.mark.asyncio
    async def test_get_plugins__with_tuple_options(self):
        """Handle check tuples with options."""

        @dataclasses.dataclass
        class ConfigurableCheck(HealthCheck):
            value: int = 0

            async def run(self):
                if self.value < 0:
                    raise HealthCheckException("Invalid value")

        from django.test import AsyncRequestFactory

        factory = AsyncRequestFactory()
        request = factory.get("/")
        view = HealthCheckView.as_view(
            checks=[(ConfigurableCheck, {"value": 42})],
        )
        response = await view(request)
        if hasattr(response, "render"):
            response.render()
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_vary_header_on_accept(self, health_check_view):
        """Response includes Vary: Accept header for content negotiation."""

        class SuccessBackend(HealthCheck):
            async def run(self):
                pass

        response = await health_check_view([SuccessBackend])
        assert "Accept" in response.get("Vary", "")
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_vary_header_with_different_accept_headers(self, health_check_view):
        """Vary: Accept header is present for all response formats."""

        class SuccessBackend(HealthCheck):
            async def run(self):
                pass

        # Test with HTML response
        html_response = await health_check_view(
            [SuccessBackend], accept_header="text/html"
        )
        assert "Accept" in html_response.get("Vary", "")

        # Test with JSON response
        json_response = await health_check_view(
            [SuccessBackend], accept_header="application/json"
        )
        assert "Accept" in json_response.get("Vary", "")

        # Test with Atom response
        atom_response = await health_check_view(
            [SuccessBackend], accept_header="application/atom+xml"
        )
        assert "Accept" in atom_response.get("Vary", "")

        # Test with RSS response
        rss_response = await health_check_view(
            [SuccessBackend], accept_header="application/rss+xml"
        )
        assert "Accept" in rss_response.get("Vary", "")

    @pytest.mark.asyncio
    async def test_get__openmetrics_format_parameter(self, health_check_view):
        """Return OpenMetrics when format=openmetrics."""

        class SuccessBackend(HealthCheck):
            async def run(self):
                pass

        response = await health_check_view([SuccessBackend], format_param="openmetrics")
        assert response.status_code == 200
        assert "application/openmetrics-text" in response["content-type"]
        content = response.content.decode("utf-8")
        assert "django_health_check_status" in content
        assert "django_health_check_response_time_seconds" in content
        assert "django_health_check_overall_status" in content
        assert "# EOF" in content

    @pytest.mark.asyncio
    async def test_get__openmetrics_accept_header_openmetrics(self, health_check_view):
        """Return OpenMetrics when Accept header is application/openmetrics-text."""

        class SuccessBackend(HealthCheck):
            async def run(self):
                pass

        response = await health_check_view(
            [SuccessBackend], accept_header="application/openmetrics-text"
        )
        assert response.status_code == 200
        assert "application/openmetrics-text" in response["content-type"]
        content = response.content.decode("utf-8")
        assert "django_health_check_status" in content
        assert "# EOF" in content

    @pytest.mark.asyncio
    async def test_get__openmetrics_healthy_status(self, health_check_view):
        """OpenMetrics show healthy status when all checks pass."""

        class SuccessBackend(HealthCheck):
            async def run(self):
                pass

        response = await health_check_view([SuccessBackend], format_param="openmetrics")
        content = response.content.decode("utf-8")
        # Check that status metric is 1 (healthy)
        assert "SuccessBackend" in content
        assert "django_health_check_status" in content
        assert "} 1" in content
        # Check that overall status is 1 (all healthy)
        assert "django_health_check_overall_status 1" in content

    @pytest.mark.asyncio
    async def test_get__openmetrics_unhealthy_status(self, health_check_view):
        """OpenMetrics show unhealthy status when check fails."""

        class FailingBackend(HealthCheck):
            async def run(self):
                raise HealthCheckException("Check failed")

        response = await health_check_view([FailingBackend], format_param="openmetrics")
        content = response.content.decode("utf-8")
        # Check that status metric is 0 (unhealthy)
        assert "FailingBackend" in content
        assert "django_health_check_status" in content
        assert "} 0" in content
        # Check that overall status is 0 (at least one unhealthy)
        assert "django_health_check_overall_status 0" in content

    @pytest.mark.asyncio
    async def test_get__openmetrics_response_time(self, health_check_view):
        """OpenMetrics include response time."""

        class SuccessBackend(HealthCheck):
            async def run(self):
                pass

        response = await health_check_view([SuccessBackend], format_param="openmetrics")
        content = response.content.decode("utf-8")
        # Check that response time metric exists
        assert "django_health_check_response_time_seconds" in content
        assert "SuccessBackend" in content

    @pytest.mark.asyncio
    async def test_get__openmetrics_multiple_checks(self, health_check_view):
        """OpenMetrics handle multiple checks correctly."""

        class SuccessBackend(HealthCheck):
            async def run(self):
                pass

        class FailingBackend(HealthCheck):
            async def run(self):
                raise HealthCheckException("Failed")

        response = await health_check_view(
            [SuccessBackend, FailingBackend], format_param="openmetrics"
        )
        content = response.content.decode("utf-8")
        # Check that both checks are represented
        assert "SuccessBackend" in content
        assert "FailingBackend" in content
        # Check that both status metrics exist (we can't easily verify exact values without complex regex)
        lines = content.split("\n")
        status_lines = [line for line in lines if "django_health_check_status{" in line]
        assert len(status_lines) == 2

    @pytest.mark.asyncio
    async def test_get__openmetrics_label_sanitization(self, health_check_view):
        """OpenMetrics sanitize labels with special characters."""

        @dataclasses.dataclass
        class CustomCheck(HealthCheck):
            async def run(self):
                pass

            def __repr__(self):
                return "Custom-Check.Backend Test"

        response = await health_check_view([CustomCheck], format_param="openmetrics")
        content = response.content.decode("utf-8")
        # Check that the label value is present (with proper escaping)
        assert 'check="Custom-Check.Backend Test"' in content

    @pytest.mark.asyncio
    async def test_get__openmetrics_label_escaping(self, health_check_view):
        """OpenMetrics properly escape special characters in label values."""

        @dataclasses.dataclass
        class EscapingCheck(HealthCheck):
            async def run(self):
                pass

            def __repr__(self):
                return 'Test "quoted" value\\with\\backslashes\nand newlines'

        response = await health_check_view([EscapingCheck], format_param="openmetrics")
        content = response.content.decode("utf-8")
        # Check that special characters are properly escaped per OpenMetrics spec
        # Double quotes should be escaped as \"
        # Backslashes should be escaped as \\
        # Newlines should be escaped as \n
        assert (
            'Test \\"quoted\\" value\\\\with\\\\backslashes\\nand newlines' in content
        )

    @pytest.mark.asyncio
    async def test_get__openmetrics_metadata(self, health_check_view):
        """OpenMetrics include proper HELP and TYPE metadata."""

        class SuccessBackend(HealthCheck):
            async def run(self):
                pass

        response = await health_check_view([SuccessBackend], format_param="openmetrics")
        content = response.content.decode("utf-8")
        # Check for proper metadata
        assert "# HELP django_health_check_status" in content
        assert "# TYPE django_health_check_status gauge" in content
        assert "# HELP django_health_check_response_time_seconds" in content
        assert "# TYPE django_health_check_response_time_seconds gauge" in content
        assert "# HELP django_health_check_overall_status" in content
        assert "# TYPE django_health_check_overall_status gauge" in content

    @pytest.mark.asyncio
    async def test_get__text_format_parameter(self, health_check_view):
        """Return plain text when format=text."""

        class SuccessBackend(HealthCheck):
            async def run(self):
                pass

        response = await health_check_view([SuccessBackend], format_param="text")
        assert response.status_code == 200
        assert "text/plain" in response["content-type"]
        content = response.content.decode("utf-8")
        assert "SuccessBackend" in content
        assert ": OK" in content

    @pytest.mark.asyncio
    async def test_get__text_accept_header(self, health_check_view):
        """Return plain text when Accept header is text/plain."""

        class SuccessBackend(HealthCheck):
            async def run(self):
                pass

        response = await health_check_view([SuccessBackend], accept_header="text/plain")
        assert response.status_code == 200
        assert "text/plain" in response["content-type"]
        content = response.content.decode("utf-8")
        assert "SuccessBackend" in content
        assert ": OK" in content

    @pytest.mark.asyncio
    async def test_get__text_healthy_status(self, health_check_view):
        """Plain text shows OK when all checks pass."""

        class SuccessBackend(HealthCheck):
            async def run(self):
                pass

        response = await health_check_view([SuccessBackend], format_param="text")
        assert response.status_code == 200
        content = response.content.decode("utf-8")
        assert "SuccessBackend" in content
        assert ": OK" in content

    @pytest.mark.asyncio
    async def test_get__text_unhealthy_status(self, health_check_view):
        """Plain text shows error message when check fails."""

        class FailingBackend(HealthCheck):
            async def run(self):
                raise HealthCheckException("Check failed")

        response = await health_check_view([FailingBackend], format_param="text")
        assert response.status_code == 500
        content = response.content.decode("utf-8")
        assert "FailingBackend" in content
        assert "Check failed" in content

    @pytest.mark.asyncio
    async def test_get__text_multiple_checks(self, health_check_view):
        """Plain text handles multiple checks correctly."""

        class SuccessBackend(HealthCheck):
            async def run(self):
                pass

        class FailingBackend(HealthCheck):
            async def run(self):
                raise HealthCheckException("Failed")

        response = await health_check_view(
            [SuccessBackend, FailingBackend], format_param="text"
        )
        assert response.status_code == 500
        content = response.content.decode("utf-8")
        lines = content.strip().split("\n")
        assert len(lines) == 2
        assert "SuccessBackend" in content
        assert ": OK" in content
        assert "FailingBackend" in content
        assert "Failed" in content
