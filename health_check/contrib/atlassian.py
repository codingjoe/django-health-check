"""Atlassian Status Page API health checks for cloud provider status pages."""

import dataclasses
import datetime
import enum
import logging

import httpx

from health_check import HealthCheck, __version__
from health_check.exceptions import ServiceUnavailable, StatusPageWarning

logger = logging.getLogger(__name__)


class AtlassianStatusPage(HealthCheck):
    """
    Base class for Atlassian status page health checks.

    Monitor cloud provider service health via Atlassian Status Page API v2.

    Each subclass should define the `base_url` for the specific status page
    and appropriate `timeout` value.

    When `component` is non-empty, only incidents affecting that named component
    are reported. If no component with that name is found in the provider's
    component list, a :exc:`~health_check.exceptions.ServiceUnavailable` error
    is raised, guarding against silent misconfiguration. An empty string (the
    default) reports all open incidents regardless of which components they
    affect.

    Use separate check instances to monitor multiple components independently:

    Examples:
        >>> import dataclasses
        >>> import datetime
        >>> from health_check.contrib.atlassian import AtlassianStatusPage
        >>> @dataclasses.dataclass
        ... class FlyIo(AtlassianStatusPage):
        ...     timeout: datetime.timedelta = datetime.timedelta(seconds=10)
        ...     base_url: str = dataclasses.field(default="https://status.flyio.net", init=False, repr=False)

    """

    base_url: str = NotImplemented
    timeout: datetime.timedelta = NotImplemented
    component: str = ""

    async def run(self):
        if incidents := [i async for i in self._fetch_incidents()]:
            raise StatusPageWarning(
                "\n".join(msg for msg, _ in incidents),
                timestamp=max(ts for _, ts in incidents),
            )
        logger.debug("No incidents found")

    async def _fetch_incidents(self):
        api_url = f"{self.base_url}/api/v2/components.json"
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

        if self.component:
            components_by_name = {c["name"]: c for c in data["components"]}
            try:
                _ = components_by_name[self.component]
            except KeyError as e:
                raise ServiceUnavailable(
                    f"Component {self.component!r} not found"
                ) from e

        for incident in data.get("incidents", []):
            if (incident.get("status") not in ("resolved", "postmortem")) and (
                self.component
                and any(
                    c["name"] == self.component for c in incident.get("components", [])
                )
            ):
                yield (
                    f"{incident['name']}: {incident['shortlink']}",
                    datetime.datetime.fromisoformat(
                        incident["updated_at"].replace("Z", "+00:00")
                    ),
                )


@dataclasses.dataclass
class Cloudflare(AtlassianStatusPage):
    """
    Check Cloudflare platform status via Atlassian Status Page API v2.

    Args:
        timeout: Request timeout duration.
        component: Name of a specific component to monitor. Monitors all
            components when empty.

    """

    timeout: datetime.timedelta = dataclasses.field(
        default=datetime.timedelta(seconds=10), repr=False
    )
    base_url: str = dataclasses.field(
        default="https://www.cloudflarestatus.com", init=False, repr=False
    )
    component: str = ""


@dataclasses.dataclass
class FlyIo(AtlassianStatusPage):
    """
    Check Fly.io platform status via Atlassian Status Page API v2.

    Args:
        timeout: Request timeout duration.
        component: Name of a specific component to monitor. Monitors all
            components when empty.

    """

    timeout: datetime.timedelta = dataclasses.field(
        default=datetime.timedelta(seconds=10), repr=False
    )
    base_url: str = dataclasses.field(
        default="https://status.flyio.net", init=False, repr=False
    )
    component: str = ""


@dataclasses.dataclass
class GitHub(AtlassianStatusPage):
    """
    Check GitHub platform status via Atlassian Status Page API v2.

    Args:
        enterprise_region: GitHub Enterprise status page region (if applicable).
        timeout: Request timeout duration.
        component: Name of a specific component to monitor. Monitors all
            components when empty.

    """

    try:

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
    except AttributeError:
        # Python <3.11 doesn't have StrEnum, so fall back to a simple string field with validation
        enterprise_region: str | None = None
    timeout: datetime.timedelta = dataclasses.field(
        default=datetime.timedelta(seconds=10), repr=False
    )
    component: str = ""

    def __post_init__(self):
        self.base_url = f"https://{self.enterprise_region if self.enterprise_region else 'www'}.githubstatus.com"


@dataclasses.dataclass
class PlatformSh(AtlassianStatusPage):
    """
    Check Platform.sh platform status via Atlassian Status Page API v2.

    Args:
        timeout: Request timeout duration.
        component: Name of a specific component to monitor. Monitors all
            components when empty.

    """

    timeout: datetime.timedelta = dataclasses.field(
        default=datetime.timedelta(seconds=10), repr=False
    )
    base_url: str = dataclasses.field(
        default="https://status.platform.sh", init=False, repr=False
    )
    component: str = ""


@dataclasses.dataclass
class DigitalOcean(AtlassianStatusPage):
    """
    Check DigitalOcean platform status via Atlassian Status Page API v2.

    Args:
        timeout: Request timeout duration.
        component: Name of a specific component to monitor. Monitors all
            components when empty.

    """

    timeout: datetime.timedelta = dataclasses.field(
        default=datetime.timedelta(seconds=10), repr=False
    )
    base_url: str = dataclasses.field(
        default="https://status.digitalocean.com", init=False, repr=False
    )
    component: str = ""


@dataclasses.dataclass
class Render(AtlassianStatusPage):
    """
    Check Render platform status via Atlassian Status Page API v2.

    Args:
        timeout: Request timeout duration.
        component: Name of a specific component to monitor. Monitors all
            components when empty.

    """

    timeout: datetime.timedelta = dataclasses.field(
        default=datetime.timedelta(seconds=10), repr=False
    )
    base_url: str = dataclasses.field(
        default="https://status.render.com", init=False, repr=False
    )
    component: str = ""


@dataclasses.dataclass
class Sentry(AtlassianStatusPage):
    """
    Check Sentry platform status via Atlassian Status Page API v2.

    Args:
        timeout: Request timeout duration.
        component: Name of a specific component to monitor. Monitors all
            components when empty.

    """

    timeout: datetime.timedelta = dataclasses.field(
        default=datetime.timedelta(seconds=10), repr=False
    )
    base_url: str = dataclasses.field(
        default="https://status.sentry.io", init=False, repr=False
    )
    component: str = ""


@dataclasses.dataclass
class Vercel(AtlassianStatusPage):
    """
    Check Vercel platform status via Atlassian Status Page API v2.

    Args:
        timeout: Request timeout duration.
        component: Name of a specific component to monitor. Monitors all
            components when empty.

    """

    timeout: datetime.timedelta = dataclasses.field(
        default=datetime.timedelta(seconds=10), repr=False
    )
    base_url: str = dataclasses.field(
        default="https://www.vercel-status.com", init=False, repr=False
    )
    component: str = ""
