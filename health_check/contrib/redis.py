"""Redis health check."""

import dataclasses
import logging

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
        client: A Redis client instance (Redis, Sentinel master, or Cluster).
                If provided, this takes precedence over redis_url.

    Examples:
        Using a standard Redis client:
        >>> from redis.asyncio import Redis as RedisClient
        >>> Redis(client=RedisClient(host='localhost', port=6379))

        Using a Cluster client:
        >>> from redis.asyncio import RedisCluster
        >>> Redis(client=RedisCluster(host='localhost', port=7000))

        Using a Sentinel client:
        >>> from redis.asyncio import Sentinel
        >>> sentinel = Sentinel([('localhost', 26379)])
        >>> Redis(client=sentinel.master_for('mymaster'))

    """

    client: RedisClient | RedisCluster = dataclasses.field(default=None, repr=False)

    async def run(self):
        logger.debug("Pinging Redis client...")
        try:
            await self.client.ping()
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
            raise ServiceUnavailable("Unknown error") from e
        else:
            logger.debug("Connection established. Redis is healthy.")
        finally:
            await self.client.close()
