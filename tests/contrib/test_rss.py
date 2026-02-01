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
      <pubDate>2024-01-01T00:00:00Z</pubDate>
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
            with mock.patch("health_check.contrib.rss.datetime") as mock_datetime:
                mock_datetime.datetime.now.return_value = mock_now
                mock_datetime.datetime.fromisoformat = datetime.datetime.fromisoformat
                mock_datetime.timezone = datetime.timezone

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
      <pubDate>2024-01-01T00:00:00Z</pubDate>
    </item>
    <item>
      <title>Resolved: Service disruption</title>
      <pubDate>2024-01-01T00:00:00Z</pubDate>
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
            with mock.patch("health_check.contrib.rss.datetime") as mock_datetime:
                mock_datetime.datetime.now.return_value = mock_now
                mock_datetime.datetime.fromisoformat = datetime.datetime.fromisoformat
                mock_datetime.timezone = datetime.timezone

                check = AWS(region="us-east-1", service="ec2")
                with pytest.raises(ServiceWarning) as exc_info:
                    check.check_status()

                assert "2 recent incident(s)" in str(exc_info.value)

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
        check = AWS(region="us-east-1", service="ec2")
        with contextlib.suppress(ServiceWarning, ServiceUnavailable):
            # Incidents may be present; network may not be available in test env
            check.check_status()
