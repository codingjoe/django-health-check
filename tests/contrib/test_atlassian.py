import datetime
from unittest import mock

import pytest

pytest.importorskip("httpx")

from health_check.contrib.atlassian import (
    DigitalOcean,
    FlyIo,
    PlatformSh,
    Render,
    Vercel,
)
from health_check.exceptions import ServiceUnavailable, ServiceWarning


class TestFlyIo:
    """Test Fly.io platform status health check via Atlassian API."""

    @pytest.mark.asyncio
    async def test_check_status__ok(self):
        """Pass when no unresolved incidents are found."""
        api_response = {"page": {"id": "test"}, "incidents": []}

        with mock.patch("health_check.contrib.rss.httpx.AsyncClient") as mock_client:
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
        """Raise ServiceWarning when recent incidents are found."""
        api_response = {
            "page": {"id": "test"},
            "incidents": [
                {
                    "name": "Database connectivity issues",
                    "created_at": "2024-01-01T00:00:00Z",
                    "status": "identified",
                }
            ],
        }

        with mock.patch("health_check.contrib.rss.httpx.AsyncClient") as mock_client:
            mock_response = mock.MagicMock()
            mock_response.json.return_value = api_response
            mock_response.raise_for_status = mock.MagicMock()

            mock_context = mock.AsyncMock()
            mock_context.__aenter__.return_value.get = mock.AsyncMock(
                return_value=mock_response
            )
            mock_client.return_value = mock_context

            mock_now = datetime.datetime(
                2024, 1, 1, 1, 0, 0, tzinfo=datetime.timezone.utc
            )
            with mock.patch(
                "health_check.contrib.rss.datetime", wraps=datetime
            ) as mock_datetime:
                mock_datetime.datetime = mock.Mock(wraps=datetime.datetime)
                mock_datetime.datetime.now = mock.Mock(return_value=mock_now)

                check = FlyIo()
                result = await check.get_result()
                assert result.error is not None
                assert isinstance(result.error, ServiceWarning)
                assert "Database connectivity issues" in str(result.error)

    @pytest.mark.asyncio
    async def test_check_status__filter_old_incidents(self):
        """Filter out incidents older than max_age."""
        api_response = {
            "page": {"id": "test"},
            "incidents": [
                {
                    "name": "Old incident",
                    "created_at": "2024-01-01T00:00:00Z",
                    "status": "identified",
                }
            ],
        }

        with mock.patch("health_check.contrib.rss.httpx.AsyncClient") as mock_client:
            mock_response = mock.MagicMock()
            mock_response.json.return_value = api_response
            mock_response.raise_for_status = mock.MagicMock()

            mock_context = mock.AsyncMock()
            mock_context.__aenter__.return_value.get = mock.AsyncMock(
                return_value=mock_response
            )
            mock_client.return_value = mock_context

            mock_now = datetime.datetime(
                2024, 1, 3, 1, 0, 0, tzinfo=datetime.timezone.utc
            )
            with mock.patch(
                "health_check.contrib.rss.datetime", wraps=datetime
            ) as mock_datetime:
                mock_datetime.datetime = mock.Mock(wraps=datetime.datetime)
                mock_datetime.datetime.now = mock.Mock(return_value=mock_now)

                check = FlyIo()
                result = await check.get_result()
                assert result.error is None

    @pytest.mark.asyncio
    async def test_check_status__http_error(self):
        """Raise ServiceUnavailable on HTTP error."""
        import httpx

        with mock.patch("health_check.contrib.rss.httpx.AsyncClient") as mock_client:
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
        with mock.patch("health_check.contrib.rss.httpx.AsyncClient") as mock_client:
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


class TestPlatformSh:
    """Test Platform.sh platform status health check via Atlassian API."""

    @pytest.mark.asyncio
    async def test_check_status__ok(self):
        """Pass when no unresolved incidents are found."""
        api_response = {"page": {"id": "test"}, "incidents": []}

        with mock.patch("health_check.contrib.rss.httpx.AsyncClient") as mock_client:
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

        with mock.patch("health_check.contrib.rss.httpx.AsyncClient") as mock_client:
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

        with mock.patch("health_check.contrib.rss.httpx.AsyncClient") as mock_client:
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


class TestVercel:
    """Test Vercel platform status health check via Atlassian API."""

    @pytest.mark.asyncio
    async def test_check_status__ok(self):
        """Pass when no unresolved incidents are found."""
        api_response = {"page": {"id": "test"}, "incidents": []}

        with mock.patch("health_check.contrib.rss.httpx.AsyncClient") as mock_client:
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
