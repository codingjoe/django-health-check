"""Kafka health check."""

import dataclasses
import datetime
import logging

from confluent_kafka import Consumer, KafkaError, KafkaException

from health_check.base import HealthCheck
from health_check.exceptions import ServiceUnavailable

logger = logging.getLogger(__name__)


@dataclasses.dataclass
class Kafka(HealthCheck):
    """
    Check Kafka service by connecting to a Kafka broker and listing topics.

    Args:
        bootstrap_servers: Comma-separated list of Kafka bootstrap servers, e.g., 'localhost:9092'.
        timeout: Timeout duration for the connection check as a datetime.timedelta.

    """

    bootstrap_servers: str
    timeout: datetime.timedelta = dataclasses.field(
        default=datetime.timedelta(seconds=10), repr=False
    )

    def run(self):
        # Note: confluent_kafka's Consumer operations are synchronous/blocking.
        # This check will be automatically executed in a thread pool via
        # asyncio.to_thread() by the base class.
        logger.debug(
            "Connecting to Kafka bootstrap servers %r ...",
            self.bootstrap_servers,
        )

        consumer = None
        try:
            # Create a consumer with minimal configuration for health check
            timeout_ms = int(self.timeout.total_seconds() * 1000)
            consumer = Consumer(
                {
                    "bootstrap.servers": self.bootstrap_servers,
                    "client.id": "health-check",
                    "group.id": "health-check",
                    "session.timeout.ms": timeout_ms,
                    "socket.timeout.ms": timeout_ms,
                }
            )

            # Try to list topics to verify connection
            # This will raise an exception if Kafka is not available
            cluster_metadata = consumer.list_topics(
                timeout=self.timeout.total_seconds()
            )

            if cluster_metadata is None or cluster_metadata.topics is None:
                raise ServiceUnavailable("Failed to retrieve Kafka topics.")

            logger.debug(
                "Connection established. Kafka is healthy. Found %d topics.",
                len(cluster_metadata.topics),
            )

        except KafkaException as e:
            kafka_error = e.args[0] if e.args else None
            if isinstance(kafka_error, KafkaError):
                raise ServiceUnavailable(
                    f"Unable to connect to Kafka: {kafka_error.str()}"
                ) from e
            raise ServiceUnavailable(f"Unable to connect to Kafka: {e}") from e
        except ServiceUnavailable:
            raise
        finally:
            if consumer is not None:
                consumer.close()
