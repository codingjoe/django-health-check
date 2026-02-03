"""Kafka health check."""

import dataclasses
import datetime
import logging

from confluent_kafka.aio import AIOConsumer
from confluent_kafka.error import KafkaException

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

    async def run(self):
        logger.debug(
            "Connecting to Kafka bootstrap servers %r ...",
            self.bootstrap_servers,
        )

        # Create a consumer with minimal configuration for health check
        timeout_ms = int(self.timeout.total_seconds() * 1000)
        consumer = AIOConsumer(
            {
                "bootstrap.servers": ",".join(self.bootstrap_servers),
                "client.id": "health-check",
                "group.id": "health-check",
                "session.timeout.ms": timeout_ms,
                "socket.timeout.ms": timeout_ms,
            }
        )

        try:
            if not (
                (
                    cluster_metadata := await consumer.list_topics(
                        timeout=self.timeout.total_seconds()
                    )
                )
                and cluster_metadata.topics
            ):
                raise ServiceUnavailable("Failed to retrieve Kafka topics.")

        except KafkaException as e:
            raise ServiceUnavailable("Unable to connect") from e
        else:
            logger.debug(
                "Connection established. Kafka is healthy. Found %d topics.",
                len(cluster_metadata.topics),
            )
        finally:
            await consumer.close()
