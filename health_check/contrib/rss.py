"""RSS/Atom feed health checks for cloud provider status pages."""

import dataclasses
import datetime
import logging
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from typing import Callable

from health_check.base import HealthCheck
from health_check.exceptions import ServiceUnavailable, ServiceWarning

logger = logging.getLogger(__name__)


@dataclasses.dataclass
class RSSFeed(HealthCheck):
    """
    Check service status by parsing an RSS or Atom feed.

    Args:
        feed_url: The URL of the RSS/Atom feed to check.
        timeout: Timeout duration for the HTTP request.
        max_age: Maximum age for incidents to be considered current.
        is_incident: Custom function to determine if an entry is an incident.

    """

    feed_url: str = dataclasses.field(default="", repr=False)
    timeout: datetime.timedelta = dataclasses.field(
        default=datetime.timedelta(seconds=10), repr=False
    )
    max_age: datetime.timedelta = dataclasses.field(
        default=datetime.timedelta(days=1), repr=False
    )
    is_incident: Callable[[ET.Element], bool] = dataclasses.field(
        default=lambda _: False, repr=False
    )

    def check_status(self):
        """Check the RSS/Atom feed for incidents."""
        logger.debug("Fetching RSS feed from %s", self.feed_url)

        try:
            request = urllib.request.Request(
                self.feed_url,
                headers={"User-Agent": "django-health-check"},
            )
            with urllib.request.urlopen(
                request, timeout=self.timeout.total_seconds()
            ) as response:
                content = response.read()
        except urllib.error.HTTPError as e:
            raise ServiceUnavailable(
                f"HTTP error {e.code} fetching RSS feed"
            ) from e
        except urllib.error.URLError as e:
            raise ServiceUnavailable(f"Failed to fetch RSS feed: {e.reason}") from e
        except TimeoutError as e:
            raise ServiceUnavailable("RSS feed request timed out") from e
        except BaseException as e:
            raise ServiceUnavailable("Unknown error fetching RSS feed") from e

        try:
            root = ET.fromstring(content)
        except ET.ParseError as e:
            raise ServiceUnavailable("Failed to parse RSS feed") from e

        entries = self._extract_entries(root)
        incidents = [entry for entry in entries if self._is_recent_incident(entry)]

        if incidents:
            incident_titles = [self._extract_title(entry) for entry in incidents]
            raise ServiceWarning(
                f"Found {len(incidents)} recent incident(s): {', '.join(incident_titles)}"
            )

        logger.debug("No recent incidents found in RSS feed")

    def _extract_entries(self, root):
        """Extract entries from RSS or Atom feed."""
        # Atom namespace
        atom_ns = {"atom": "http://www.w3.org/2005/Atom"}

        # Try Atom format first
        entries = root.findall("atom:entry", atom_ns)
        if entries:
            return entries

        # Try RSS 2.0 format
        entries = root.findall(".//item")
        if entries:
            return entries

        # Try RSS 1.0 format
        rss10_ns = {"rss": "http://purl.org/rss/1.0/"}
        entries = root.findall("rss:item", rss10_ns)
        return entries

    def _is_recent_incident(self, entry):
        """Check if entry is a recent incident."""
        if not self.is_incident(entry):
            return False

        published_at = self._extract_date(entry)
        if not published_at:
            return True

        cutoff = datetime.datetime.now(tz=datetime.timezone.utc) - self.max_age
        return published_at > cutoff

    def _extract_date(self, entry):
        """Extract publication date from entry."""
        # Atom format
        atom_ns = {"atom": "http://www.w3.org/2005/Atom"}
        published = entry.find("atom:published", atom_ns)
        updated = entry.find("atom:updated", atom_ns)

        date_text = None
        if published is not None and published.text:
            date_text = published.text
        elif updated is not None and updated.text:
            date_text = updated.text

        # RSS format
        if not date_text:
            pubDate = entry.find("pubDate")
            if pubDate is not None and pubDate.text:
                date_text = pubDate.text

        if not date_text:
            return None

        try:
            return datetime.datetime.fromisoformat(
                date_text.replace("Z", "+00:00")
            )
        except ValueError:
            return None

    def _extract_title(self, entry):
        """Extract title from entry."""
        # Atom format
        atom_ns = {"atom": "http://www.w3.org/2005/Atom"}
        title = entry.find("atom:title", atom_ns)
        if title is not None and title.text:
            return title.text

        # RSS format
        title = entry.find("title")
        if title is not None and title.text:
            return title.text

        return "Untitled incident"


@dataclasses.dataclass
class GoogleCloudStatus(RSSFeed):
    """
    Check Google Cloud Platform service status.

    Args:
        service_name: Optional service name to filter incidents.
                     If not specified, checks all services.

    """

    service_name: str | None = None

    def __post_init__(self):
        """Initialize feed URL and incident detector."""
        self.feed_url = "https://status.cloud.google.com/en/feed.atom"
        self.is_incident = self._detect_google_incident

    def _detect_google_incident(self, entry):
        """Detect if entry is an incident for Google Cloud."""
        title = self._extract_title(entry)
        title_lower = title.lower()

        # Filter by service if specified
        if self.service_name and self.service_name.lower() not in title_lower:
            return False

        # Check for incident keywords
        incident_keywords = ["outage", "disruption", "incident", "issue"]
        return any(keyword in title_lower for keyword in incident_keywords)


@dataclasses.dataclass
class AWSServiceStatus(RSSFeed):
    """
    Check AWS service status for a specific region and service.

    Args:
        service: AWS service name (e.g., 'ec2', 's3', 'rds').
        region: AWS region code (e.g., 'us-east-1', 'eu-west-1').

    """

    service: str = ""
    region: str = ""

    def __post_init__(self):
        """Initialize feed URL and incident detector."""
        if not self.service or not self.region:
            raise ValueError("Both 'service' and 'region' are required")
        self.feed_url = (
            f"https://status.aws.amazon.com/rss/{self.service}-{self.region}.rss"
        )
        self.is_incident = self._detect_aws_incident

    def _detect_aws_incident(self, entry):
        """Detect if entry is an incident for AWS."""
        title = self._extract_title(entry)
        title_lower = title.lower()

        # AWS marks resolved incidents differently
        resolved_keywords = ["resolved", "resolved:"]
        if any(keyword in title_lower for keyword in resolved_keywords):
            return False

        # Any other entry is considered an active incident
        return True


@dataclasses.dataclass
class AzureStatus(RSSFeed):
    """
    Check Microsoft Azure service status.

    Args:
        service_name: Optional service name to filter incidents.
                     If not specified, checks all services.

    """

    service_name: str | None = None

    def __post_init__(self):
        """Initialize feed URL and incident detector."""
        self.feed_url = "https://rssfeed.azure.status.microsoft/en-us/status/feed/"
        self.is_incident = self._detect_azure_incident

    def _detect_azure_incident(self, entry):
        """Detect if entry is an incident for Azure."""
        title = self._extract_title(entry)
        title_lower = title.lower()

        # Filter by service if specified
        if self.service_name and self.service_name.lower() not in title_lower:
            return False

        # Check for incident keywords
        incident_keywords = ["outage", "degradation", "incident", "issue", "down"]
        return any(keyword in title_lower for keyword in incident_keywords)
