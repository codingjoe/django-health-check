"""RSS feed health checks for cloud provider status pages."""

import dataclasses
import datetime
import email.utils
import logging
import typing
from xml.etree import ElementTree

import httpx

from health_check.base import HealthCheck
from health_check.exceptions import ServiceUnavailable, ServiceWarning

logger = logging.getLogger(__name__)


class StatusFeedBase(HealthCheck):
    """
    Base class for cloud provider status feed health checks.

    Monitor cloud provider service health via their public RSS or Atom status feeds.
    """

    feed_url: typing.ClassVar[str] = NotImplemented
    timeout: datetime.timedelta = NotImplemented
    max_age: datetime.timedelta = NotImplemented

    async def run(self):
        logger.debug("Fetching feed from %s", self.feed_url)

        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(
                    self.feed_url,
                    headers={"User-Agent": "django-health-check"},
                    timeout=self.timeout.total_seconds(),
                    follow_redirects=True,
                )
            except httpx.TimeoutException as e:
                raise ServiceUnavailable("Feed request timed out") from e
            except httpx.RequestError as e:
                raise ServiceUnavailable(f"Failed to fetch feed: {e}") from e

            try:
                response.raise_for_status()
            except httpx.HTTPStatusError as e:
                raise ServiceUnavailable(
                    f"HTTP error {e.response.status_code} fetching feed {e.response.text}"
                ) from e

            content = response.text

        try:
            root = ElementTree.fromstring(content)  # noqa: S314
        except ElementTree.ParseError as e:
            raise ServiceUnavailable("Failed to parse feed") from e

        entries = self._extract_entries(root)
        incidents = [entry for entry in entries if self._is_recent_incident(entry)]

        if incidents:
            incident_titles = [self._extract_title(entry) for entry in incidents]
            raise ServiceWarning(
                f"Found {len(incidents)} recent incident(s): {', '.join(incident_titles)}"
            )

        logger.debug("No recent incidents found in feed")

    def _extract_entries(self, root):
        """
        Extract entries from feed.

        Returns:
            list: Entry elements from the feed.

        """
        raise NotImplementedError

    def _is_recent_incident(self, entry):
        """Check if entry is a recent incident."""
        published_at = self._extract_date(entry)
        if not published_at:
            return True

        cutoff = datetime.datetime.now(tz=datetime.timezone.utc) - self.max_age
        return datetime.datetime.now(tz=datetime.timezone.utc) >= published_at > cutoff

    def _extract_date(self, entry):
        """
        Extract publication date from entry.

        Returns:
            datetime or None: Publication date, or None if not found.

        """
        raise NotImplementedError

    def _extract_title(self, entry):
        """
        Extract title from entry.

        Returns:
            str: Entry title, or 'Untitled incident' if not found.

        """
        raise NotImplementedError


@dataclasses.dataclass
class RSSFeed(StatusFeedBase):
    """
    Base class for RSS 2.0 feed health checks.

    Examples:
        >>> class MyService(RSSFeed):
        ...     feed_url = "https://example.com/status/rss"
        ...     timeout = datetime.timedelta(seconds=10)
        ...     max_age = datetime.timedelta(hours=8)

    """

    def _extract_entries(self, root):
        """Extract entries from RSS 2.0 feed."""
        return root.findall(".//item")

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


@dataclasses.dataclass
class AtomFeed(StatusFeedBase):
    """
    Base class for Atom feed health checks.

    Examples:
        >>> class MyService(AtomFeed):
        ...     feed_url = "https://example.com/status/atom"
        ...     timeout = datetime.timedelta(seconds=10)
        ...     max_age = datetime.timedelta(hours=8)

    """

    def _extract_entries(self, root):
        """Extract entries from Atom feed."""
        namespace = {"atom": "http://www.w3.org/2005/Atom"}
        entries = root.findall(".//atom:entry", namespace)
        if not entries:
            entries = root.findall(".//{http://www.w3.org/2005/Atom}entry")
        return entries

    def _extract_date(self, entry):
        """Extract publication date from Atom entry."""
        namespace = {"atom": "http://www.w3.org/2005/Atom"}

        for date_field in ["published", "updated"]:
            date_element = entry.find(f"atom:{date_field}", namespace)
            if date_element is None:
                date_element = entry.find(
                    f"{{http://www.w3.org/2005/Atom}}{date_field}"
                )

            if date_element is not None and (date_text := date_element.text):
                try:
                    return datetime.datetime.fromisoformat(
                        date_text.replace("Z", "+00:00")
                    )
                except (ValueError, TypeError):
                    pass

    def _extract_title(self, entry):
        """Extract title from Atom entry."""
        namespace = {"atom": "http://www.w3.org/2005/Atom"}

        title = entry.find("atom:title", namespace)
        if title is None:
            title = entry.find("{http://www.w3.org/2005/Atom}title")

        if title is not None:
            return title.text or "Untitled incident"
        return "Untitled incident"


@dataclasses.dataclass
class AWS(RSSFeed):
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
        default=datetime.timedelta(hours=8), repr=False
    )

    def __post_init__(self):
        self.feed_url: str = (
            f"https://status.aws.amazon.com/rss/{self.service}-{self.region}.rss"
        )


@dataclasses.dataclass
class Heroku(RSSFeed):
    """
    Check Heroku platform status via their public RSS status feed.

    Args:
        timeout: Request timeout duration.
        max_age: Maximum age for an incident to be considered active.

    """

    timeout: datetime.timedelta = dataclasses.field(
        default=datetime.timedelta(seconds=10), repr=False
    )
    max_age: datetime.timedelta = dataclasses.field(
        default=datetime.timedelta(hours=8), repr=False
    )
    feed_url: typing.ClassVar[str] = "https://status.heroku.com/feed"


@dataclasses.dataclass
class Azure(RSSFeed):
    """
    Check Azure platform status via their public RSS status feed.

    Args:
        timeout: Request timeout duration.
        max_age: Maximum age for an incident to be considered active.

    """

    timeout: datetime.timedelta = dataclasses.field(
        default=datetime.timedelta(seconds=10), repr=False
    )
    max_age: datetime.timedelta = dataclasses.field(
        default=datetime.timedelta(hours=8), repr=False
    )
    feed_url: typing.ClassVar[str] = (
        "https://rssfeed.azure.status.microsoft/en-us/status/feed/"
    )


@dataclasses.dataclass
class GoogleCloud(AtomFeed):
    """
    Check Google Cloud platform status via their public Atom status feed.

    Args:
        timeout: Request timeout duration.
        max_age: Maximum age for an incident to be considered active.

    """

    timeout: datetime.timedelta = dataclasses.field(
        default=datetime.timedelta(seconds=10), repr=False
    )
    max_age: datetime.timedelta = dataclasses.field(
        default=datetime.timedelta(hours=8), repr=False
    )

    feed_url: typing.ClassVar[str] = "https://status.cloud.google.com/en/feed.atom"
