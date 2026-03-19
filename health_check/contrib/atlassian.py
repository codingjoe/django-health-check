"""Atlassian Status Page API health checks for cloud provider status pages."""

import dataclasses
import datetime
import enum
import logging

import httpx

from health_check import HealthCheck, __version__
from health_check.exceptions import ServiceUnavailable, StatusPageWarning

logger = logging.getLogger(__name__)


@dataclasses.dataclass(eq=False)
class _ComponentNamesCheck:
    """Django system check that validates configured component names against the provider's components API."""

    status_page: "AtlassianStatusPage"

    def __call__(self, app_configs, **kwargs):
        from django.core.checks import Warning as CheckWarning

        api_url = f"{self.status_page.base_url}/api/v2/components.json"
        try:
            response = httpx.get(
                api_url,
                headers={"User-Agent": f"django-health-check@{__version__}"},
                timeout=self.status_page.timeout.total_seconds(),
                follow_redirects=True,
            )
            response.raise_for_status()
            data = response.json()
        except Exception:
            logger.warning(
                "Could not validate components: failed to fetch %r",
                api_url,
                exc_info=True,
            )
            return []

        valid_names = {
            component["name"] for component in data.get("components", [])
        }
        return [
            CheckWarning(
                f"Unknown component {name!r} configured for {self.status_page!r}.",
                hint=f"Valid component names: {', '.join(sorted(valid_names))}",
                obj=self.status_page,
                id="health_check.W001",
            )
            for name in self.status_page.components
            if name not in valid_names
        ]


class AtlassianStatusPage(HealthCheck):
    """
    Base class for Atlassian status page health checks.

    Monitor cloud provider service health via Atlassian Status Page API v2.

    Each subclass should define the `base_url` for the specific status page
    and appropriate `timeout` value. The `max_age` parameter is not used
    since the API endpoint only returns currently unresolved incidents.

    When `components` is non-empty, only incidents affecting at least one
    of the named components are reported. An empty frozenset (the default)
    reports all incidents regardless of which components they affect.

    Examples:
        >>> import dataclasses
        >>> import datetime
        >>> import typing
        >>> from health_check.contrib.atlassian import AtlassianStatusPage
        >>> @dataclasses.dataclass
        >>> class FlyIo(AtlassianStatusPage):
        ...     timeout: datetime.timedelta = datetime.timedelta(seconds=10)
        ...     base_url: str = dataclasses.field(default="https://status.flyio.net", init=False, repr=False)

    """

    base_url: str = NotImplemented
    timeout: datetime.timedelta = NotImplemented
    components: frozenset[str] = frozenset()

    def __post_init__(self):
        """Register a Django system check to validate configured component names."""
        if self.components:
            from django.core import checks

            checks.register(_ComponentNamesCheck(self))

    async def run(self):
        if incidents := [i async for i in self._fetch_incidents()]:
            raise StatusPageWarning(
                "\n".join(msg for msg, _ in incidents),
                timestamp=max(ts for _, ts in incidents),
            )
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
            if incident["status"] in ("resolved", "postmortem"):
                continue
            if self.components and not any(
                c["name"] in self.components for c in incident.get("components", [])
            ):
                continue
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
        components: Limit alerts to incidents affecting these component names.

    """

    timeout: datetime.timedelta = dataclasses.field(
        default=datetime.timedelta(seconds=10), repr=False
    )
    base_url: str = dataclasses.field(
        default="https://www.cloudflarestatus.com", init=False, repr=False
    )
    components: frozenset[str] = dataclasses.field(default_factory=frozenset)


@dataclasses.dataclass
class FlyIo(AtlassianStatusPage):
    """
    Check Fly.io platform status via Atlassian Status Page API v2.

    Args:
        timeout: Request timeout duration.
        components: Limit alerts to incidents affecting these component names.

    """

    timeout: datetime.timedelta = dataclasses.field(
        default=datetime.timedelta(seconds=10), repr=False
    )
    base_url: str = dataclasses.field(
        default="https://status.flyio.net", init=False, repr=False
    )
    components: frozenset[str] = dataclasses.field(default_factory=frozenset)


@dataclasses.dataclass
class GitHub(AtlassianStatusPage):
    """
    Check GitHub platform status via Atlassian Status Page API v2.

    Args:
        enterprise_region: GitHub Enterprise status page region (if applicable).
        timeout: Request timeout duration.
        components: Limit alerts to incidents affecting these component names.

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
    components: frozenset[str] = dataclasses.field(default_factory=frozenset)

    def __post_init__(self):
        self.base_url = f"https://{self.enterprise_region if self.enterprise_region else 'www'}.githubstatus.com"
        super().__post_init__()


@dataclasses.dataclass
class PlatformSh(AtlassianStatusPage):
    """
    Check Platform.sh platform status via Atlassian Status Page API v2.

    Args:
        timeout: Request timeout duration.
        components: Limit alerts to incidents affecting these component names.

    """

    timeout: datetime.timedelta = dataclasses.field(
        default=datetime.timedelta(seconds=10), repr=False
    )
    base_url: str = dataclasses.field(
        default="https://status.platform.sh", init=False, repr=False
    )
    components: frozenset[str] = dataclasses.field(default_factory=frozenset)


@dataclasses.dataclass
class DigitalOcean(AtlassianStatusPage):
    """
    Check DigitalOcean platform status via Atlassian Status Page API v2.

    Args:
        timeout: Request timeout duration.
        components: Limit alerts to incidents affecting these component names.

    """

    timeout: datetime.timedelta = dataclasses.field(
        default=datetime.timedelta(seconds=10), repr=False
    )
    base_url: str = dataclasses.field(
        default="https://status.digitalocean.com", init=False, repr=False
    )
    components: frozenset[str] = dataclasses.field(default_factory=frozenset)


@dataclasses.dataclass
class Render(AtlassianStatusPage):
    """
    Check Render platform status via Atlassian Status Page API v2.

    Args:
        timeout: Request timeout duration.
        components: Limit alerts to incidents affecting these component names.

    """

    timeout: datetime.timedelta = dataclasses.field(
        default=datetime.timedelta(seconds=10), repr=False
    )
    base_url: str = dataclasses.field(
        default="https://status.render.com", init=False, repr=False
    )
    components: frozenset[str] = dataclasses.field(default_factory=frozenset)


@dataclasses.dataclass
class Sentry(AtlassianStatusPage):
    """
    Check Sentry platform status via Atlassian Status Page API v2.

    Args:
        timeout: Request timeout duration.
        components: Limit alerts to incidents affecting these component names.

    """

    timeout: datetime.timedelta = dataclasses.field(
        default=datetime.timedelta(seconds=10), repr=False
    )
    base_url: str = dataclasses.field(
        default="https://status.sentry.io", init=False, repr=False
    )
    components: frozenset[str] = dataclasses.field(default_factory=frozenset)


@dataclasses.dataclass
class Vercel(AtlassianStatusPage):
    """
    Check Vercel platform status via Atlassian Status Page API v2.

    Args:
        timeout: Request timeout duration.
        components: Limit alerts to incidents affecting these component names.

    """

    timeout: datetime.timedelta = dataclasses.field(
        default=datetime.timedelta(seconds=10), repr=False
    )
    base_url: str = dataclasses.field(
        default="https://www.vercel-status.com", init=False, repr=False
    )
    components: frozenset[str] = dataclasses.field(default_factory=frozenset)
