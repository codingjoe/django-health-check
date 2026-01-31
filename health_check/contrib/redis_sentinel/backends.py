import logging

from django.conf import settings
from redis import Sentinel, exceptions

from health_check.backends import BaseHealthCheckBackend
from health_check.exceptions import ServiceUnavailable

logger = logging.getLogger(__name__)


class RedisSentinelHealthCheck(BaseHealthCheckBackend):
    """Health check for Redis Sentinel."""

    redis_sentinels = getattr(settings, "REDIS_SENTINELS", ())
    redis_master_name = getattr(settings, "REDIS_MASTER_NAME", "mymaster")
    redis_sentinels_healthcheck_socket_timeout = getattr(
        settings, "REDIS_SENTINELS_HEALTHCHECK_SOCKET_TIMEOUT", 1000
    )

    def check_status(self, subset=None):
        """Check Redis service by pinging the redis instance with a redis connection."""
        logger.debug(
            "Got %s as the redis_sentinels. Connecting to redis...",
            self.redis_sentinels,
        )

        logger.debug("Attempting to connect to redis...")
        try:
            client = self._get_redis_client(
                sentinels=self.redis_sentinels,
                master_name=self.redis_master_name,
                timeout=self.redis_sentinels_healthcheck_socket_timeout,
            )
            client.ping()
        except ConnectionRefusedError as e:
            self.add_error(
                ServiceUnavailable(
                    "Unable to connect to Redis: Connection was refused."
                ),
                e,
            )
        except exceptions.TimeoutError as e:
            self.add_error(
                ServiceUnavailable("Unable to connect to Redis: Timeout."), e
            )
        except exceptions.ConnectionError as e:
            self.add_error(
                ServiceUnavailable("Unable to connect to Redis: Connection Error"),
                e,
            )
        except BaseException as e:
            self.add_error(ServiceUnavailable("Unknown error"), e)
        else:
            logger.debug("Connection established. Redis is healthy.")

    @staticmethod
    def _get_redis_client(sentinels, master_name, timeout):
        sentinel = Sentinel(sentinels, socket_timeout=timeout)
        return sentinel.master_for(master_name, socket_timeout=timeout)
