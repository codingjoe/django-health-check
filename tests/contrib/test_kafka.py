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

    @pytest.mark.asyncio
    async def test_check_status__success(self):
        """Connect to Kafka successfully when topics are retrieved."""
        with mock.patch(
            "health_check.contrib.kafka.KafkaConsumer"
        ) as mock_consumer_cls:
            mock_consumer = mock.MagicMock()
            mock_consumer_cls.return_value = mock_consumer

            # Mock topics response
            mock_consumer.topics.return_value = {"test-topic", "another-topic"}

            check = KafkaHealthCheck(bootstrap_servers=["localhost:9092"])
            result = await check.result
            assert result.error is None

            # Verify consumer was closed
            mock_consumer.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_check_status__kafka_exception(self):
        """Raise ServiceUnavailable when KafkaError is raised."""
        with mock.patch(
            "health_check.contrib.kafka.KafkaConsumer"
        ) as mock_consumer_cls:
            mock_consumer = mock.MagicMock()
            mock_consumer_cls.return_value = mock_consumer
            mock_consumer.topics.side_effect = KafkaError("Failed to connect to broker")

            check = KafkaHealthCheck(bootstrap_servers=["localhost:9092"])
            result = await check.result
            assert result.error is not None
            assert isinstance(result.error, ServiceUnavailable)
            assert "Unable to connect to Kafka" in str(result.error)

            # Verify consumer was closed
            mock_consumer.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_check_status__topics_is_none(self):
        """Raise ServiceUnavailable when topics is None."""
        with mock.patch(
            "health_check.contrib.kafka.KafkaConsumer"
        ) as mock_consumer_cls:
            mock_consumer = mock.MagicMock()
            mock_consumer_cls.return_value = mock_consumer
            mock_consumer.topics.return_value = None

            check = KafkaHealthCheck(bootstrap_servers=["localhost:9092"])
            result = await check.result
            assert result.error is not None
            assert isinstance(result.error, ServiceUnavailable)
            assert "Failed to retrieve Kafka topics" in str(result.error)

            # Verify consumer was closed
            mock_consumer.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_check_status__unknown_error(self):
        """Raise ServiceUnavailable on unexpected exceptions."""
        with mock.patch(
            "health_check.contrib.kafka.KafkaConsumer"
        ) as mock_consumer_cls:
            mock_consumer = mock.MagicMock()
            mock_consumer_cls.return_value = mock_consumer
            mock_consumer.topics.side_effect = RuntimeError("unexpected")

            check = KafkaHealthCheck(bootstrap_servers=["localhost:9092"])
            result = await check.result
            assert result.error is not None
            assert isinstance(result.error, ServiceUnavailable)
            assert "Unknown error" in str(result.error)

            # Verify consumer was closed
            mock_consumer.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_check_status__custom_timeout(self):
        """Use custom timeout when provided."""
        with mock.patch(
            "health_check.contrib.kafka.KafkaConsumer"
        ) as mock_consumer_cls:
            mock_consumer = mock.MagicMock()
            mock_consumer_cls.return_value = mock_consumer

            mock_consumer.topics.return_value = set()

            check = KafkaHealthCheck(
                bootstrap_servers=["localhost:9092"],
                timeout=datetime.timedelta(seconds=5),
            )
            await check.result

            # Verify timeout was used in consumer configuration
            call_kwargs = mock_consumer_cls.call_args[1]
            assert call_kwargs["request_timeout_ms"] == 5000
            assert call_kwargs["connections_max_idle_ms"] == 6000

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_check_status__real_kafka(self):
        """Connect to real Kafka server when KAFKA_BOOTSTRAP_SERVERS is configured."""
        kafka_servers = os.getenv("KAFKA_BOOTSTRAP_SERVERS")
        if not kafka_servers:
            pytest.skip("KAFKA_BOOTSTRAP_SERVERS not set; skipping integration test")

        check = KafkaHealthCheck(bootstrap_servers=[kafka_servers])
        result = await check.result
        assert result.error is None
