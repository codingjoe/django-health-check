"""django-crontask health check."""

import dataclasses
import typing

from django.conf import settings
from redis import exceptions
from redis.asyncio import Redis as RedisClient

from health_check.base import HealthCheck
from health_check.exceptions import ServiceUnavailable


def create_client_from_settings() -> RedisClient:
    url = (getattr(settings, "CRONTASK", None) or {}).get("REDIS_URL")
    if not url:
        raise ServiceUnavailable(
            "CRONTASK['REDIS_URL'] is not configured. Set it to the Redis URL of "
            "the crontask scheduler's lock, or pass a client_factory."
        )
    # A fixed 1 s connect and read budget stops an unreachable Redis from
    # stalling the health endpoint; supply your own client_factory for longer.
    return RedisClient.from_url(url, socket_timeout=1, socket_connect_timeout=1)


@dataclasses.dataclass
class Scheduler(HealthCheck):
    """
    Presence of the django-crontask lock in Redis.

    django-crontask renews its lock as a dead man's switch while it runs, so a
    missing key means it is dead. Requires `CRONTASK["REDIS_URL"]`, since
    django-crontask uses a no-op lock without it.

    Args:
        client_factory: A callable returning a Redis client, defaults to
            `create_client_from_settings`.

    """

    client_factory: typing.Callable[[], RedisClient] = dataclasses.field(
        default=create_client_from_settings, repr=False
    )

    async def run(self):
        client = self.client_factory()
        try:
            # django-crontask hardcodes this key with no setting; update if renamed
            if not await client.exists("crontask-lock"):
                raise ServiceUnavailable("No django-crontask scheduler is running.")
        except exceptions.RedisError as e:
            raise ServiceUnavailable("Unable to query the crontask lock.") from e
        finally:
            await client.aclose()
