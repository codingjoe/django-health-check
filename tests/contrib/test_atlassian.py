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


class TestFlyIo:
    """Test Fly.io platform status health check via Atlassian API."""

    @pytest.mark.asyncio
    async def test_check_status__ok(self):
        """Pass when no unresolved incidents are found."""
        api_response = {"page": {"id": "test"}, "incidents": []}

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

    @pytest.mark.asyncio
    async def test_check_status__raise_service_warning(self):
        """Raise ServiceWarning when incidents are found."""
        api_response = {
            "page": {"id": "test"},
            "incidents": [
                {
                    "name": "Database connectivity issues",
                    "shortlink": "https://stspg.io/abc123",
                }
            ],
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

            check = FlyIo()
            result = await check.get_result()
            assert result.error is not None
            assert isinstance(result.error, ServiceWarning)
            assert "Database connectivity issues" in str(result.error)
            assert "https://stspg.io/abc123" in str(result.error)

    @pytest.mark.asyncio
    async def test_check_status__multiple_incidents(self):
        """Show all unresolved incidents."""
        api_response = {
            "page": {"id": "test"},
            "incidents": [
                {
                    "name": "Database connectivity issues",
                    "shortlink": "https://stspg.io/abc123",
                },
                {
                    "name": "Network degradation",
                    "shortlink": "https://stspg.io/def456",
                },
            ],
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

            check = FlyIo()
            result = await check.get_result()
            assert result.error is not None
            assert isinstance(result.error, ServiceWarning)
            assert "Database connectivity issues" in str(result.error)
            assert "Network degradation" in str(result.error)

    @pytest.mark.asyncio
    async def test_check_status__incident_carries_source_timestamp(self):
        """StatusPageWarning carries the most recent incident created_at as its timestamp."""
        import datetime

        api_response = {
            "page": {"id": "test"},
            "incidents": [
                {
                    "name": "Older incident",
                    "shortlink": "https://stspg.io/older",
                    "created_at": "2024-01-01T00:00:00.000Z",
                },
                {
                    "name": "Newer incident",
                    "shortlink": "https://stspg.io/newer",
                    "created_at": "2024-01-01T06:00:00.000Z",
                },
            ],
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

            check = FlyIo()
            result = await check.get_result()
            assert result.error is not None
            assert isinstance(result.error, StatusPageWarning)
            expected_ts = datetime.datetime(2024, 1, 1, 6, 0, 0, tzinfo=datetime.timezone.utc)
            assert result.error.timestamp == expected_ts, (
                "StatusPageWarning should carry the most recent incident timestamp"
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

    @pytest.mark.asyncio
    async def test_check_status__ok(self):
        """Pass when no unresolved incidents are found."""
        api_response = {"page": {"id": "test"}, "incidents": []}

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

    def test_base_url_format(self):
        """Verify correct base URL for GitHub."""
        assert GitHub().base_url == "https://www.githubstatus.com"
        assert GitHub("eu").base_url == "https://eu.githubstatus.com"


class TestCloudflare:
    """Test Cloudflare platform status health check via Atlassian API."""

    @pytest.mark.asyncio
    async def test_check_status__ok(self):
        """Pass when no unresolved incidents are found."""
        api_response = {"page": {"id": "test"}, "incidents": []}

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
        """Pass when no unresolved incidents are found."""
        api_response = {"page": {"id": "test"}, "incidents": []}

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
        """Pass when no unresolved incidents are found."""
        api_response = {"page": {"id": "test"}, "incidents": []}

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
        """Pass when no unresolved incidents are found."""
        api_response = {"page": {"id": "test"}, "incidents": []}

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
        """Pass when no unresolved incidents are found."""
        api_response = {"page": {"id": "test"}, "incidents": []}

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
        assert Sentry().base_url == "https://status.sentry.io"


class TestVercel:
    """Test Vercel platform status health check via Atlassian API."""

    @pytest.mark.asyncio
    async def test_check_status__ok(self):
        """Pass when no unresolved incidents are found."""
        api_response = {"page": {"id": "test"}, "incidents": []}

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
