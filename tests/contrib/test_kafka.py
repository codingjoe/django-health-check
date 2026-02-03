"""Tests for Kafka health check."""

import datetime
import os
from unittest import mock

import pytest

pytest.importorskip("confluent_kafka")

from confluent_kafka.error import KafkaError, KafkaException

from health_check.contrib.kafka import Kafka as KafkaHealthCheck
from health_check.exceptions import ServiceUnavailable


class TestKafka:
    """Test Kafka health check."""

    @pytest.mark.asyncio
    async def test_check_status__success(self):
        """Connect to Kafka successfully when topics are retrieved."""
        with mock.patch("health_check.contrib.kafka.AIOConsumer") as mock_consumer_cls:
            mock_consumer = mock.AsyncMock()
            mock_consumer_cls.return_value = mock_consumer

            # Mock cluster metadata response
            mock_metadata = mock.MagicMock()
            mock_metadata.topics = {"test-topic": mock.MagicMock()}
            mock_consumer.list_topics.return_value = mock_metadata

            check = KafkaHealthCheck(bootstrap_servers=["localhost:9092"])
            result = await check.get_result()
            assert result.error is None

            # Verify consumer was closed
            mock_consumer.close.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_check_status__kafka_exception(self):
        """Raise ServiceUnavailable when KafkaException is raised."""
        with mock.patch("health_check.contrib.kafka.AIOConsumer") as mock_consumer_cls:
            mock_consumer = mock.AsyncMock()
            mock_consumer_cls.return_value = mock_consumer

            kafka_error = KafkaError(1)  # Error code for broker not available
            mock_consumer.list_topics.side_effect = KafkaException(kafka_error)

            check = KafkaHealthCheck(bootstrap_servers=["localhost:9092"])
            result = await check.get_result()
            assert result.error is not None
            assert isinstance(result.error, ServiceUnavailable)
            assert "Unable to connect" in str(result.error)

            # Verify consumer was closed
            mock_consumer.close.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_check_status__topics_is_none(self):
        """Raise ServiceUnavailable when metadata is None."""
        with mock.patch("health_check.contrib.kafka.AIOConsumer") as mock_consumer_cls:
            mock_consumer = mock.AsyncMock()
            mock_consumer_cls.return_value = mock_consumer
            mock_consumer.list_topics.return_value = None

            check = KafkaHealthCheck(bootstrap_servers=["localhost:9092"])
            result = await check.get_result()
            assert result.error is not None
            assert isinstance(result.error, ServiceUnavailable)
            assert "Failed to retrieve Kafka topics" in str(result.error)

            # Verify consumer was closed
            mock_consumer.close.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_check_status__custom_timeout(self):
        """Use custom timeout when provided."""
        with mock.patch("health_check.contrib.kafka.AIOConsumer") as mock_consumer_cls:
            mock_consumer = mock.AsyncMock()
            mock_consumer_cls.return_value = mock_consumer

            mock_metadata = mock.MagicMock()
            mock_metadata.topics = {}
            mock_consumer.list_topics.return_value = mock_metadata

            check = KafkaHealthCheck(
                bootstrap_servers=["localhost:9092"],
                timeout=datetime.timedelta(seconds=5),
            )
            await check.get_result()

            # Verify timeout was used in consumer configuration
            call_kwargs = mock_consumer_cls.call_args[0][0]
            assert call_kwargs["session.timeout.ms"] == 5000
            assert call_kwargs["socket.timeout.ms"] == 5000

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_check_status__real_kafka(self):
        """Connect to real Kafka server when KAFKA_BOOTSTRAP_SERVERS is configured."""
        kafka_servers = os.getenv("KAFKA_BOOTSTRAP_SERVERS")
        if not kafka_servers:
            pytest.skip("KAFKA_BOOTSTRAP_SERVERS not set; skipping integration test")

        check = KafkaHealthCheck(bootstrap_servers=kafka_servers.split(","))
        result = await check.get_result()
        assert result.error
        assert isinstance(result.error, ServiceUnavailable)
        assert "Failed to retrieve Kafka topics." in str(result.error)
