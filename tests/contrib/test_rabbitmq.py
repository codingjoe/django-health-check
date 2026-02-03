"""Tests for RabbitMQ health check."""

import os
from unittest import mock

import pytest

pytest.importorskip("aio_pika")

import aio_pika

from health_check.contrib.rabbitmq import RabbitMQ as RabbitMQHealthCheck
from health_check.exceptions import ServiceUnavailable


class TestRabbitMQ:
    """Test RabbitMQ health check."""

    @pytest.mark.asyncio
    async def test_check_status__success(self):
        """Connect to RabbitMQ successfully."""
        with mock.patch(
            "health_check.contrib.rabbitmq.aio_pika.connect_robust"
        ) as mock_connect:
            mock_conn = mock.AsyncMock()
            mock_connect.return_value = mock_conn

            check = RabbitMQHealthCheck(amqp_url="amqp://guest:guest@localhost:5672//")
            result = await check.result
            assert result.error is None
            mock_conn.close.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_check_status__connection_refused(self):
        """Raise ServiceUnavailable when connection is refused."""
        with mock.patch(
            "health_check.contrib.rabbitmq.aio_pika.connect_robust"
        ) as mock_connect:
            mock_connect.side_effect = ConnectionRefusedError("refused")

            check = RabbitMQHealthCheck(amqp_url="amqp://guest:guest@localhost:5672//")
            result = await check.result
            assert result.error is not None
            assert isinstance(result.error, ServiceUnavailable)

    @pytest.mark.asyncio
    async def test_check_status__authentication_error(self):
        """Raise ServiceUnavailable on authentication failure."""
        with mock.patch(
            "health_check.contrib.rabbitmq.aio_pika.connect_robust"
        ) as mock_connect:
            mock_connect.side_effect = aio_pika.exceptions.ProbableAuthenticationError(
                "auth failed"
            )

            check = RabbitMQHealthCheck(amqp_url="amqp://guest:guest@localhost:5672//")
            result = await check.result
            assert result.error is not None
            assert isinstance(result.error, ServiceUnavailable)

    @pytest.mark.asyncio
    async def test_check_status__os_error(self):
        """Raise ServiceUnavailable on OS error."""
        with mock.patch(
            "health_check.contrib.rabbitmq.aio_pika.connect_robust"
        ) as mock_connect:
            mock_connect.side_effect = OSError("os error")

            check = RabbitMQHealthCheck(amqp_url="amqp://guest:guest@localhost:5672//")
            result = await check.result
            assert result.error is not None
            assert isinstance(result.error, ServiceUnavailable)

    @pytest.mark.asyncio
    async def test_check_status__unknown_error(self):
        """Raise ServiceUnavailable on unexpected exceptions."""
        with mock.patch(
            "health_check.contrib.rabbitmq.aio_pika.connect_robust"
        ) as mock_connect:
            mock_connect.side_effect = RuntimeError("unexpected")

            check = RabbitMQHealthCheck(amqp_url="amqp://guest:guest@localhost:5672//")
            result = await check.result
            assert result.error is not None
            assert isinstance(result.error, ServiceUnavailable)

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_check_status__real_rabbitmq(self):
        """Connect to real RabbitMQ server when BROKER_URL is configured."""
        broker_url = os.getenv("BROKER_URL") or os.getenv("RABBITMQ_URL")
        if not broker_url:
            pytest.skip("BROKER_URL/RABBITMQ_URL not set; skipping integration test")

        check = RabbitMQHealthCheck(amqp_url=broker_url)
        result = await check.result
        assert result.error is None
