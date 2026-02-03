"""RSS feed health checks for cloud provider status pages."""

import dataclasses
import datetime
import email.utils
import logging
from xml.etree import ElementTree

import httpx

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

    async def run(self):
        """Check the RSS feed for incidents."""
        logger.debug("Fetching feed from %s", self.feed_url)

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    self.feed_url,
                    headers={"User-Agent": "django-health-check"},
                    timeout=self.timeout.total_seconds(),
                    follow_redirects=True,
                )
                response.raise_for_status()
                content = response.content
        except httpx.HTTPStatusError as e:
            raise ServiceUnavailable(
                f"HTTP error {e.response.status_code} fetching RSS feed"
            ) from e
        except httpx.TimeoutException as e:
            raise ServiceUnavailable("RSS feed request timed out") from e
        except httpx.RequestError as e:
            raise ServiceUnavailable(f"Failed to fetch RSS feed: {e}") from e

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
        """Extract entries from RSS 2.0 feed."""
        return root.findall(".//item")

    def _is_recent_incident(self, entry):
        """Check if entry is a recent incident."""
        published_at = self._extract_date(entry)
        if not published_at:
            return True

        cutoff = datetime.datetime.now(tz=datetime.timezone.utc) - self.max_age
        return published_at > cutoff

    def _extract_date(self, entry):
        """Extract publication date from RSS entry."""
        pub_date = entry.find("pubDate")
        if pub_date is not None and (date_text := pub_date.text):
            try:
                return email.utils.parsedate_to_datetime(date_text)
            except (ValueError, TypeError):
                pass

    def _extract_title(self, entry):
        """Extract title from RSS entry."""
        if (title := entry.find("title")) is not None:
            return title.text or "Untitled incident"

        return "Untitled incident"
