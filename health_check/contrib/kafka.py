"""Kafka health check."""

import dataclasses
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
        bootstrap_servers: Comma-separated list of Kafka broker addresses,
                          e.g., 'localhost:9092' or 'broker1:9092,broker2:9092'.
        timeout: Timeout in seconds for the connection check (default: 10).

    """

    bootstrap_servers: str
    timeout: int = 10

    def check_status(self):
        logger.debug(
            "Got %s as bootstrap_servers. Connecting to Kafka...",
            self.bootstrap_servers,
        )

        consumer = None
        try:
            # Create a consumer with minimal configuration for health check
            consumer = Consumer(
                {
                    "bootstrap.servers": self.bootstrap_servers,
                    "group.id": "health-check",
                    "session.timeout.ms": self.timeout * 1000,
                    "socket.timeout.ms": self.timeout * 1000,
                }
            )

            # Try to list topics to verify connection
            # This will raise an exception if Kafka is not available
            metadata = consumer.list_topics(timeout=self.timeout)

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
