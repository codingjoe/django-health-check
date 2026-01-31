"""Kafka health check."""

import dataclasses
import datetime
import logging

from confluent_kafka import Consumer, KafkaException

from health_check.base import HealthCheck
from health_check.exceptions import ServiceUnavailable

logger = logging.getLogger(__name__)


@dataclasses.dataclass
class Kafka(HealthCheck):
    """
    Check Kafka service by connecting to a Kafka broker and listing topics.

    Args:
        bootstrap_servers: List of Kafka bootstrap servers, e.g., ['localhost:9092'].
        timeout: Timeout in seconds for the connection check.

    """

    bootstrap_servers: list[str]
    timeout: datetime.timedelta = dataclasses.field(
        default=datetime.timedelta(seconds=10), repr=False
    )

    def check_status(self):
        logger.debug(
            "Connecting to Kafka bootstrap servers %r ...",
            self.bootstrap_servers,
        )

        consumer = None
        try:
            # Create a consumer with minimal configuration for health check
            consumer = Consumer(
                {
                    "bootstrap.servers": self.bootstrap_servers,
                    "group.id": "health-check",
                    "session.timeout.ms": self.timeout.total_seconds() * 1000,
                    "socket.timeout.ms": self.timeout.total_seconds() * 1000,
                }
            )

            # Try to list topics to verify connection
            # This will raise an exception if Kafka is not available
            metadata = consumer.list_topics(timeout=self.timeout.total_seconds())

            if metadata is None:
                raise ServiceUnavailable("Failed to retrieve Kafka metadata.")

            logger.debug(
                "Connection established. Kafka is healthy. Found %d topics.",
                len(metadata.topics),
            )

        except KafkaException as e:
            raise ServiceUnavailable(f"Unable to connect to Kafka: {e}") from e
        except Exception as e:
            raise ServiceUnavailable(f"Unknown error connecting to Kafka: {e}") from e
        finally:
            if consumer is not None:
                consumer.close()
