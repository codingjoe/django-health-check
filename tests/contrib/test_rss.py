"""Tests for cloud provider status feed health checks."""

import datetime
import logging
from unittest import mock

import pytest

pytest.importorskip("httpx")

from health_check.contrib.rss import (
    AWS,
    Azure,
    GoogleCloud,
    Heroku,
)
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
            mock_response.text = rss_content.decode("utf-8")
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
                mock_datetime.timezone = datetime.timezone
                mock_datetime.timezone = datetime.timezone
                check = AWS(region="us-east-1", service="ec2")
                result = await check.get_result()
                assert result.error is not None
                assert isinstance(result.error, ServiceWarning)
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
            mock_response.text = rss_content.decode("utf-8")
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
                mock_datetime.timezone = datetime.timezone

                check = AWS(region="us-east-1", service="ec2")
                result = await check.get_result()
                assert result.error is not None
                assert isinstance(result.error, ServiceWarning)
                assert "\n" in str(result.error)

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
            mock_response.text = rss_content.decode("utf-8")
            mock_response.raise_for_status = mock.MagicMock()

            mock_context = mock.AsyncMock()
            mock_context.__aenter__.return_value.get = mock.AsyncMock(
                return_value=mock_response
            )
            mock_client.return_value = mock_context

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
            assert "Failed to fetch feed" in str(result.error)

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
        """Feedparser handles malformed feeds gracefully with bozo flag."""
        invalid_xml = b"not valid xml"

        with mock.patch("health_check.contrib.rss.httpx.AsyncClient") as mock_client:
            mock_response = mock.MagicMock()
            mock_response.text = invalid_xml.decode("utf-8")
            mock_response.raise_for_status = mock.MagicMock()

            mock_context = mock.AsyncMock()
            mock_context.__aenter__.return_value.get = mock.AsyncMock(
                return_value=mock_response
            )
            mock_client.return_value = mock_context

            check = AWS(region="us-east-1", service="ec2")
            result = await check.get_result()
            # feedparser handles malformed feeds gracefully - no error raised
            # but it logs a warning
            assert result.error is None

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
            mock_response.text = rss_content.decode("utf-8")
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
            mock_response.text = rss_content.decode("utf-8")
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

    def test_extract_date__invalid_date_tuple_values(self, caplog):
        """Entry with invalid date tuple values is treated as recent incident."""
        check = AWS(region="us-east-1", service="ec2")

        # Create a mock entry with an invalid date_tuple (day=32)
        mock_entry = mock.MagicMock()
        mock_entry.published_parsed = (2024, 1, 32, 0, 0, 0, 0, 0, 0)

        with caplog.at_level(logging.WARNING):
            result = check._extract_date(mock_entry)
        assert result is None
        assert (
            "Failed to parse date from entry (2024, 1, 32, 0, 0, 0, 0, 0, 0) for 'htt"
            in caplog.text
        )

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
            mock_response.text = rss_content.decode("utf-8")
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
                mock_datetime.timezone = datetime.timezone

                check = AWS(region="us-east-1", service="ec2")
                result = await check.get_result()
                assert result.error is not None
                assert isinstance(result.error, ServiceWarning)
                assert "Unknown Incident" in str(result.error)

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


class TestHeroku:
    """Test Heroku platform status health check."""

    @pytest.mark.asyncio
    async def test_check_status__ok(self):
        """Pass when no recent incidents are found."""
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
            mock_response.text = rss_content.decode("utf-8")
            mock_response.raise_for_status = mock.MagicMock()

            mock_context = mock.AsyncMock()
            mock_context.__aenter__.return_value.get = mock.AsyncMock(
                return_value=mock_response
            )
            mock_client.return_value = mock_context

            check = Heroku()
            result = await check.get_result()
            assert result.error is None

    @pytest.mark.asyncio
    async def test_check_status__raise_service_warning(self):
        """Raise ServiceWarning when recent incidents are found."""
        rss_content = b"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <item>
      <title>Platform degradation</title>
      <pubDate>Mon, 01 Jan 2024 00:00:00 GMT</pubDate>
    </item>
  </channel>
</rss>"""

        with mock.patch("health_check.contrib.rss.httpx.AsyncClient") as mock_client:
            mock_response = mock.MagicMock()
            mock_response.text = rss_content.decode("utf-8")
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
                mock_datetime.timezone = datetime.timezone

                check = Heroku()
                result = await check.get_result()
                assert result.error is not None
                assert isinstance(result.error, ServiceWarning)
                assert "Platform degradation" in str(result.error)

    def test_feed_url_format(self):
        """Verify correct feed URL for Heroku."""
        check = Heroku()
        assert check.feed_url == "https://status.heroku.com/feed"


class TestAzure:
    """Test Azure platform status health check."""

    @pytest.mark.asyncio
    async def test_check_status__ok(self):
        """Pass when no recent incidents are found."""
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
            mock_response.text = rss_content.decode("utf-8")
            mock_response.raise_for_status = mock.MagicMock()

            mock_context = mock.AsyncMock()
            mock_context.__aenter__.return_value.get = mock.AsyncMock(
                return_value=mock_response
            )
            mock_client.return_value = mock_context

            check = Azure()
            result = await check.get_result()
            assert result.error is None

    @pytest.mark.asyncio
    async def test_check_status__raise_service_warning(self):
        """Raise ServiceWarning when recent incidents are found."""
        rss_content = b"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <item>
      <title>Virtual Machines outage</title>
      <pubDate>Mon, 01 Jan 2024 00:00:00 GMT</pubDate>
    </item>
  </channel>
</rss>"""

        with mock.patch("health_check.contrib.rss.httpx.AsyncClient") as mock_client:
            mock_response = mock.MagicMock()
            mock_response.text = rss_content.decode("utf-8")
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
                mock_datetime.timezone = datetime.timezone

                check = Azure()
                result = await check.get_result()
                assert result.error is not None
                assert isinstance(result.error, ServiceWarning)
                assert "Virtual Machines outage" in str(result.error)


class TestGoogleCloud:
    """Test Google Cloud platform status health check."""

    @pytest.mark.asyncio
    async def test_check_status__ok(self):
        """Pass when no recent incidents are found."""
        atom_content = b"""<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <entry>
    <title>Old incident</title>
    <published>2024-01-01T00:00:00Z</published>
  </entry>
</feed>"""

        with mock.patch("health_check.contrib.rss.httpx.AsyncClient") as mock_client:
            mock_response = mock.MagicMock()
            mock_response.text = atom_content.decode("utf-8")
            mock_response.raise_for_status = mock.MagicMock()

            mock_context = mock.AsyncMock()
            mock_context.__aenter__.return_value.get = mock.AsyncMock(
                return_value=mock_response
            )
            mock_client.return_value = mock_context

            check = GoogleCloud()
            result = await check.get_result()
            assert result.error is None

    @pytest.mark.asyncio
    async def test_check_status__raise_service_warning(self):
        """Raise ServiceWarning when recent incidents are found."""
        atom_content = b"""<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <entry>
    <title>Compute Engine disruption</title>
    <published>2024-01-01T00:00:00Z</published>
  </entry>
</feed>"""

        with mock.patch("health_check.contrib.rss.httpx.AsyncClient") as mock_client:
            mock_response = mock.MagicMock()
            mock_response.text = atom_content.decode("utf-8")
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
                mock_datetime.timezone = datetime.timezone

                check = GoogleCloud()
                result = await check.get_result()
                assert result.error is not None
                assert isinstance(result.error, ServiceWarning)
                assert "Compute Engine disruption" in str(result.error)

    @pytest.mark.asyncio
    async def test_check_status__atom_with_updated_field(self):
        """Parse Atom feed with updated field instead of published."""
        atom_content = b"""<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <entry>
    <title>Service update</title>
    <updated>2024-01-01T00:00:00Z</updated>
  </entry>
</feed>"""

        with mock.patch("health_check.contrib.rss.httpx.AsyncClient") as mock_client:
            mock_response = mock.MagicMock()
            mock_response.text = atom_content.decode("utf-8")
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
                mock_datetime.timezone = datetime.timezone

                check = GoogleCloud()
                result = await check.get_result()
                assert result.error is not None
                assert isinstance(result.error, ServiceWarning)
                assert "Service update" in str(result.error)

    @pytest.mark.asyncio
    async def test_check_status__atom_without_namespace(self):
        """Parse Atom feed without explicit namespace prefix."""
        atom_content = b"""<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <entry>
    <title>Incident</title>
    <published>2024-01-01T00:00:00Z</published>
  </entry>
</feed>"""

        with mock.patch("health_check.contrib.rss.httpx.AsyncClient") as mock_client:
            mock_response = mock.MagicMock()
            mock_response.text = atom_content.decode("utf-8")
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
                mock_datetime.timezone = datetime.timezone

                check = GoogleCloud()
                result = await check.get_result()
                assert result.error is not None
                assert isinstance(result.error, ServiceWarning)

    def test_feed_url_format(self):
        """Verify correct feed URL for Google Cloud."""
        check = GoogleCloud()
        assert check.feed_url == "https://status.cloud.google.com/en/feed.atom"

    @pytest.mark.asyncio
    async def test_check_status__atom_entry_without_namespace_prefix(self):
        """Parse Atom feed where entries don't have namespace prefix."""
        atom_content = b"""<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <entry xmlns="http://www.w3.org/2005/Atom">
    <title>Incident</title>
    <published>2024-01-01T00:00:00Z</published>
  </entry>
</feed>"""

        with mock.patch("health_check.contrib.rss.httpx.AsyncClient") as mock_client:
            mock_response = mock.MagicMock()
            mock_response.text = atom_content.decode("utf-8")
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
                mock_datetime.timezone = datetime.timezone

                check = GoogleCloud()
                result = await check.get_result()
                assert result.error is not None
                assert isinstance(result.error, ServiceWarning)

    @pytest.mark.asyncio
    async def test_check_status__atom_invalid_date_format(self):
        """Handle invalid date format in Atom feed."""
        atom_content = b"""<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <entry>
    <title>Incident with invalid date</title>
    <published>not a valid date</published>
  </entry>
</feed>"""

        with mock.patch("health_check.contrib.rss.httpx.AsyncClient") as mock_client:
            mock_response = mock.MagicMock()
            mock_response.text = atom_content.decode("utf-8")
            mock_response.raise_for_status = mock.MagicMock()

            mock_context = mock.AsyncMock()
            mock_context.__aenter__.return_value.get = mock.AsyncMock(
                return_value=mock_response
            )
            mock_client.return_value = mock_context

            check = GoogleCloud()
            result = await check.get_result()
            assert result.error is not None
            assert isinstance(result.error, ServiceWarning)
            assert "Incident with invalid date" in str(result.error)

    @pytest.mark.asyncio
    async def test_check_status__atom_title_without_namespace_prefix(self):
        """Parse Atom feed where title doesn't have namespace prefix."""
        atom_content = b"""<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <entry xmlns="http://www.w3.org/2005/Atom">
    <title xmlns="http://www.w3.org/2005/Atom">Title without prefix</title>
    <published>2024-01-01T00:00:00Z</published>
  </entry>
</feed>"""

        with mock.patch("health_check.contrib.rss.httpx.AsyncClient") as mock_client:
            mock_response = mock.MagicMock()
            mock_response.text = atom_content.decode("utf-8")
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
                mock_datetime.timezone = datetime.timezone

                check = GoogleCloud()
                result = await check.get_result()
                assert result.error is not None
                assert isinstance(result.error, ServiceWarning)
                assert "Title without prefix" in str(result.error)

    @pytest.mark.asyncio
    async def test_check_status__atom_entry_with_empty_title(self):
        """Handle Atom entry with empty title element."""
        atom_content = b"""<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <entry>
    <title></title>
    <published>2024-01-01T00:00:00Z</published>
  </entry>
</feed>"""

        with mock.patch("health_check.contrib.rss.httpx.AsyncClient") as mock_client:
            mock_response = mock.MagicMock()
            mock_response.text = atom_content.decode("utf-8")
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
                mock_datetime.timezone = datetime.timezone

                check = GoogleCloud()
                result = await check.get_result()
                assert result.error is not None
                assert isinstance(result.error, ServiceWarning)
                assert "Unknown Incident:" in str(result.error)

    @pytest.mark.asyncio
    async def test_check_status__atom_entry_without_title(self):
        """Handle Atom entry without title element."""
        atom_content = b"""<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <entry>
    <published>2024-01-01T00:00:00Z</published>
  </entry>
</feed>"""

        with mock.patch("health_check.contrib.rss.httpx.AsyncClient") as mock_client:
            mock_response = mock.MagicMock()
            mock_response.text = atom_content.decode("utf-8")
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
                mock_datetime.timezone = datetime.timezone

                check = GoogleCloud()
                result = await check.get_result()
                assert result.error is not None
                assert isinstance(result.error, ServiceWarning)
                assert "Unknown Incident:" in str(result.error)
