"""Tests for Kafka health check."""

import os
from unittest import mock

import pytest

pytest.importorskip("confluent_kafka")

from confluent_kafka import KafkaException

from health_check.contrib.kafka import Kafka as KafkaHealthCheck
from health_check.exceptions import ServiceUnavailable


class TestKafka:
    """Test Kafka health check."""

    def test_check_status__success(self):
        """Connect to Kafka successfully when metadata is retrieved."""
        with mock.patch("health_check.contrib.kafka.Consumer") as mock_consumer_cls:
            mock_consumer = mock.MagicMock()
            mock_consumer_cls.return_value = mock_consumer

            # Mock metadata response
            mock_metadata = mock.MagicMock()
            mock_metadata.topics = {"test-topic": mock.MagicMock()}
            mock_consumer.list_topics.return_value = mock_metadata

            check = KafkaHealthCheck(bootstrap_servers="localhost:9092")
            check.check_status()
            assert check.errors == []

            # Verify consumer was closed
            mock_consumer.close.assert_called_once()

    def test_check_status__kafka_exception(self):
        """Raise ServiceUnavailable when KafkaException is raised."""
        with mock.patch("health_check.contrib.kafka.Consumer") as mock_consumer_cls:
            mock_consumer = mock.MagicMock()
            mock_consumer_cls.return_value = mock_consumer
            mock_consumer.list_topics.side_effect = KafkaException(
                "Failed to connect to broker"
            )

            check = KafkaHealthCheck(bootstrap_servers="localhost:9092")
            with pytest.raises(ServiceUnavailable) as exc_info:
                check.check_status()

            assert "Unable to connect to Kafka" in str(exc_info.value)

            # Verify consumer was closed
            mock_consumer.close.assert_called_once()

    def test_check_status__metadata_is_none(self):
        """Raise ServiceUnavailable when metadata is None."""
        with mock.patch("health_check.contrib.kafka.Consumer") as mock_consumer_cls:
            mock_consumer = mock.MagicMock()
            mock_consumer_cls.return_value = mock_consumer
            mock_consumer.list_topics.return_value = None

            check = KafkaHealthCheck(bootstrap_servers="localhost:9092")
            with pytest.raises(ServiceUnavailable) as exc_info:
                check.check_status()

            assert "Failed to retrieve Kafka metadata" in str(exc_info.value)

            # Verify consumer was closed
            mock_consumer.close.assert_called_once()

    def test_check_status__unknown_error(self):
        """Raise ServiceUnavailable on unexpected exceptions."""
        with mock.patch("health_check.contrib.kafka.Consumer") as mock_consumer_cls:
            mock_consumer = mock.MagicMock()
            mock_consumer_cls.return_value = mock_consumer
            mock_consumer.list_topics.side_effect = RuntimeError("unexpected")

            check = KafkaHealthCheck(bootstrap_servers="localhost:9092")
            with pytest.raises(ServiceUnavailable) as exc_info:
                check.check_status()

            assert "Unknown error connecting to Kafka" in str(exc_info.value)

            # Verify consumer was closed
            mock_consumer.close.assert_called_once()

    def test_check_status__custom_timeout(self):
        """Use custom timeout when provided."""
        with mock.patch("health_check.contrib.kafka.Consumer") as mock_consumer_cls:
            mock_consumer = mock.MagicMock()
            mock_consumer_cls.return_value = mock_consumer

            mock_metadata = mock.MagicMock()
            mock_metadata.topics = {}
            mock_consumer.list_topics.return_value = mock_metadata

            check = KafkaHealthCheck(bootstrap_servers="localhost:9092", timeout=5)
            check.check_status()

            # Verify timeout was used in consumer configuration
            consumer_config = mock_consumer_cls.call_args[0][0]
            assert consumer_config["session.timeout.ms"] == 5000
            assert consumer_config["socket.timeout.ms"] == 5000

            # Verify timeout was passed to list_topics
            mock_consumer.list_topics.assert_called_once_with(timeout=5)

    @pytest.mark.integration
    def test_check_status__real_kafka(self):
        """Connect to real Kafka server when KAFKA_BOOTSTRAP_SERVERS is configured."""
        kafka_servers = os.getenv("KAFKA_BOOTSTRAP_SERVERS")
        if not kafka_servers:
            pytest.skip("KAFKA_BOOTSTRAP_SERVERS not set; skipping integration test")

        check = KafkaHealthCheck(bootstrap_servers=kafka_servers)
        check.check_status()
        assert check.errors == []
