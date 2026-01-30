"""RabbitMQ health check."""

import dataclasses
import logging

from amqp.exceptions import AccessRefused
from kombu import Connection

from health_check.base import HealthCheck
from health_check.exceptions import ServiceUnavailable

logger = logging.getLogger(__name__)


@dataclasses.dataclass
class RabbitMQ(HealthCheck):
    """
    Check RabbitMQ service by opening and closing a broker channel.

    Args:
        url (str): The URL of the RabbitMQ broker to connect to, e.g., 'amqp://guest:guest@localhost:5672//'.

    """

    url: str

    def check_status(self):
        logger.debug("Attempting to connect to %r...", self.url)
        try:
            # conn is used as a context to release opened resources later
            with Connection(self.url) as conn:
                conn.connect()  # exceptions may be raised upon calling connect
        except ConnectionRefusedError as e:
            raise ServiceUnavailable(
                "Unable to connect to RabbitMQ: Connection was refused."
            ) from e
        except AccessRefused as e:
            raise ServiceUnavailable(
                "Unable to connect to RabbitMQ: Authentication error."
            ) from e

        except OSError as e:
            raise ServiceUnavailable("IOError") from e

        except BaseException as e:
            raise ServiceUnavailable("Unknown error") from e
        else:
            logger.debug("Connection established. RabbitMQ is healthy.")
