"""RSS feed health checks for cloud provider status pages."""

import dataclasses
import datetime
import logging
import typing

import feedparser
import httpx

from health_check import HealthCheck, __version__
from health_check.exceptions import ServiceUnavailable, ServiceWarning

logger = logging.getLogger(__name__)


class Feed(HealthCheck):
    """
    Base class for cloud provider status feed health checks.

    Monitor cloud provider service health via their public RSS or Atom status feeds.

    Subclasses must provide:

    Attributes:
        feed_url: The full URL of the RSS or Atom feed to monitor.
        timeout: Maximum duration to wait for the HTTP request before failing.
        max_age: Maximum age for an incident entry to be considered active.

    The `timeout` and `max_age` values are used to control how long the
    health check waits for the feed and how far back in time incidents are
    considered relevant. The `feed_url` is used to fetch the status feed.

    Examples:
        >>> import dataclasses
        >>> import datetime
        >>> import typing
        >>> from health_check.contrib.rss import Feed
        >>> @dataclasses.dataclass
        ... class MyProviderStatus(Feed):
        ...     \"\"\"Check MyProvider status via its public RSS feed.\"\"\"
        ...     timeout: datetime.timedelta = dataclasses.field(
        ...         default=datetime.timedelta(seconds=10),
        ...         repr=False,
        ...     )
        ...     max_age: datetime.timedelta = dataclasses.field(
        ...         default=datetime.timedelta(hours=4),
        ...         repr=False,
        ...     )
        ...     feed_url: typing.ClassVar[str] = "https://status.myprovider.com/feed"

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
                    headers={"User-Agent": f"django-health-check@{__version__}"},
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
                    f"HTTP error {e.response.status_code} fetching feed from {self.feed_url!r}"
                ) from e

            content = response.text

        feed = feedparser.parse(content)

        if feed.bozo:
            # feedparser sets bozo=1 for malformed feeds
            logger.warning("Feed parsing encountered errors: %s", feed.bozo_exception)

        if not feed.entries:
            logger.debug("No entries found in feed")
            return

        incidents = [entry for entry in feed.entries if self._is_recent_incident(entry)]

        if incidents:
            raise ServiceWarning(
                f"Found {len(incidents)} recent incident(s): {
                    ', '.join(
                        getattr(entry, 'title', 'Untitled incident')
                        or 'Untitled incident'
                        for entry in incidents
                    )
                }"
            )

        logger.debug("No recent incidents found in feed")

    def _is_recent_incident(self, entry):
        """Check if entry is a recent incident."""
        published_at = self._extract_date(entry)
        if not published_at:
            return True

        now = datetime.datetime.now(tz=datetime.timezone.utc)
        cutoff = now - self.max_age
        return now >= published_at > cutoff

    def _extract_date(self, entry):
        # feedparser normalizes both RSS and Atom dates to struct_time
        # Try published first, then updated
        for date_field in ["published_parsed", "updated_parsed"]:
            if date_tuple := getattr(entry, date_field, None):
                try:
                    # Convert struct_time to datetime
                    return datetime.datetime(
                        *date_tuple[:6], tzinfo=datetime.timezone.utc
                    )
                except ValueError:
                    pass
        return None


@dataclasses.dataclass
class AWS(Feed):
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
class Heroku(Feed):
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
class Azure(Feed):
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
class GoogleCloud(Feed):
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
