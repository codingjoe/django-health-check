"""Atlassian Status Page API health checks for cloud provider status pages."""

import dataclasses
import datetime
import enum
import logging
import typing

import httpx

from health_check import HealthCheck, __version__
from health_check.exceptions import ServiceUnavailable, ServiceWarning

logger = logging.getLogger(__name__)


class AtlassianStatusPage(HealthCheck):
    """
    Base class for Atlassian status page health checks.

    Monitor cloud provider service health via Atlassian Status Page API v2.

    Each subclass should define the `base_url` for the specific status page
    and appropriate `timeout` value. The `max_age` parameter is not used
    since the API endpoint only returns currently unresolved incidents.

    Examples:
        >>> class FlyIo(AtlassianStatusPage):
        ...     timeout = datetime.timedelta(seconds=10)
        ...     base_url = "https://status.flyio.net"

    """

    base_url: typing.ClassVar[str] = NotImplemented
    timeout: datetime.timedelta = NotImplemented

    async def run(self):
        if msg := "\n".join([i async for i in self._fetch_incidents()]):
            raise ServiceWarning(msg)
        logger.debug("No recent incidents found")

    async def _fetch_incidents(self):
        api_url = f"{self.base_url}/api/v2/incidents/unresolved.json"
        logger.debug("Fetching incidents from %r", api_url)

        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(
                    api_url,
                    headers={"User-Agent": f"django-health-check@{__version__}"},
                    timeout=self.timeout.total_seconds(),
                    follow_redirects=True,
                )
            except httpx.TimeoutException as e:
                raise ServiceUnavailable("API request timed out") from e
            except httpx.RequestError as e:
                raise ServiceUnavailable(f"Failed to fetch API: {e}") from e

            try:
                response.raise_for_status()
            except httpx.HTTPStatusError as e:
                raise ServiceUnavailable(
                    f"HTTP error {e.response.status_code} fetching API from {api_url!r}"
                ) from e

            try:
                data = response.json()
            except ValueError as e:
                raise ServiceUnavailable("Failed to parse JSON response") from e

        for incident in data["incidents"]:
            yield f"{incident['name']}: {incident['shortlink']}"


@dataclasses.dataclass
class Cloudflare(AtlassianStatusPage):
    """
    Check Cloudflare platform status via Atlassian Status Page API v2.

    Args:
        timeout: Request timeout duration.

    """

    timeout: datetime.timedelta = dataclasses.field(
        default=datetime.timedelta(seconds=10), repr=False
    )
    base_url: typing.ClassVar[str] = "https://www.cloudflarestatus.com"


@dataclasses.dataclass
class FlyIo(AtlassianStatusPage):
    """
    Check Fly.io platform status via Atlassian Status Page API v2.

    Args:
        timeout: Request timeout duration.

    """

    timeout: datetime.timedelta = dataclasses.field(
        default=datetime.timedelta(seconds=10), repr=False
    )
    base_url: typing.ClassVar[str] = "https://status.flyio.net"


@dataclasses.dataclass
class GitHub(AtlassianStatusPage):
    """
    Check GitHub platform status via Atlassian Status Page API v2.

    Args:
        enterprise_region: GitHub Enterprise status page region (if applicable).
        timeout: Request timeout duration.

    """

    class EnterpriseRegion(enum.StrEnum):
        """GitHub Enterprise status page regions."""

        australia = "au"
        """Australia."""
        eu = "eu"
        """Europe."""
        japan = "jp"
        """Japan."""
        us = "us"
        """United States."""

    enterprise_region: EnterpriseRegion | None = None
    timeout: datetime.timedelta = dataclasses.field(
        default=datetime.timedelta(seconds=10), repr=False
    )

    def __post_init__(self):
        self.base_url = f"https://{self.enterprise_region if self.enterprise_region else 'www'}.githubstatus.com"


@dataclasses.dataclass
class PlatformSh(AtlassianStatusPage):
    """
    Check Platform.sh platform status via Atlassian Status Page API v2.

    Args:
        timeout: Request timeout duration.

    """

    timeout: datetime.timedelta = dataclasses.field(
        default=datetime.timedelta(seconds=10), repr=False
    )
    base_url: typing.ClassVar[str] = "https://status.platform.sh"


@dataclasses.dataclass
class DigitalOcean(AtlassianStatusPage):
    """
    Check DigitalOcean platform status via Atlassian Status Page API v2.

    Args:
        timeout: Request timeout duration.

    """

    timeout: datetime.timedelta = dataclasses.field(
        default=datetime.timedelta(seconds=10), repr=False
    )
    base_url: typing.ClassVar[str] = "https://status.digitalocean.com"


@dataclasses.dataclass
class Render(AtlassianStatusPage):
    """
    Check Render platform status via Atlassian Status Page API v2.

    Args:
        timeout: Request timeout duration.

    """

    timeout: datetime.timedelta = dataclasses.field(
        default=datetime.timedelta(seconds=10), repr=False
    )
    base_url: typing.ClassVar[str] = "https://status.render.com"


@dataclasses.dataclass
class Sentry(AtlassianStatusPage):
    """
    Check Sentry platform status via Atlassian Status Page API v2.

    Args:
        timeout: Request timeout duration.

    """

    timeout: datetime.timedelta = dataclasses.field(
        default=datetime.timedelta(seconds=10), repr=False
    )
    base_url: typing.ClassVar[str] = "https://status.sentry.io"


@dataclasses.dataclass
class Vercel(AtlassianStatusPage):
    """
    Check Vercel platform status via Atlassian Status Page API v2.

    Args:
        timeout: Request timeout duration.

    """

    timeout: datetime.timedelta = dataclasses.field(
        default=datetime.timedelta(seconds=10), repr=False
    )
    base_url: typing.ClassVar[str] = "https://www.vercel-status.com"
