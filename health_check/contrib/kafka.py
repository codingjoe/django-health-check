"""Kafka health check."""

import dataclasses
import datetime
import logging

from kafka import KafkaConsumer
from kafka.errors import KafkaError

from health_check.base import HealthCheck
from health_check.exceptions import ServiceUnavailable

logger = logging.getLogger(__name__)


@dataclasses.dataclass
class Kafka(HealthCheck):
    """
    Check Kafka service by connecting to a Kafka broker and listing topics.

    Args:
        bootstrap_servers: List of Kafka bootstrap servers, e.g., ['localhost:9092'].
        timeout: Timeout duration for the connection check as a datetime.timedelta.

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
            timeout_ms = int(self.timeout.total_seconds() * 1000)
            consumer = KafkaConsumer(
                bootstrap_servers=self.bootstrap_servers,
                client_id="health-check",
                request_timeout_ms=timeout_ms,
                # Note: connections_max_idle_ms must be larger than request_timeout_ms
                # We use a value slightly larger than request_timeout_ms
                connections_max_idle_ms=timeout_ms + 1000,
            )

            # Try to list topics to verify connection
            # This will raise an exception if Kafka is not available
            topics = consumer.topics()

            if topics is None:
                raise ServiceUnavailable("Failed to retrieve Kafka topics.")

            logger.debug(
                "Connection established. Kafka is healthy. Found %d topics.",
                len(topics),
            )

        except KafkaError as e:
            raise ServiceUnavailable(f"Unable to connect to Kafka: {e}") from e
        except ServiceUnavailable:
            raise
        except BaseException as e:
            raise ServiceUnavailable("Unknown error") from e
        finally:
            if consumer is not None:
                consumer.close()
