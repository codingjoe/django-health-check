"""Tests for RSS/Atom feed health checks."""

import contextlib
import dataclasses
import datetime
from unittest import mock

import pytest

from health_check.contrib.rss import (
    AWSServiceStatus,
    AzureStatus,
    GoogleCloudStatus,
    RSSFeed,
)
from health_check.exceptions import ServiceUnavailable, ServiceWarning


class TestRSSFeed:
    """Test RSS feed health check."""

    def test_check_status__success_no_incidents(self):
        """Parse RSS feed successfully when no incidents found."""
        rss_content = b"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>Service Status</title>
    <item>
      <title>All systems operational</title>
      <pubDate>2024-01-01T00:00:00Z</pubDate>
    </item>
  </channel>
</rss>"""

        with mock.patch("urllib.request.urlopen") as mock_urlopen:
            mock_response = mock.MagicMock()
            mock_response.read.return_value = rss_content
            mock_response.__enter__.return_value = mock_response
            mock_urlopen.return_value = mock_response

            @dataclasses.dataclass
            class TestFeed(RSSFeed):
                feed_url: str = dataclasses.field(
                    default="https://example.com/status.rss", init=False
                )

                def is_incident(self, entry):
                    return False

            check = TestFeed()
            check.check_status()
            assert check.errors == []

    def test_check_status__atom_feed_no_incidents(self):
        """Parse Atom feed successfully when no incidents found."""
        atom_content = b"""<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <title>Service Status</title>
  <entry>
    <title>All systems operational</title>
    <published>2024-01-01T00:00:00Z</published>
  </entry>
</feed>"""

        with mock.patch("urllib.request.urlopen") as mock_urlopen:
            mock_response = mock.MagicMock()
            mock_response.read.return_value = atom_content
            mock_response.__enter__.return_value = mock_response
            mock_urlopen.return_value = mock_response

            @dataclasses.dataclass
            class TestFeed(RSSFeed):
                feed_url: str = dataclasses.field(
                    default="https://example.com/status.atom", init=False
                )

                def is_incident(self, entry):
                    return False

            check = TestFeed()
            check.check_status()
            assert check.errors == []

    def test_check_status__incident_found(self):
        """Raise ServiceWarning when incident is found."""
        rss_content = b"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <item>
      <title>Service outage detected</title>
      <pubDate>2024-01-01T00:00:00Z</pubDate>
    </item>
  </channel>
</rss>"""

        with mock.patch("urllib.request.urlopen") as mock_urlopen:
            mock_response = mock.MagicMock()
            mock_response.read.return_value = rss_content
            mock_response.__enter__.return_value = mock_response
            mock_urlopen.return_value = mock_response

            # Mock datetime.now to make the incident recent
            mock_now = datetime.datetime(
                2024, 1, 1, 1, 0, 0, tzinfo=datetime.timezone.utc
            )
            with mock.patch("health_check.contrib.rss.datetime") as mock_datetime:
                mock_datetime.datetime.now.return_value = mock_now
                mock_datetime.datetime.fromisoformat = datetime.datetime.fromisoformat
                mock_datetime.timezone = datetime.timezone

                @dataclasses.dataclass
                class TestFeed(RSSFeed):
                    feed_url: str = dataclasses.field(
                        default="https://example.com/status.rss", init=False
                    )

                    def is_incident(self, entry):
                        return True

                check = TestFeed()

                with pytest.raises(ServiceWarning) as exc_info:
                    check.check_status()

                assert "1 recent incident(s)" in str(exc_info.value)
                assert "Service outage detected" in str(exc_info.value)

    def test_check_status__old_incident_ignored(self):
        """Ignore incidents older than max_age."""
        rss_content = b"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <item>
      <title>Old service outage</title>
      <pubDate>2024-01-01T00:00:00Z</pubDate>
    </item>
  </channel>
</rss>"""

        with mock.patch("urllib.request.urlopen") as mock_urlopen:
            mock_response = mock.MagicMock()
            mock_response.read.return_value = rss_content
            mock_response.__enter__.return_value = mock_response
            mock_urlopen.return_value = mock_response

            # Mock datetime.now to make the incident old
            mock_now = datetime.datetime(
                2024, 1, 10, 0, 0, 0, tzinfo=datetime.timezone.utc
            )
            with mock.patch("health_check.contrib.rss.datetime") as mock_datetime:
                mock_datetime.datetime.now.return_value = mock_now
                mock_datetime.datetime.fromisoformat = datetime.datetime.fromisoformat
                mock_datetime.timezone = datetime.timezone

                @dataclasses.dataclass
                class TestFeed(RSSFeed):
                    feed_url: str = dataclasses.field(
                        default="https://example.com/status.rss", init=False
                    )

                    def is_incident(self, entry):
                        return True

                check = TestFeed(max_age=datetime.timedelta(days=1))
                check.check_status()
                assert check.errors == []

    def test_check_status__http_error(self):
        """Raise ServiceUnavailable when HTTP error occurs."""
        from urllib.error import HTTPError

        with mock.patch("urllib.request.urlopen") as mock_urlopen:
            mock_urlopen.side_effect = HTTPError(
                "https://example.com/status.rss", 404, "Not Found", {}, None
            )

            check = RSSFeed(feed_url="https://example.com/status.rss")
            with pytest.raises(ServiceUnavailable) as exc_info:
                check.check_status()

            assert "HTTP error 404" in str(exc_info.value)

    def test_check_status__url_error(self):
        """Raise ServiceUnavailable when URL error occurs."""
        from urllib.error import URLError

        with mock.patch("urllib.request.urlopen") as mock_urlopen:
            mock_urlopen.side_effect = URLError("Connection refused")

            check = RSSFeed(feed_url="https://example.com/status.rss")
            with pytest.raises(ServiceUnavailable) as exc_info:
                check.check_status()

            assert "Failed to fetch RSS feed" in str(exc_info.value)

    def test_check_status__timeout(self):
        """Raise ServiceUnavailable when request times out."""
        with mock.patch("urllib.request.urlopen") as mock_urlopen:
            mock_urlopen.side_effect = TimeoutError("Connection timed out")

            check = RSSFeed(feed_url="https://example.com/status.rss")
            with pytest.raises(ServiceUnavailable) as exc_info:
                check.check_status()

            assert "timed out" in str(exc_info.value)

    def test_check_status__parse_error(self):
        """Raise ServiceUnavailable when XML parsing fails."""
        invalid_content = b"not valid xml"

        with mock.patch("urllib.request.urlopen") as mock_urlopen:
            mock_response = mock.MagicMock()
            mock_response.read.return_value = invalid_content
            mock_response.__enter__.return_value = mock_response
            mock_urlopen.return_value = mock_response

            check = RSSFeed(feed_url="https://example.com/status.rss")
            with pytest.raises(ServiceUnavailable) as exc_info:
                check.check_status()

            assert "Failed to parse RSS feed" in str(exc_info.value)

    def test_check_status__general_exception(self):
        """Raise ServiceUnavailable for unexpected exceptions."""
        with mock.patch("urllib.request.urlopen") as mock_urlopen:
            mock_urlopen.side_effect = RuntimeError("Unexpected error")

            check = RSSFeed(feed_url="https://example.com/status.rss")
            with pytest.raises(ServiceUnavailable) as exc_info:
                check.check_status()

            assert "Unknown error fetching RSS feed" in str(exc_info.value)

    def test_extract_entries__rss10_format(self):
        """Parse RSS 1.0 format feed."""
        rss10_content = b"""<?xml version="1.0" encoding="UTF-8"?>
<rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#"
         xmlns="http://purl.org/rss/1.0/">
  <item>
    <title>Test item</title>
  </item>
</rdf:RDF>"""

        with mock.patch("urllib.request.urlopen") as mock_urlopen:
            mock_response = mock.MagicMock()
            mock_response.read.return_value = rss10_content
            mock_response.__enter__.return_value = mock_response
            mock_urlopen.return_value = mock_response

            @dataclasses.dataclass
            class TestFeed(RSSFeed):
                feed_url: str = dataclasses.field(
                    default="https://example.com/status.rss", init=False
                )

            check = TestFeed()
            check.check_status()
            assert check.errors == []

    def test_extract_date__invalid_format(self):
        """Handle invalid date format gracefully."""
        rss_content = b"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <item>
      <title>Incident</title>
      <pubDate>not a valid date</pubDate>
    </item>
  </channel>
</rss>"""

        with mock.patch("urllib.request.urlopen") as mock_urlopen:
            mock_response = mock.MagicMock()
            mock_response.read.return_value = rss_content
            mock_response.__enter__.return_value = mock_response
            mock_urlopen.return_value = mock_response

            @dataclasses.dataclass
            class TestFeed(RSSFeed):
                feed_url: str = dataclasses.field(
                    default="https://example.com/status.rss", init=False
                )

                def is_incident(self, entry):
                    return True

            check = TestFeed()
            # Should treat as recent incident when date parsing fails
            with pytest.raises(ServiceWarning):
                check.check_status()

    def test_extract_date__no_date(self):
        """Handle entries without date."""
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

            @dataclasses.dataclass
            class TestFeed(RSSFeed):
                feed_url: str = dataclasses.field(
                    default="https://example.com/status.rss", init=False
                )

                def is_incident(self, entry):
                    return True

            check = TestFeed()
            # Should treat as recent incident when no date found
            with pytest.raises(ServiceWarning):
                check.check_status()

    def test_extract_title__no_title(self):
        """Handle entries without title."""
        rss_content = b"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <item>
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

                @dataclasses.dataclass
                class TestFeed(RSSFeed):
                    feed_url: str = dataclasses.field(
                        default="https://example.com/status.rss", init=False
                    )

                    def is_incident(self, entry):
                        return True

                check = TestFeed()
                with pytest.raises(ServiceWarning) as exc_info:
                    check.check_status()

                assert "Untitled incident" in str(exc_info.value)

    def test_is_incident__default_implementation(self):
        """Default is_incident returns False."""
        rss_content = b"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <item>
      <title>Any incident</title>
      <pubDate>2024-01-01T00:00:00Z</pubDate>
    </item>
  </channel>
</rss>"""

        with mock.patch("urllib.request.urlopen") as mock_urlopen:
            mock_response = mock.MagicMock()
            mock_response.read.return_value = rss_content
            mock_response.__enter__.return_value = mock_response
            mock_urlopen.return_value = mock_response

            # Using base class without overriding is_incident
            check = RSSFeed(feed_url="https://example.com/status.rss")
            check.check_status()
            assert check.errors == []


class TestGoogleCloudStatus:
    """Test Google Cloud Platform status health check."""

    def test_check_status__no_incidents(self):
        """Parse Google Cloud status feed with no incidents."""
        atom_content = b"""<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <entry>
    <title>All services operational</title>
    <published>2024-01-01T00:00:00Z</published>
  </entry>
</feed>"""

        with mock.patch("urllib.request.urlopen") as mock_urlopen:
            mock_response = mock.MagicMock()
            mock_response.read.return_value = atom_content
            mock_response.__enter__.return_value = mock_response
            mock_urlopen.return_value = mock_response

            check = GoogleCloudStatus()
            check.check_status()
            assert check.errors == []

    def test_check_status__detects_outage(self):
        """Detect Google Cloud outage incident."""
        atom_content = b"""<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <entry>
    <title>Compute Engine outage in us-central1</title>
    <published>2024-01-01T00:00:00Z</published>
  </entry>
</feed>"""

        with mock.patch("urllib.request.urlopen") as mock_urlopen:
            mock_response = mock.MagicMock()
            mock_response.read.return_value = atom_content
            mock_response.__enter__.return_value = mock_response
            mock_urlopen.return_value = mock_response

            mock_now = datetime.datetime(
                2024, 1, 1, 1, 0, 0, tzinfo=datetime.timezone.utc
            )
            with mock.patch("health_check.contrib.rss.datetime") as mock_datetime:
                mock_datetime.datetime.now.return_value = mock_now
                mock_datetime.datetime.fromisoformat = datetime.datetime.fromisoformat
                mock_datetime.timezone = datetime.timezone

                check = GoogleCloudStatus()
                with pytest.raises(ServiceWarning) as exc_info:
                    check.check_status()

                assert "Compute Engine outage" in str(exc_info.value)

    def test_check_status__filters_by_service(self):
        """Filter incidents by service name."""
        atom_content = b"""<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <entry>
    <title>Cloud Storage disruption</title>
    <published>2024-01-01T00:00:00Z</published>
  </entry>
  <entry>
    <title>Compute Engine incident</title>
    <published>2024-01-01T00:00:00Z</published>
  </entry>
</feed>"""

        with mock.patch("urllib.request.urlopen") as mock_urlopen:
            mock_response = mock.MagicMock()
            mock_response.read.return_value = atom_content
            mock_response.__enter__.return_value = mock_response
            mock_urlopen.return_value = mock_response

            mock_now = datetime.datetime(
                2024, 1, 1, 1, 0, 0, tzinfo=datetime.timezone.utc
            )
            with mock.patch("health_check.contrib.rss.datetime") as mock_datetime:
                mock_datetime.datetime.now.return_value = mock_now
                mock_datetime.datetime.fromisoformat = datetime.datetime.fromisoformat
                mock_datetime.timezone = datetime.timezone

                check = GoogleCloudStatus(service_name="Cloud Storage")
                with pytest.raises(ServiceWarning) as exc_info:
                    check.check_status()

                assert "Cloud Storage" in str(exc_info.value)
                assert "Compute Engine" not in str(exc_info.value)

    @pytest.mark.integration
    def test_check_status__live_endpoint(self):
        """Fetch and parse live Google Cloud status feed."""
        check = GoogleCloudStatus()
        with contextlib.suppress(ServiceWarning, ServiceUnavailable):
            # Incidents may be present; network may not be available in test env
            check.check_status()

    @pytest.mark.integration
    def test_check_status__live_endpoint_with_service_filter(self):
        """Fetch and parse live Google Cloud status feed with service filter."""
        check = GoogleCloudStatus(service_name="Compute Engine")
        with contextlib.suppress(ServiceWarning, ServiceUnavailable):
            # Incidents may be present; network may not be available in test env
            check.check_status()


class TestAWSServiceStatus:
    """Test AWS service status health check."""

    def test_check_status__no_incidents(self):
        """Parse AWS status feed with no incidents."""
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

            # Normal operation message should not trigger incident
            check = AWSServiceStatus(region="us-east-1", service="ec2")
            check.check_status()
            assert check.errors == []

    def test_check_status__detects_incident(self):
        """Detect AWS service incident."""
        rss_content = b"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <item>
      <title>Increased API Error Rates</title>
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

                # Error in title should trigger incident
                check = AWSServiceStatus(region="us-east-1", service="ec2")
                with pytest.raises(ServiceWarning) as exc_info:
                    check.check_status()

                assert "Increased API Error Rates" in str(exc_info.value)

    def test_check_status__ignores_resolved(self):
        """Ignore resolved AWS incidents."""
        rss_content = b"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
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

            # Resolved incidents should not trigger warning
            check = AWSServiceStatus(region="us-east-1", service="ec2")
            check.check_status()
            assert check.errors == []

    def test_feed_url_format(self):
        """Verify correct feed URL format for AWS."""
        check = AWSServiceStatus(region="eu-west-1", service="s3")
        assert check.feed_url == "https://status.aws.amazon.com/rss/s3-eu-west-1.rss"

    def test_init__missing_region(self):
        """Raise ValueError when region is missing."""
        with pytest.raises(ValueError) as exc_info:
            AWSServiceStatus(region="", service="s3")

        assert "Both 'region' and 'service' are required" in str(exc_info.value)

    def test_init__missing_service(self):
        """Raise ValueError when service is missing."""
        with pytest.raises(ValueError) as exc_info:
            AWSServiceStatus(region="us-east-1", service="")

        assert "Both 'region' and 'service' are required" in str(exc_info.value)

    @pytest.mark.integration
    def test_check_status__live_endpoint(self):
        """Fetch and parse live AWS status feed."""
        check = AWSServiceStatus(region="us-east-1", service="ec2")
        with contextlib.suppress(ServiceWarning, ServiceUnavailable):
            # Incidents may be present; network may not be available in test env
            check.check_status()


class TestAzureStatus:
    """Test Microsoft Azure status health check."""

    def test_check_status__no_incidents(self):
        """Parse Azure status feed with no incidents."""
        rss_content = b"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <item>
      <title>All services healthy</title>
      <pubDate>2024-01-01T00:00:00Z</pubDate>
    </item>
  </channel>
</rss>"""

        with mock.patch("urllib.request.urlopen") as mock_urlopen:
            mock_response = mock.MagicMock()
            mock_response.read.return_value = rss_content
            mock_response.__enter__.return_value = mock_response
            mock_urlopen.return_value = mock_response

            check = AzureStatus()
            check.check_status()
            assert check.errors == []

    def test_check_status__detects_degradation(self):
        """Detect Azure service degradation."""
        rss_content = b"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <item>
      <title>Azure Storage degradation in West US</title>
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

                check = AzureStatus()
                with pytest.raises(ServiceWarning) as exc_info:
                    check.check_status()

                assert "Azure Storage degradation" in str(exc_info.value)

    def test_check_status__filters_by_service(self):
        """Filter incidents by service name."""
        rss_content = b"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <item>
      <title>Virtual Machines outage</title>
      <pubDate>2024-01-01T00:00:00Z</pubDate>
    </item>
    <item>
      <title>Azure SQL Database issue</title>
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

                check = AzureStatus(service_name="Virtual Machines")
                with pytest.raises(ServiceWarning) as exc_info:
                    check.check_status()

                assert "Virtual Machines" in str(exc_info.value)
                assert "SQL Database" not in str(exc_info.value)

    @pytest.mark.integration
    def test_check_status__live_endpoint(self):
        """Fetch and parse live Azure status feed."""
        check = AzureStatus()
        with contextlib.suppress(ServiceWarning, ServiceUnavailable):
            # Incidents may be present; network may not be available in test env
            check.check_status()

    @pytest.mark.integration
    def test_check_status__live_endpoint_with_service_filter(self):
        """Fetch and parse live Azure status feed with service filter."""
        check = AzureStatus(service_name="Virtual Machines")
        with contextlib.suppress(ServiceWarning, ServiceUnavailable):
            # Incidents may be present; network may not be available in test env
            check.check_status()
