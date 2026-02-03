"""Tests for AWS RSS feed health check."""

import datetime
from unittest import mock

import pytest

pytest.importorskip("httpx")

from health_check.contrib.rss import AWS
from health_check.exceptions import ServiceUnavailable, ServiceWarning


class TestAWS:
    """Test AWS service status health check."""

    @pytest.mark.asyncio
    async def test_check_status__detects_any_entry_as_incident(self):
        """Any entry in AWS RSS feed is treated as an incident."""
        rss_content = b"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <item>
      <title>Service is operating normally</title>
      <pubDate>Mon, 01 Jan 2024 00:00:00 GMT</pubDate>
    </item>
  </channel>
</rss>"""

        with mock.patch("health_check.contrib.rss.httpx.AsyncClient") as mock_client:
            mock_response = mock.MagicMock()
            mock_response.content = rss_content
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
                check = AWS(region="us-east-1", service="ec2")
                result = await check.get_result()
                assert result.error is not None
                assert isinstance(result.error, ServiceWarning)
                assert "1 recent incident(s)" in str(result.error)
                assert "Service is operating normally" in str(result.error)

    @pytest.mark.asyncio
    async def test_check_status__multiple_incidents(self):
        """Multiple entries are all treated as incidents."""
        rss_content = b"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <item>
      <title>Increased API Error Rates</title>
      <pubDate>Mon, 01 Jan 2024 00:00:00 GMT</pubDate>
    </item>
    <item>
      <title>Resolved: Service disruption</title>
      <pubDate>Mon, 01 Jan 2024 00:00:00 GMT</pubDate>
    </item>
  </channel>
</rss>"""

        with mock.patch("health_check.contrib.rss.httpx.AsyncClient") as mock_client:
            mock_response = mock.MagicMock()
            mock_response.content = rss_content
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

                check = AWS(region="us-east-1", service="ec2")
                result = await check.get_result()
                assert result.error is not None
                assert isinstance(result.error, ServiceWarning)
                assert "2 recent incident(s)" in str(result.error)

    @pytest.mark.asyncio
    async def test_check_status__no_recent_incidents(self):
        """Old incidents are filtered out."""
        rss_content = b"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <item>
      <title>Old incident</title>
      <pubDate>Mon, 01 Jan 2024 00:00:00 GMT</pubDate>
    </item>
  </channel>
</rss>"""

        with mock.patch("health_check.contrib.rss.httpx.AsyncClient") as mock_client:
            mock_response = mock.MagicMock()
            mock_response.content = rss_content
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

                check = AWS(region="us-east-1", service="ec2")
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

            check = AWS(region="us-east-1", service="ec2")
            result = await check.get_result()
            assert result.error is not None
            assert isinstance(result.error, ServiceUnavailable)
            assert "HTTP error 404" in str(result.error)

    @pytest.mark.asyncio
    async def test_check_status__url_error(self):
        """Raise ServiceUnavailable on request error."""
        import httpx

        with mock.patch("health_check.contrib.rss.httpx.AsyncClient") as mock_client:
            mock_context = mock.AsyncMock()
            mock_context.__aenter__.return_value.get = mock.AsyncMock(
                side_effect=httpx.RequestError("Connection refused")
            )
            mock_client.return_value = mock_context

            check = AWS(region="us-east-1", service="ec2")
            result = await check.get_result()
            assert result.error is not None
            assert isinstance(result.error, ServiceUnavailable)
            assert "Failed to fetch RSS feed" in str(result.error)

    @pytest.mark.asyncio
    async def test_check_status__timeout_error(self):
        """Raise ServiceUnavailable on timeout."""
        import httpx

        with mock.patch("health_check.contrib.rss.httpx.AsyncClient") as mock_client:
            mock_context = mock.AsyncMock()
            mock_context.__aenter__.return_value.get = mock.AsyncMock(
                side_effect=httpx.TimeoutException("Timed out")
            )
            mock_client.return_value = mock_context

            check = AWS(region="us-east-1", service="ec2")
            result = await check.get_result()
            assert result.error is not None
            assert isinstance(result.error, ServiceUnavailable)
            assert "timed out" in str(result.error)

    @pytest.mark.asyncio
    async def test_check_status__parse_error(self):
        """Raise ServiceUnavailable on XML parse error."""
        invalid_xml = b"not valid xml"

        with mock.patch("health_check.contrib.rss.httpx.AsyncClient") as mock_client:
            mock_response = mock.MagicMock()
            mock_response.content = invalid_xml
            mock_response.raise_for_status = mock.MagicMock()

            mock_context = mock.AsyncMock()
            mock_context.__aenter__.return_value.get = mock.AsyncMock(
                return_value=mock_response
            )
            mock_client.return_value = mock_context

            check = AWS(region="us-east-1", service="ec2")
            result = await check.get_result()
            assert result.error is not None
            assert isinstance(result.error, ServiceUnavailable)
            assert "Failed to parse RSS feed" in str(result.error)

    @pytest.mark.asyncio
    async def test_extract_date__entry_without_date(self):
        """Entry without date is treated as recent incident."""
        rss_content = b"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <item>
      <title>Incident without date</title>
    </item>
  </channel>
</rss>"""

        with mock.patch("health_check.contrib.rss.httpx.AsyncClient") as mock_client:
            mock_response = mock.MagicMock()
            mock_response.content = rss_content
            mock_response.raise_for_status = mock.MagicMock()

            mock_context = mock.AsyncMock()
            mock_context.__aenter__.return_value.get = mock.AsyncMock(
                return_value=mock_response
            )
            mock_client.return_value = mock_context

            check = AWS(region="us-east-1", service="ec2")
            result = await check.get_result()
            assert result.error is not None
            assert isinstance(result.error, ServiceWarning)
            assert "Incident without date" in str(result.error)

    @pytest.mark.asyncio
    async def test_extract_date__invalid_date_format(self):
        """Entry with invalid date format is treated as recent incident."""
        rss_content = b"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <item>
      <title>Incident with bad date</title>
      <pubDate>not a valid date</pubDate>
    </item>
  </channel>
</rss>"""

        with mock.patch("health_check.contrib.rss.httpx.AsyncClient") as mock_client:
            mock_response = mock.MagicMock()
            mock_response.content = rss_content
            mock_response.raise_for_status = mock.MagicMock()

            mock_context = mock.AsyncMock()
            mock_context.__aenter__.return_value.get = mock.AsyncMock(
                return_value=mock_response
            )
            mock_client.return_value = mock_context

            check = AWS(region="us-east-1", service="ec2")
            result = await check.get_result()
            assert result.error is not None
            assert isinstance(result.error, ServiceWarning)
            assert "Incident with bad date" in str(result.error)

    @pytest.mark.asyncio
    async def test_extract_title__entry_without_title(self):
        """Entry without title shows 'Untitled incident'."""
        rss_content = b"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <item>
      <pubDate>Mon, 01 Jan 2024 00:00:00 GMT</pubDate>
    </item>
  </channel>
</rss>"""

        with mock.patch("health_check.contrib.rss.httpx.AsyncClient") as mock_client:
            mock_response = mock.MagicMock()
            mock_response.content = rss_content
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

                check = AWS(region="us-east-1", service="ec2")
                result = await check.get_result()
                assert result.error is not None
                assert isinstance(result.error, ServiceWarning)
                assert "Untitled incident" in str(result.error)

    def test_feed_url_format(self):
        """Verify correct feed URL format for AWS."""
        check = AWS(region="eu-west-1", service="s3")
        assert check.feed_url == "https://status.aws.amazon.com/rss/s3-eu-west-1.rss"

    def test_init__missing_region(self):
        """Raise TypeError when region is missing."""
        with pytest.raises(TypeError):
            AWS(service="s3")

    def test_init__missing_service(self):
        """Raise TypeError when service is missing."""
        with pytest.raises(TypeError):
            AWS(region="us-east-1")

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_check_status__live_endpoint(self):
        """Fetch and parse live AWS status feed."""
        import os

        aws_rss_feed_url = os.getenv("AWS_RSS_FEED_URL")
        if not aws_rss_feed_url:
            pytest.skip("AWS_RSS_FEED_URL not set; skipping integration test")

        check = AWS(region="us-east-1", service="ec2")
        check.feed_url = aws_rss_feed_url
        result = await check.get_result()
        # Result can be either None or ServiceWarning, both are acceptable for live endpoint
        assert result.error is None or isinstance(result.error, ServiceWarning)
