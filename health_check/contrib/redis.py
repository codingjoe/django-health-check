"""Redis health check."""

import dataclasses
import logging
import typing
import warnings

from redis import Redis as RedisClient
from redis import RedisCluster, exceptions, from_url

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
        client: A Redis client instance (Redis, Sentinel master, or Cluster).
                If provided, this takes precedence over redis_url.
        redis_url: (Deprecated) The Redis connection URL, e.g., 'redis://localhost:6379/0'.
                   Use the 'client' parameter instead.
        redis_url_options: (Deprecated) Additional options for the Redis connection,
                           e.g., {'socket_connect_timeout': 5}.
                           Use the 'client' parameter instead.

    Examples:
        Using a standard Redis client:
        >>> from redis import Redis as RedisClient
        >>> Redis(client=RedisClient(host='localhost', port=6379))

        Using a Cluster client:
        >>> from redis.cluster import RedisCluster
        >>> Redis(client=RedisCluster(host='localhost', port=7000))

        Using a Sentinel client:
        >>> from redis.sentinel import Sentinel
        >>> sentinel = Sentinel([('localhost', 26379)])
        >>> Redis(client=sentinel.master_for('mymaster'))

    """

    client: RedisClient | RedisCluster = dataclasses.field(default=None, repr=False)
    redis_url: str | None = dataclasses.field(default=None, repr=False)
    redis_url_options: dict[str, typing.Any] = dataclasses.field(
        default_factory=dict, repr=False
    )

    def __post_init__(self):
        if not self.client:
            warnings.warn(
                "The 'redis_url' parameter is deprecated. Please use the 'client' parameter instead.",
                DeprecationWarning,
            )
            self.client = from_url(self.redis_url, **self.redis_url_options)

    def check_status(self):
        logger.debug("Pinging Redis client...")
        try:
            self.client.ping()
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
        except BaseException as e:
            raise ServiceUnavailable("Unknown error.") from e
        else:
            logger.debug("Connection established. Redis is healthy.")
