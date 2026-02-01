"""Tests for AWS RSS feed health check."""

import contextlib
import datetime
from unittest import mock

import pytest

from health_check.contrib.rss import AWS
from health_check.exceptions import ServiceUnavailable, ServiceWarning


class TestAWS:
    """Test AWS service status health check."""

    def test_check_status__detects_any_entry_as_incident(self):
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

        with mock.patch("urllib.request.urlopen") as mock_urlopen:
            mock_response = mock.MagicMock()
            mock_response.read.return_value = rss_content
            mock_response.__enter__.return_value = mock_response
            mock_urlopen.return_value = mock_response

            mock_now = datetime.datetime(
                2024, 1, 1, 1, 0, 0, tzinfo=datetime.timezone.utc
            )
            with mock.patch(
                "health_check.contrib.rss.datetime", wraps=datetime
            ) as mock_datetime:
                mock_datetime.datetime = mock.Mock(wraps=datetime.datetime)
                mock_datetime.datetime.now = mock.Mock(return_value=mock_now)
                check = AWS(region="us-east-1", service="ec2")
                with pytest.raises(ServiceWarning) as exc_info:
                    check.check_status()

                assert "1 recent incident(s)" in str(exc_info.value)
                assert "Service is operating normally" in str(exc_info.value)

    def test_check_status__multiple_incidents(self):
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

        with mock.patch("urllib.request.urlopen") as mock_urlopen:
            mock_response = mock.MagicMock()
            mock_response.read.return_value = rss_content
            mock_response.__enter__.return_value = mock_response
            mock_urlopen.return_value = mock_response

            mock_now = datetime.datetime(
                2024, 1, 1, 1, 0, 0, tzinfo=datetime.timezone.utc
            )
            with mock.patch(
                "health_check.contrib.rss.datetime", wraps=datetime
            ) as mock_datetime:
                mock_datetime.datetime = mock.Mock(wraps=datetime.datetime)
                mock_datetime.datetime.now = mock.Mock(return_value=mock_now)

                check = AWS(region="us-east-1", service="ec2")
                with pytest.raises(ServiceWarning) as exc_info:
                    check.check_status()

                assert "2 recent incident(s)" in str(exc_info.value)

    def test_check_status__no_recent_incidents(self):
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

        with mock.patch("urllib.request.urlopen") as mock_urlopen:
            mock_response = mock.MagicMock()
            mock_response.read.return_value = rss_content
            mock_response.__enter__.return_value = mock_response
            mock_urlopen.return_value = mock_response

            mock_now = datetime.datetime(
                2024, 1, 3, 1, 0, 0, tzinfo=datetime.timezone.utc
            )
            with mock.patch(
                "health_check.contrib.rss.datetime", wraps=datetime
            ) as mock_datetime:
                mock_datetime.datetime = mock.Mock(wraps=datetime.datetime)
                mock_datetime.datetime.now = mock.Mock(return_value=mock_now)

                check = AWS(region="us-east-1", service="ec2")
                check.check_status()
                assert check.errors == []

    def test_check_status__http_error(self):
        """Raise ServiceUnavailable on HTTP error."""
        with mock.patch("urllib.request.urlopen") as mock_urlopen:
            from urllib.error import HTTPError

            mock_urlopen.side_effect = HTTPError("url", 404, "Not Found", {}, None)

            check = AWS(region="us-east-1", service="ec2")
            with pytest.raises(ServiceUnavailable) as exc_info:
                check.check_status()

            assert "HTTP error 404" in str(exc_info.value)

    def test_check_status__url_error(self):
        """Raise ServiceUnavailable on URL error."""
        with mock.patch("urllib.request.urlopen") as mock_urlopen:
            from urllib.error import URLError

            mock_urlopen.side_effect = URLError("Connection refused")

            check = AWS(region="us-east-1", service="ec2")
            with pytest.raises(ServiceUnavailable) as exc_info:
                check.check_status()

            assert "Failed to fetch RSS feed" in str(exc_info.value)

    def test_check_status__timeout_error(self):
        """Raise ServiceUnavailable on timeout."""
        with mock.patch("urllib.request.urlopen") as mock_urlopen:
            mock_urlopen.side_effect = TimeoutError("Timed out")

            check = AWS(region="us-east-1", service="ec2")
            with pytest.raises(ServiceUnavailable) as exc_info:
                check.check_status()

            assert "timed out" in str(exc_info.value)

    def test_check_status__general_exception(self):
        """Raise ServiceUnavailable on general exception."""
        with mock.patch("urllib.request.urlopen") as mock_urlopen:
            mock_urlopen.side_effect = RuntimeError("Unexpected error")

            check = AWS(region="us-east-1", service="ec2")
            with pytest.raises(ServiceUnavailable) as exc_info:
                check.check_status()

            assert "Unknown error fetching RSS feed" in str(exc_info.value)

    def test_check_status__parse_error(self):
        """Raise ServiceUnavailable on XML parse error."""
        invalid_xml = b"not valid xml"

        with mock.patch("urllib.request.urlopen") as mock_urlopen:
            mock_response = mock.MagicMock()
            mock_response.read.return_value = invalid_xml
            mock_response.__enter__.return_value = mock_response
            mock_urlopen.return_value = mock_response

            check = AWS(region="us-east-1", service="ec2")
            with pytest.raises(ServiceUnavailable) as exc_info:
                check.check_status()

            assert "Failed to parse RSS feed" in str(exc_info.value)

    def test_extract_date__entry_without_date(self):
        """Entry without date is treated as recent incident."""
        rss_content = b"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <item>
      <title>Incident without date</title>
    </item>
  </channel>
</rss>"""

        with mock.patch("urllib.request.urlopen") as mock_urlopen:
            mock_response = mock.MagicMock()
            mock_response.read.return_value = rss_content
            mock_response.__enter__.return_value = mock_response
            mock_urlopen.return_value = mock_response

            check = AWS(region="us-east-1", service="ec2")
            with pytest.raises(ServiceWarning) as exc_info:
                check.check_status()

            assert "Incident without date" in str(exc_info.value)

    def test_extract_date__invalid_date_format(self):
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

        with mock.patch("urllib.request.urlopen") as mock_urlopen:
            mock_response = mock.MagicMock()
            mock_response.read.return_value = rss_content
            mock_response.__enter__.return_value = mock_response
            mock_urlopen.return_value = mock_response

            check = AWS(region="us-east-1", service="ec2")
            with pytest.raises(ServiceWarning) as exc_info:
                check.check_status()

            assert "Incident with bad date" in str(exc_info.value)

    def test_extract_date__naive_datetime_normalized_to_utc(self):
        """Entry with naive datetime (no timezone) is normalized to UTC."""
        rss_content = b"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <item>
      <title>Recent incident without timezone</title>
      <pubDate>Mon, 01 Jan 2024 00:00:00</pubDate>
    </item>
  </channel>
</rss>"""

        with mock.patch("urllib.request.urlopen") as mock_urlopen:
            mock_response = mock.MagicMock()
            mock_response.read.return_value = rss_content
            mock_response.__enter__.return_value = mock_response
            mock_urlopen.return_value = mock_response

            mock_now = datetime.datetime(
                2024, 1, 1, 1, 0, 0, tzinfo=datetime.timezone.utc
            )
            with mock.patch(
                "health_check.contrib.rss.datetime", wraps=datetime
            ) as mock_datetime:
                mock_datetime.datetime = mock.Mock(wraps=datetime.datetime)
                mock_datetime.datetime.now = mock.Mock(return_value=mock_now)

                check = AWS(region="us-east-1", service="ec2")
                with pytest.raises(ServiceWarning) as exc_info:
                    check.check_status()

                assert "Recent incident without timezone" in str(exc_info.value)

    def test_extract_title__entry_without_title(self):
        """Entry without title shows 'Untitled incident'."""
        rss_content = b"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <item>
      <pubDate>Mon, 01 Jan 2024 00:00:00 GMT</pubDate>
    </item>
  </channel>
</rss>"""

        with mock.patch("urllib.request.urlopen") as mock_urlopen:
            mock_response = mock.MagicMock()
            mock_response.read.return_value = rss_content
            mock_response.__enter__.return_value = mock_response
            mock_urlopen.return_value = mock_response

            mock_now = datetime.datetime(
                2024, 1, 1, 1, 0, 0, tzinfo=datetime.timezone.utc
            )
            with mock.patch(
                "health_check.contrib.rss.datetime", wraps=datetime
            ) as mock_datetime:
                mock_datetime.datetime = mock.Mock(wraps=datetime.datetime)
                mock_datetime.datetime.now = mock.Mock(return_value=mock_now)

                check = AWS(region="us-east-1", service="ec2")
                with pytest.raises(ServiceWarning) as exc_info:
                    check.check_status()

                assert "Untitled incident" in str(exc_info.value)

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
    def test_check_status__live_endpoint(self):
        """Fetch and parse live AWS status feed."""
        import os

        aws_rss_feed_url = os.getenv("AWS_RSS_FEED_URL")
        if not aws_rss_feed_url:
            pytest.skip("AWS_RSS_FEED_URL not set; skipping integration test")

        check = AWS(region="us-east-1", service="ec2")
        check.feed_url = aws_rss_feed_url
        with contextlib.suppress(ServiceWarning):
            check.check_status()
