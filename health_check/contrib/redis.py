"""Redis health check."""

import dataclasses
import logging

from redis import exceptions
from redis.asyncio import Redis as RedisClient

from health_check.base import HealthCheck
from health_check.exceptions import ServiceUnavailable

logger = logging.getLogger(__name__)


@dataclasses.dataclass
class Redis(HealthCheck):
    """
    Check Redis service by pinging a Redis server.

    Creates a new Redis client connection for each health check to avoid
    event loop binding issues across multiple requests.

    Args:
        redis_url: Redis connection URL, e.g., 'redis://localhost:6379/0'.

    Examples:
        Using a Redis URL:
        >>> Redis(redis_url='redis://localhost:6379/0')

        With authentication:
        >>> Redis(redis_url='redis://:password@localhost:6379/0')

        Using Redis Cluster:
        >>> Redis(redis_url='redis://localhost:7000')

    """

    redis_url: str

    async def run(self):
        logger.debug("Connecting to Redis at %r...", self.redis_url)
        client = RedisClient.from_url(self.redis_url)
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
            await client.aclose()
