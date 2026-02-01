"""RSS/Atom feed health checks for cloud provider status pages."""

import dataclasses
import datetime
import logging
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET  # noqa: S405

from health_check.base import HealthCheck
from health_check.exceptions import ServiceUnavailable, ServiceWarning

logger = logging.getLogger(__name__)


@dataclasses.dataclass
class RSSFeed(HealthCheck):
    """
    Check service status by parsing an RSS or Atom feed.

    Args:
        timeout: Timeout duration for the HTTP request.
        max_age: Maximum age for incidents to be considered current.

    """

    feed_url: str
    timeout: datetime.timedelta = dataclasses.field(
        default=datetime.timedelta(seconds=10), repr=False
    )
    max_age: datetime.timedelta = dataclasses.field(
        default=datetime.timedelta(hours=2), repr=False
    )

    def check_status(self):
        """Check the RSS/Atom feed for incidents."""
        logger.debug("Fetching RSS feed from %s", self.feed_url)

        try:
            request = urllib.request.Request(  # noqa: S310
                self.feed_url,
                headers={"User-Agent": "django-health-check"},
            )
            with urllib.request.urlopen(  # noqa: S310
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
        except Exception as e:
            raise ServiceUnavailable("Unknown error fetching RSS feed") from e

        try:
            root = ET.fromstring(content)  # noqa: S314
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

    def is_incident(self, entry: ET.Element) -> bool:
        """
        Determine if an entry represents an incident.

        Subclasses should override this method to implement custom incident detection.

        Args:
            entry: The RSS/Atom feed entry element.

        Returns:
            True if the entry represents an incident, False otherwise.

        """
        return False

    def _extract_entries(self, root):
        """Extract entries from RSS or Atom feed."""
        # Try Atom format first
        atom_ns = {"atom": "http://www.w3.org/2005/Atom"}
        if entries := root.findall("atom:entry", atom_ns):
            return entries

        # Try RSS 2.0 format
        if entries := root.findall(".//item"):
            return entries

        # Try RSS 1.0 format
        rss10_ns = {"rss": "http://purl.org/rss/1.0/"}
        return root.findall("rss:item", rss10_ns)

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
        if (
            (published := entry.find("atom:published", atom_ns)) is not None
            and (date_text := published.text)
        ) or (
            (updated := entry.find("atom:updated", atom_ns)) is not None
            and (date_text := updated.text)
        ) or (
            # RSS format
            (pub_date := entry.find("pubDate")) is not None
            and (date_text := pub_date.text)
        ):
            try:
                return datetime.datetime.fromisoformat(date_text.replace("Z", "+00:00"))
            except ValueError:
                return None
        return None

    def _extract_title(self, entry):
        """Extract title from entry."""
        # Atom format
        atom_ns = {"atom": "http://www.w3.org/2005/Atom"}
        if (title := entry.find("atom:title", atom_ns)) is not None:
            return title.text or "Untitled incident"

        # RSS format
        if (title := entry.find("title")) is not None:
            return title.text or "Untitled incident"

        return "Untitled incident"


@dataclasses.dataclass
class GoogleCloudStatus(RSSFeed):
    """
    Proxy for Google Cloud Platform service status.

    Checks the current operational status of Google Cloud services
    by parsing their public status feed.

    Example:
        >>> check = GoogleCloudStatus()
        >>> check.run_check()  # Check all services
        >>> # Or filter by specific service:
        >>> check = GoogleCloudStatus(service_name="Compute Engine")
        >>> check.run_check()

    Args:
        service_name: Optional service name to filter incidents.
                     If not specified, checks all services.

    """

    feed_url: str = dataclasses.field(
        default="https://status.cloud.google.com/en/feed.atom", init=False, repr=False
    )
    service_name: str | None = None

    def is_incident(self, entry: ET.Element) -> bool:
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
    Proxy for AWS service status.

    Checks the current operational status of specific AWS services
    in a given region by parsing their public status feed.

    Args:
        region: AWS region code (e.g., 'us-east-1', 'eu-west-1').
        service: AWS service name (e.g., 'ec2', 's3', 'rds').

    """

    feed_url: str = dataclasses.field(default="", init=False, repr=False)
    region: str = ""
    service: str = ""

    def __post_init__(self):
        """Initialize feed URL."""
        if not self.region or not self.service:
            raise ValueError("Both 'region' and 'service' are required")
        self.feed_url = (
            f"https://status.aws.amazon.com/rss/{self.service}-{self.region}.rss"
        )

    def is_incident(self, entry: ET.Element) -> bool:
        """Detect if entry is an incident for AWS."""
        title = self._extract_title(entry)
        title_lower = title.lower()

        # AWS marks resolved incidents with "resolved:"
        if "resolved:" in title_lower:
            return False

        # Check for incident keywords in AWS status
        incident_keywords = [
            "error",
            "issue",
            "degradation",
            "disruption",
            "outage",
            "unavailable",
        ]
        return any(keyword in title_lower for keyword in incident_keywords)


@dataclasses.dataclass
class AzureStatus(RSSFeed):
    """
    Proxy for Microsoft Azure service status.

    Checks the current operational status of Azure services
    by parsing their public status feed.

    Args:
        service_name: Optional service name to filter incidents.
                     If not specified, checks all services.

    """

    feed_url: str = dataclasses.field(
        default="https://rssfeed.azure.status.microsoft.com/en-us/status/feed/",
        init=False,
        repr=False,
    )
    service_name: str | None = None

    def is_incident(self, entry: ET.Element) -> bool:
        """Detect if entry is an incident for Azure."""
        title = self._extract_title(entry)
        title_lower = title.lower()

        # Filter by service if specified
        if self.service_name and self.service_name.lower() not in title_lower:
            return False

        # Check for incident keywords
        incident_keywords = ["outage", "degradation", "incident", "issue", "down"]
        return any(keyword in title_lower for keyword in incident_keywords)
