"""RSS/Atom feed health checks for cloud provider status pages."""

import dataclasses
import datetime
import logging
import urllib.error
import urllib.request
from xml.etree import ElementTree

from health_check.base import HealthCheck
from health_check.exceptions import ServiceUnavailable, ServiceWarning

logger = logging.getLogger(__name__)


@dataclasses.dataclass
class AWS(HealthCheck):
    """
    Check AWS service status via their public RSS status feeds.

    Args:
        region: AWS region code (e.g., 'us-east-1', 'eu-west-1').
        service: AWS service name (e.g., 'ec2', 's3', 'rds').
        timeout: Request timeout duration.
        max_age: Maximum age for an incident to be considered active.

    """

    region: str
    service: str
    timeout: datetime.timedelta = dataclasses.field(
        default=datetime.timedelta(seconds=10), repr=False
    )
    max_age: datetime.timedelta = dataclasses.field(
        default=datetime.timedelta(days=1), repr=False
    )

    def __post_init__(self):
        self.feed_url: str = (
            f"https://status.aws.amazon.com/rss/{self.service}-{self.region}.rss"
        )

    def check_status(self):
        """Check the RSS/Atom feed for incidents."""
        logger.debug("Fetching feed from %s", self.feed_url)

        request = urllib.request.Request(  # noqa: S310
            self.feed_url,
            headers={"User-Agent": "django-health-check"},
        )

        try:
            with urllib.request.urlopen(  # noqa: S310
                request, timeout=self.timeout.total_seconds()
            ) as response:
                content = response.read()
        except urllib.error.HTTPError as e:
            raise ServiceUnavailable(f"HTTP error {e.code} fetching RSS feed") from e
        except urllib.error.URLError as e:
            raise ServiceUnavailable(f"Failed to fetch RSS feed: {e.reason}") from e
        except TimeoutError as e:
            raise ServiceUnavailable("RSS feed request timed out") from e
        except Exception as e:
            raise ServiceUnavailable("Unknown error fetching RSS feed") from e

        try:
            root = ElementTree.fromstring(content)  # noqa: S314
        except ElementTree.ParseError as e:
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
        published_at = self._extract_date(entry)
        if not published_at:
            return True

        cutoff = datetime.datetime.now(tz=datetime.timezone.utc) - self.max_age
        return published_at > cutoff

    def _extract_date(self, entry):
        """Extract publication date from entry."""
        # Atom format
        atom_ns = {"atom": "http://www.w3.org/2005/Atom"}
        date_text = (
            (
                (published := entry.find("atom:published", atom_ns)) is not None
                and published.text
            )
            or (
                (updated := entry.find("atom:updated", atom_ns)) is not None
                and updated.text
            )
            or (
                # RSS format
                (pub_date := entry.find("pubDate")) is not None and pub_date.text
            )
            or None
        )

        if date_text is None:
            return None

        try:
            return datetime.datetime.fromisoformat(date_text.replace("Z", "+00:00"))
        except ValueError:
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
