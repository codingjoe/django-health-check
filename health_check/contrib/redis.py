"""Redis health check."""

import dataclasses
import logging
import typing
import warnings

from redis import exceptions
from redis.asyncio import Redis as RedisClient
from redis.asyncio import RedisCluster

from health_check.base import HealthCheck
from health_check.exceptions import ServiceUnavailable

logger = logging.getLogger(__name__)


@dataclasses.dataclass
class Redis(HealthCheck):
    """
    Check Redis service by pinging a Redis client.

    This check works with any Redis client that implements the ping() method,
    including standard Redis, Sentinel, and Cluster clients.

    Args:
        client_factory: A callable that returns an instance of a Redis client.
        client: Deprecated, use `client_factory` instead.

    Examples:
        Using a standard Redis client:
        >>> from redis.asyncio import Redis as RedisClient
        >>> Redis(client_factory=lambda: RedisClient(host='localhost', port=6379))

        Using from_url to create a client:
        >>> from redis.asyncio import Redis as RedisClient
        >>> Redis(client_factory=lambda: RedisClient.from_url('redis://localhost:6379'))

        Using a Cluster client:
        >>> from redis.asyncio import RedisCluster
        >>> Redis(client_factory=lambda: RedisCluster(host='localhost', port=7000))

        Using a Sentinel client:
        >>> from redis.asyncio import Sentinel
        >>> Redis(client_factory=lambda: Sentinel([('localhost', 26379)]).master_for('mymaster'))

    """

    client: RedisClient | RedisCluster | None = dataclasses.field(repr=False, default=None)
    client_factory: typing.Callable[[], RedisClient | RedisCluster] | None = (
        dataclasses.field(repr=False, default=None)
    )

    def __post_init__(self):
        if not self.client_factory and not self.client:
            raise ValueError("Either 'client_factory' or 'client' must be provided.")
        if self.client and not self.client_factory:
            warnings.warn(
                "The `client` argument is deprecated and will be removed in a future version. "
                "Please use `client_factory` instead.",
                DeprecationWarning,
                stacklevel=2,
            )

    async def run(self):
        logger.debug("Pinging Redis client...")

        # Create a fresh client if using factory, otherwise use the provided client
        if self.client_factory:
            client = self.client_factory()
        else:
            client = self.client

        try:
            await client.ping()
        except ConnectionRefusedError as e:
            raise ServiceUnavailable(
                "Unable to connect to Redis: Connection was refused."
            ) from e
        except exceptions.TimeoutError as e:
            raise ServiceUnavailable("Unable to connect to Redis: Timeout.") from e
        except exceptions.ConnectionError as e:
            raise ServiceUnavailable(
                "Unable to connect to Redis: Connection Error"
            ) from e
        else:
            logger.debug("Connection established. Redis is healthy.")
        finally:
            # Only close client if created by factory
            if self.client_factory:
                await client.aclose()
