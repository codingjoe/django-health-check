import datetime
from unittest import mock

import pytest

pytest.importorskip("httpx")

from health_check.contrib.atlassian import (
    Cloudflare,
    DigitalOcean,
    FlyIo,
    GitHub,
    PlatformSh,
    Render,
    Sentry,
    Vercel,
)
from health_check.exceptions import (
    ServiceUnavailable,
    ServiceWarning,
    StatusPageWarning,
)


def _make_response(components, incidents=None):
    """Build a minimal /api/v2/summary.json payload."""
    return {
        "page": {"id": "test"},
        "components": list(components),
        "incidents": list(incidents or []),
    }


def _component(name, status="operational", updated_at="2024-01-01T00:00:00.000Z"):
    return {"name": name, "status": status, "updated_at": updated_at}


def _incident(
    name,
    shortlink,
    status="investigating",
    updated_at="2024-01-01T06:00:00.000Z",
    components=None,
):
    return {
        "name": name,
        "shortlink": shortlink,
        "status": status,
        "updated_at": updated_at,
        "components": [{"name": c} for c in (components or [])],
    }


class TestFlyIo:
    """Test Fly.io platform status health check via Atlassian API."""

    @pytest.mark.asyncio
    async def test_check_status__ok(self):
        """Pass when there are no open incidents."""
        api_response = _make_response(
            [_component("Networking"), _component("Compute")],
        )

        with mock.patch(
            "health_check.contrib.atlassian.httpx.AsyncClient"
        ) as mock_client:
            mock_response = mock.MagicMock()
            mock_response.json.return_value = api_response
            mock_response.raise_for_status = mock.MagicMock()

            mock_context = mock.AsyncMock()
            mock_context.__aenter__.return_value.get = mock.AsyncMock(
                return_value=mock_response
            )
            mock_client.return_value = mock_context

            check = FlyIo()
            result = await check.get_result()
            assert result.error is None
            mock_context.__aenter__.return_value.get.assert_awaited_once()
            assert (
                mock_context.__aenter__.return_value.get.await_args.args[0]
                == "https://status.flyio.net/api/v2/summary.json"
            )

    @pytest.mark.asyncio
    async def test_check_status__raise_service_warning(self):
        """Raise ServiceWarning when an open incident is found."""
        api_response = _make_response(
            [_component("Networking", status="partial_outage")],
            incidents=[
                _incident(
                    "Networking degraded performance",
                    "https://stspg.io/abc123",
                    components=["Networking"],
                )
            ],
        )

        with mock.patch(
            "health_check.contrib.atlassian.httpx.AsyncClient"
        ) as mock_client:
            mock_response = mock.MagicMock()
            mock_response.json.return_value = api_response
            mock_response.raise_for_status = mock.MagicMock()

            mock_context = mock.AsyncMock()
            mock_context.__aenter__.return_value.get = mock.AsyncMock(
                return_value=mock_response
            )
            mock_client.return_value = mock_context

            check = FlyIo()
            result = await check.get_result()
            assert result.error is not None
            assert isinstance(result.error, ServiceWarning)
            assert "Networking degraded performance" in str(result.error)
            assert "https://stspg.io/abc123" in str(result.error)

    @pytest.mark.asyncio
    async def test_check_status__multiple_incidents(self):
        """Report all open incidents."""
        api_response = _make_response(
            [
                _component("Networking", status="partial_outage"),
                _component("Compute", status="major_outage"),
            ],
            incidents=[
                _incident(
                    "Networking issues",
                    "https://stspg.io/abc123",
                    components=["Networking"],
                ),
                _incident(
                    "Compute outage",
                    "https://stspg.io/def456",
                    components=["Compute"],
                ),
            ],
        )

        with mock.patch(
            "health_check.contrib.atlassian.httpx.AsyncClient"
        ) as mock_client:
            mock_response = mock.MagicMock()
            mock_response.json.return_value = api_response
            mock_response.raise_for_status = mock.MagicMock()

            mock_context = mock.AsyncMock()
            mock_context.__aenter__.return_value.get = mock.AsyncMock(
                return_value=mock_response
            )
            mock_client.return_value = mock_context

            check = FlyIo()
            result = await check.get_result()
            assert result.error is not None
            assert isinstance(result.error, ServiceWarning)
            assert "Networking issues" in str(result.error)
            assert "Compute outage" in str(result.error)

    @pytest.mark.asyncio
    async def test_check_status__incident_carries_source_timestamp(self):
        """StatusPageWarning carries the most recent incident updated_at as its timestamp."""
        api_response = _make_response(
            [
                _component("Networking", status="degraded_performance"),
                _component("Compute", status="partial_outage"),
            ],
            incidents=[
                _incident(
                    "Older incident",
                    "https://stspg.io/older",
                    updated_at="2024-01-01T00:00:00.000Z",
                ),
                _incident(
                    "Newer incident",
                    "https://stspg.io/newer",
                    updated_at="2024-01-01T06:00:00.000Z",
                ),
            ],
        )

        with mock.patch(
            "health_check.contrib.atlassian.httpx.AsyncClient"
        ) as mock_client:
            mock_response = mock.MagicMock()
            mock_response.json.return_value = api_response
            mock_response.raise_for_status = mock.MagicMock()

            mock_context = mock.AsyncMock()
            mock_context.__aenter__.return_value.get = mock.AsyncMock(
                return_value=mock_response
            )
            mock_client.return_value = mock_context

            check = FlyIo()
            result = await check.get_result()
            assert result.error is not None
            assert isinstance(result.error, StatusPageWarning)
            expected_ts = datetime.datetime(
                2024, 1, 1, 6, 0, 0, tzinfo=datetime.timezone.utc
            )
            assert result.error.timestamp == expected_ts, (
                "StatusPageWarning should carry the most recent incident timestamp"
            )

    @pytest.mark.asyncio
    async def test_check_status__resolved_incidents_are_filtered(self):
        """Resolved and postmortem incidents do not produce warnings."""
        api_response = _make_response(
            [_component("Networking")],
            incidents=[
                _incident(
                    "Resolved incident",
                    "https://stspg.io/resolved",
                    status="resolved",
                ),
                _incident(
                    "Postmortem incident",
                    "https://stspg.io/postmortem",
                    status="postmortem",
                ),
            ],
        )

        with mock.patch(
            "health_check.contrib.atlassian.httpx.AsyncClient"
        ) as mock_client:
            mock_response = mock.MagicMock()
            mock_response.json.return_value = api_response
            mock_response.raise_for_status = mock.MagicMock()

            mock_context = mock.AsyncMock()
            mock_context.__aenter__.return_value.get = mock.AsyncMock(
                return_value=mock_response
            )
            mock_client.return_value = mock_context

            check = FlyIo()
            result = await check.get_result()
            assert result.error is None, (
                "Resolved and postmortem incidents should not raise a warning"
            )

    @pytest.mark.asyncio
    async def test_check_status__http_error(self):
        """Raise ServiceUnavailable on HTTP error."""
        import httpx

        with mock.patch(
            "health_check.contrib.atlassian.httpx.AsyncClient"
        ) as mock_client:
            mock_response = mock.MagicMock()
            mock_response.status_code = 404
            mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
                "Not Found", request=mock.MagicMock(), response=mock_response
            )

            mock_context = mock.AsyncMock()
            mock_context.__aenter__.return_value.get = mock.AsyncMock(
                return_value=mock_response
            )
            mock_client.return_value = mock_context

            check = FlyIo()
            result = await check.get_result()
            assert result.error is not None
            assert isinstance(result.error, ServiceUnavailable)
            assert "HTTP error 404" in str(result.error)

    @pytest.mark.asyncio
    async def test_check_status__json_parse_error(self):
        """Raise ServiceUnavailable on JSON parse error."""
        with mock.patch(
            "health_check.contrib.atlassian.httpx.AsyncClient"
        ) as mock_client:
            mock_response = mock.MagicMock()
            mock_response.json.side_effect = ValueError("Invalid JSON")
            mock_response.raise_for_status = mock.MagicMock()

            mock_context = mock.AsyncMock()
            mock_context.__aenter__.return_value.get = mock.AsyncMock(
                return_value=mock_response
            )
            mock_client.return_value = mock_context

            check = FlyIo()
            result = await check.get_result()
            assert result.error is not None
            assert isinstance(result.error, ServiceUnavailable)
            assert "Failed to parse JSON" in str(result.error)

    def test_base_url_format(self):
        """Verify correct base URL for Fly.io."""
        check = FlyIo()
        assert check.base_url == "https://status.flyio.net"

    @pytest.mark.asyncio
    async def test_check_status__timeout(self):
        """Raise ServiceUnavailable on timeout."""
        import httpx

        with mock.patch(
            "health_check.contrib.atlassian.httpx.AsyncClient"
        ) as mock_client:
            mock_context = mock.AsyncMock()
            mock_context.__aenter__.return_value.get = mock.AsyncMock(
                side_effect=httpx.TimeoutException("Timed out")
            )
            mock_client.return_value = mock_context

            check = FlyIo()
            result = await check.get_result()
            assert result.error is not None
            assert isinstance(result.error, ServiceUnavailable)
            assert "timed out" in str(result.error).lower()

    @pytest.mark.asyncio
    async def test_check_status__request_error(self):
        """Raise ServiceUnavailable on request error."""
        import httpx

        with mock.patch(
            "health_check.contrib.atlassian.httpx.AsyncClient"
        ) as mock_client:
            mock_context = mock.AsyncMock()
            mock_context.__aenter__.return_value.get = mock.AsyncMock(
                side_effect=httpx.RequestError("Connection refused")
            )
            mock_client.return_value = mock_context

            check = FlyIo()
            result = await check.get_result()
            assert result.error is not None
            assert isinstance(result.error, ServiceUnavailable)
            assert "Failed to fetch API" in str(result.error)


class TestGitHub:
    """Test GitHub platform status health check via Atlassian API."""

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_check_status__live_summary_endpoint(self):
        """Verify the check can read a real Statuspage summary endpoint."""
        result = await GitHub().get_result()
        assert result.error is None or isinstance(result.error, StatusPageWarning)

    @pytest.mark.asyncio
    async def test_check_status__ok(self):
        """Pass when there are no open incidents."""
        api_response = _make_response(
            [_component("Actions"), _component("API Requests")],
        )

        with mock.patch(
            "health_check.contrib.atlassian.httpx.AsyncClient"
        ) as mock_client:
            mock_response = mock.MagicMock()
            mock_response.json.return_value = api_response
            mock_response.raise_for_status = mock.MagicMock()

            mock_context = mock.AsyncMock()
            mock_context.__aenter__.return_value.get = mock.AsyncMock(
                return_value=mock_response
            )
            mock_client.return_value = mock_context

            check = GitHub()
            result = await check.get_result()
            assert result.error is None

    @pytest.mark.asyncio
    async def test_check_status__missing_expected_key(self):
        """Raise ServiceUnavailable when the Statuspage payload is malformed."""
        api_response = {
            "page": {"id": "test"},
            "components": [_component("Actions")],
        }

        with mock.patch(
            "health_check.contrib.atlassian.httpx.AsyncClient"
        ) as mock_client:
            mock_response = mock.MagicMock()
            mock_response.json.return_value = api_response
            mock_response.raise_for_status = mock.MagicMock()

            mock_context = mock.AsyncMock()
            mock_context.__aenter__.return_value.get = mock.AsyncMock(
                return_value=mock_response
            )
            mock_client.return_value = mock_context

            check = GitHub()
            result = await check.get_result()
            assert result.error is not None
            assert isinstance(result.error, ServiceUnavailable)
            assert "Missing key 'incidents'" in str(result.error)

    def test_base_url_format(self):
        """Verify correct base URL for GitHub."""
        assert GitHub().base_url == "https://www.githubstatus.com"
        assert GitHub("eu").base_url == "https://eu.githubstatus.com"

    @pytest.mark.asyncio
    async def test_check_status__component_filter_match(self):
        """Raise ServiceWarning when an incident affects the watched component."""
        api_response = _make_response(
            [
                _component("Actions", status="partial_outage"),
                _component("API Requests"),
            ],
            incidents=[
                _incident(
                    "Actions degraded performance",
                    "https://stspg.io/abc123",
                    components=["Actions", "API Requests"],
                )
            ],
        )

        with mock.patch(
            "health_check.contrib.atlassian.httpx.AsyncClient"
        ) as mock_client:
            mock_response = mock.MagicMock()
            mock_response.json.return_value = api_response
            mock_response.raise_for_status = mock.MagicMock()

            mock_context = mock.AsyncMock()
            mock_context.__aenter__.return_value.get = mock.AsyncMock(
                return_value=mock_response
            )
            mock_client.return_value = mock_context

            check = GitHub(component="Actions")
            result = await check.get_result()
            assert result.error is not None
            assert isinstance(result.error, ServiceWarning)
            assert "Actions degraded performance" in str(result.error)
            assert "https://stspg.io/abc123" in str(result.error)

    @pytest.mark.asyncio
    async def test_check_status__component_filter_no_match(self):
        """Pass when no incident affects the watched component."""
        api_response = _make_response(
            [_component("Actions"), _component("Pages", status="partial_outage")],
            incidents=[
                _incident(
                    "Pages outage",
                    "https://stspg.io/abc123",
                    components=["Pages"],
                )
            ],
        )

        with mock.patch(
            "health_check.contrib.atlassian.httpx.AsyncClient"
        ) as mock_client:
            mock_response = mock.MagicMock()
            mock_response.json.return_value = api_response
            mock_response.raise_for_status = mock.MagicMock()

            mock_context = mock.AsyncMock()
            mock_context.__aenter__.return_value.get = mock.AsyncMock(
                return_value=mock_response
            )
            mock_client.return_value = mock_context

            check = GitHub(component="Actions")
            result = await check.get_result()
            assert result.error is None

    @pytest.mark.asyncio
    async def test_check_status__component_not_found(self):
        """Raise ServiceUnavailable when the configured component name does not exist."""
        api_response = _make_response(
            [_component("Actions"), _component("API Requests")],
        )

        with mock.patch(
            "health_check.contrib.atlassian.httpx.AsyncClient"
        ) as mock_client:
            mock_response = mock.MagicMock()
            mock_response.json.return_value = api_response
            mock_response.raise_for_status = mock.MagicMock()

            mock_context = mock.AsyncMock()
            mock_context.__aenter__.return_value.get = mock.AsyncMock(
                return_value=mock_response
            )
            mock_client.return_value = mock_context

            check = GitHub(component="Nonexistent")
            result = await check.get_result()
            assert result.error is not None
            assert isinstance(result.error, ServiceUnavailable)
            assert "Nonexistent" in str(result.error)

    @pytest.mark.asyncio
    async def test_check_status__no_component_filter(self):
        """Report all open incidents when no component filter is set."""
        api_response = _make_response(
            [
                _component("Actions", status="partial_outage"),
                _component("Pages", status="degraded_performance"),
            ],
            incidents=[
                _incident(
                    "Actions degraded performance",
                    "https://stspg.io/abc123",
                    components=["Actions"],
                ),
                _incident(
                    "Pages outage",
                    "https://stspg.io/def456",
                    components=["Pages"],
                ),
            ],
        )

        with mock.patch(
            "health_check.contrib.atlassian.httpx.AsyncClient"
        ) as mock_client:
            mock_response = mock.MagicMock()
            mock_response.json.return_value = api_response
            mock_response.raise_for_status = mock.MagicMock()

            mock_context = mock.AsyncMock()
            mock_context.__aenter__.return_value.get = mock.AsyncMock(
                return_value=mock_response
            )
            mock_client.return_value = mock_context

            check = GitHub()
            result = await check.get_result()
            assert result.error is not None
            assert "Actions degraded performance" in str(result.error)
            assert "Pages outage" in str(result.error)


class TestCloudflare:
    """Test Cloudflare platform status health check via Atlassian API."""

    @pytest.mark.asyncio
    async def test_check_status__ok(self):
        """Pass when there are no open incidents."""
        api_response = _make_response([_component("CDN")])

        with mock.patch(
            "health_check.contrib.atlassian.httpx.AsyncClient"
        ) as mock_client:
            mock_response = mock.MagicMock()
            mock_response.json.return_value = api_response
            mock_response.raise_for_status = mock.MagicMock()

            mock_context = mock.AsyncMock()
            mock_context.__aenter__.return_value.get = mock.AsyncMock(
                return_value=mock_response
            )
            mock_client.return_value = mock_context

            check = Cloudflare()
            result = await check.get_result()
            assert result.error is None

    def test_base_url_format(self):
        """Verify correct base URL for Cloudflare."""
        check = Cloudflare()
        assert check.base_url == "https://www.cloudflarestatus.com"


class TestPlatformSh:
    """Test Platform.sh platform status health check via Atlassian API."""

    @pytest.mark.asyncio
    async def test_check_status__ok(self):
        """Pass when there are no open incidents."""
        api_response = _make_response([_component("Hosting")])

        with mock.patch(
            "health_check.contrib.atlassian.httpx.AsyncClient"
        ) as mock_client:
            mock_response = mock.MagicMock()
            mock_response.json.return_value = api_response
            mock_response.raise_for_status = mock.MagicMock()

            mock_context = mock.AsyncMock()
            mock_context.__aenter__.return_value.get = mock.AsyncMock(
                return_value=mock_response
            )
            mock_client.return_value = mock_context

            check = PlatformSh()
            result = await check.get_result()
            assert result.error is None

    def test_base_url_format(self):
        """Verify correct base URL for Platform.sh."""
        check = PlatformSh()
        assert check.base_url == "https://status.platform.sh"


class TestDigitalOcean:
    """Test DigitalOcean platform status health check via Atlassian API."""

    @pytest.mark.asyncio
    async def test_check_status__ok(self):
        """Pass when there are no open incidents."""
        api_response = _make_response([_component("Droplets")])

        with mock.patch(
            "health_check.contrib.atlassian.httpx.AsyncClient"
        ) as mock_client:
            mock_response = mock.MagicMock()
            mock_response.json.return_value = api_response
            mock_response.raise_for_status = mock.MagicMock()

            mock_context = mock.AsyncMock()
            mock_context.__aenter__.return_value.get = mock.AsyncMock(
                return_value=mock_response
            )
            mock_client.return_value = mock_context

            check = DigitalOcean()
            result = await check.get_result()
            assert result.error is None

    def test_base_url_format(self):
        """Verify correct base URL for DigitalOcean."""
        check = DigitalOcean()
        assert check.base_url == "https://status.digitalocean.com"


class TestRender:
    """Test Render platform status health check via Atlassian API."""

    @pytest.mark.asyncio
    async def test_check_status__ok(self):
        """Pass when there are no open incidents."""
        api_response = _make_response([_component("Web Services")])

        with mock.patch(
            "health_check.contrib.atlassian.httpx.AsyncClient"
        ) as mock_client:
            mock_response = mock.MagicMock()
            mock_response.json.return_value = api_response
            mock_response.raise_for_status = mock.MagicMock()

            mock_context = mock.AsyncMock()
            mock_context.__aenter__.return_value.get = mock.AsyncMock(
                return_value=mock_response
            )
            mock_client.return_value = mock_context

            check = Render()
            result = await check.get_result()
            assert result.error is None

    def test_base_url_format(self):
        """Verify correct base URL for Render."""
        check = Render()
        assert check.base_url == "https://status.render.com"


class TestSentry:
    """Test Sentry platform status health check via Atlassian API."""

    @pytest.mark.asyncio
    async def test_check_status__ok(self):
        """Pass when there are no open incidents."""
        api_response = _make_response([_component("Error Tracking")])

        with mock.patch(
            "health_check.contrib.atlassian.httpx.AsyncClient"
        ) as mock_client:
            mock_response = mock.MagicMock()
            mock_response.json.return_value = api_response
            mock_response.raise_for_status = mock.MagicMock()

            mock_context = mock.AsyncMock()
            mock_context.__aenter__.return_value.get = mock.AsyncMock(
                return_value=mock_response
            )
            mock_client.return_value = mock_context

            check = Sentry()
            result = await check.get_result()
            assert result.error is None

    def test_base_url_format(self):
        """Verify correct base URL for Sentry."""
        check = Sentry()
        assert check.base_url == "https://status.sentry.io"


class TestVercel:
    """Test Vercel platform status health check via Atlassian API."""

    @pytest.mark.asyncio
    async def test_check_status__ok(self):
        """Pass when there are no open incidents."""
        api_response = _make_response([_component("Deployments")])

        with mock.patch(
            "health_check.contrib.atlassian.httpx.AsyncClient"
        ) as mock_client:
            mock_response = mock.MagicMock()
            mock_response.json.return_value = api_response
            mock_response.raise_for_status = mock.MagicMock()

            mock_context = mock.AsyncMock()
            mock_context.__aenter__.return_value.get = mock.AsyncMock(
                return_value=mock_response
            )
            mock_client.return_value = mock_context

            check = Vercel()
            result = await check.get_result()
            assert result.error is None

    def test_base_url_format(self):
        """Verify correct base URL for Vercel."""
        check = Vercel()
        assert check.base_url == "https://www.vercel-status.com"
