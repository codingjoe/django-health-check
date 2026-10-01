"""RabbitMQ health check."""

import dataclasses
import datetime
import logging
import urllib.parse

import aio_pika

from health_check.base import HealthCheck
from health_check.exceptions import ServiceUnavailable

logger = logging.getLogger(__name__)


@dataclasses.dataclass
class RabbitMQ(HealthCheck):
    """
    Check RabbitMQ service by opening and closing a broker channel.

    Args:
        amqp_url (str): The URL of the RabbitMQ broker to connect to, e.g., 'amqp://guest:guest@localhost:5672//'.
        timeout: Timeout for the connection attempt.

    """

    amqp_url: str = dataclasses.field(repr=False)
    timeout: datetime.timedelta = dataclasses.field(
        default=datetime.timedelta(seconds=5), repr=False
    )

    def __repr__(self) -> str:
        arguments = ", ".join(
            f"{key}={value!r}" for key, value in self._connection_details().items()
        )
        return f"{self.__class__.__name__}({arguments})"

    @property
    def labels(self) -> dict[str, str]:
        return super().labels | {
            key: str(value) for key, value in self._connection_details().items()
        }

    def _connection_details(self) -> dict[str, str | int]:
        try:
            url = urllib.parse.urlsplit(self.amqp_url)
            details = {"scheme": url.scheme, "host": url.hostname, "port": url.port}
        except ValueError:
            return {}
        if not details["host"]:
            return {}
        return {key: value for key, value in details.items() if value}

    async def run(self):
        logger.debug("Attempting to connect to %r...", self)
        try:
            # conn is used as a context to release opened resources later
            connection = await aio_pika.connect_robust(
                self.amqp_url, timeout=self.timeout.total_seconds()
            )
            await connection.close()
        except ConnectionRefusedError as e:
            raise ServiceUnavailable(
                "Unable to connect to RabbitMQ: Connection was refused."
            ) from e
        except aio_pika.exceptions.ProbableAuthenticationError as e:
            raise ServiceUnavailable(
                "Unable to connect to RabbitMQ: Authentication error."
            ) from e
        except OSError as e:
            raise ServiceUnavailable("IOError") from e
        else:
            logger.debug("Connection established. RabbitMQ is healthy.")
