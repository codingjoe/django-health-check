"""Redis health check."""

import dataclasses
import logging
import typing

from redis import exceptions, from_url

from health_check.base import HealthCheck
from health_check.exceptions import ServiceUnavailable

logger = logging.getLogger(__name__)


@dataclasses.dataclass
class Redis(HealthCheck):
    """
    Check Redis service by pinging the redis instance with a redis connection.

    Args:
        redis_url: The Redis connection URL, e.g., 'redis://localhost:6379/0'.
        redis_url_options: Additional options for the Redis connection,
                           e.g., {'socket_connect_timeout': 5}.

    """

    redis_url: str = dataclasses.field(repr=False)
    redis_url_options: dict[str, typing.Any] = dataclasses.field(
        default_factory=dict, repr=False
    )

    def check_status(self):
        logger.debug("Got %s as the redis_url. Connecting to redis...", self.redis_url)

        logger.debug("Attempting to connect to redis...")
        try:
            # conn is used as a context to release opened resources later
            with from_url(self.redis_url, **self.redis_url_options) as conn:
                conn.ping()  # exceptions may be raised upon ping
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
