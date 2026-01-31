"""Tests for Kafka health check."""

import datetime
import os
from unittest import mock

import pytest

pytest.importorskip("kafka")

from kafka.errors import KafkaError

from health_check.contrib.kafka import Kafka as KafkaHealthCheck
from health_check.exceptions import ServiceUnavailable


class TestKafka:
    """Test Kafka health check."""

    def test_check_status__success(self):
        """Connect to Kafka successfully when topics are retrieved."""
        with mock.patch("health_check.contrib.kafka.KafkaConsumer") as mock_consumer_cls:
            mock_consumer = mock.MagicMock()
            mock_consumer_cls.return_value = mock_consumer

            # Mock topics response
            mock_consumer.topics.return_value = {"test-topic", "another-topic"}

            check = KafkaHealthCheck(bootstrap_servers=["localhost:9092"])
            check.check_status()
            assert check.errors == []

            # Verify consumer was closed
            mock_consumer.close.assert_called_once()

    def test_check_status__kafka_exception(self):
        """Raise ServiceUnavailable when KafkaError is raised."""
        with mock.patch("health_check.contrib.kafka.KafkaConsumer") as mock_consumer_cls:
            mock_consumer = mock.MagicMock()
            mock_consumer_cls.return_value = mock_consumer
            mock_consumer.topics.side_effect = KafkaError(
                "Failed to connect to broker"
            )

            check = KafkaHealthCheck(bootstrap_servers=["localhost:9092"])
            with pytest.raises(ServiceUnavailable) as exc_info:
                check.check_status()

            assert "Unable to connect to Kafka" in str(exc_info.value)

            # Verify consumer was closed
            mock_consumer.close.assert_called_once()

    def test_check_status__topics_is_none(self):
        """Raise ServiceUnavailable when topics is None."""
        with mock.patch("health_check.contrib.kafka.KafkaConsumer") as mock_consumer_cls:
            mock_consumer = mock.MagicMock()
            mock_consumer_cls.return_value = mock_consumer
            mock_consumer.topics.return_value = None

            check = KafkaHealthCheck(bootstrap_servers=["localhost:9092"])
            with pytest.raises(ServiceUnavailable) as exc_info:
                check.check_status()

            assert "Failed to retrieve Kafka topics" in str(exc_info.value)

            # Verify consumer was closed
            mock_consumer.close.assert_called_once()

    def test_check_status__unknown_error(self):
        """Raise ServiceUnavailable on unexpected exceptions."""
        with mock.patch("health_check.contrib.kafka.KafkaConsumer") as mock_consumer_cls:
            mock_consumer = mock.MagicMock()
            mock_consumer_cls.return_value = mock_consumer
            mock_consumer.topics.side_effect = RuntimeError("unexpected")

            check = KafkaHealthCheck(bootstrap_servers=["localhost:9092"])
            with pytest.raises(ServiceUnavailable) as exc_info:
                check.check_status()

            assert "Unknown error connecting to Kafka" in str(exc_info.value)

            # Verify consumer was closed
            mock_consumer.close.assert_called_once()

    def test_check_status__custom_timeout(self):
        """Use custom timeout when provided."""
        with mock.patch("health_check.contrib.kafka.KafkaConsumer") as mock_consumer_cls:
            mock_consumer = mock.MagicMock()
            mock_consumer_cls.return_value = mock_consumer

            mock_consumer.topics.return_value = set()

            check = KafkaHealthCheck(
                bootstrap_servers=["localhost:9092"],
                timeout=datetime.timedelta(seconds=5),
            )
            check.check_status()

            # Verify timeout was used in consumer configuration
            call_kwargs = mock_consumer_cls.call_args[1]
            assert call_kwargs["request_timeout_ms"] == 5000
            assert call_kwargs["session_timeout_ms"] == 5000
            assert call_kwargs["connections_max_idle_ms"] == 5000

    @pytest.mark.integration
    def test_check_status__real_kafka(self):
        """Connect to real Kafka server when KAFKA_BOOTSTRAP_SERVERS is configured."""
        kafka_servers = os.getenv("KAFKA_BOOTSTRAP_SERVERS")
        if not kafka_servers:
            pytest.skip("KAFKA_BOOTSTRAP_SERVERS not set; skipping integration test")

        check = KafkaHealthCheck(bootstrap_servers=[kafka_servers])
        check.check_status()
        assert check.errors == []
