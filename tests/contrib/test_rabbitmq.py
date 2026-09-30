"""Tests for RabbitMQ health check."""

import logging
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
            result = await check.get_result()
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
            result = await check.get_result()
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
            result = await check.get_result()
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
            result = await check.get_result()
            assert result.error is not None
            assert isinstance(result.error, ServiceUnavailable)

    @pytest.mark.asyncio
    async def test_check_status__unknown_error(self):
        """Unexpected exceptions are caught by base class and logged."""
        with mock.patch(
            "health_check.contrib.rabbitmq.aio_pika.connect_robust"
        ) as mock_connect:
            mock_connect.side_effect = RuntimeError("unexpected")

            check = RabbitMQHealthCheck(amqp_url="amqp://guest:guest@localhost:5672//")
            result = await check.get_result()
            assert result.error is not None
            # Base class catches unexpected exceptions and converts to HealthCheckException
            assert "unknown error" in str(result.error)

    @pytest.mark.asyncio
    async def test_check_status__debug_log_excludes_credentials(self, caplog):
        """Debug logs never contain the broker credentials."""
        with (
            mock.patch(
                "health_check.contrib.rabbitmq.aio_pika.connect_robust"
            ) as mock_connect,
            caplog.at_level(logging.DEBUG, logger="health_check.contrib.rabbitmq"),
        ):
            mock_connect.return_value = mock.AsyncMock()
            check = RabbitMQHealthCheck(
                amqp_url="amqps://admin:supersecret@rabbit.example.com:5671//"
            )
            await check.get_result()
        assert "supersecret" not in caplog.text
        assert "host='rabbit.example.com'" in caplog.text

    def test_rabbitmq__repr_excludes_credentials(self):
        """Verify repr shows only scheme, host and port."""
        check = RabbitMQHealthCheck(
            amqp_url="amqps://admin:supersecret@rabbit.example.com:5671//"
        )
        assert (
            repr(check)
            == "RabbitMQ(scheme='amqps', host='rabbit.example.com', port=5671)"
        )

    def test_rabbitmq__labels_exclude_credentials(self):
        """Verify labels show only scheme, host and port."""
        check = RabbitMQHealthCheck(
            amqp_url="amqps://admin:supersecret@rabbit.example.com:5671//"
        )
        assert check.labels == {
            "check": "RabbitMQ",
            "scheme": "amqps",
            "host": "rabbit.example.com",
            "port": "5671",
        }

    def test_rabbitmq__labels_without_port(self):
        """Verify labels omit a missing port."""
        check = RabbitMQHealthCheck(amqp_url="amqp://rabbit.example.com//")
        assert check.labels == {
            "check": "RabbitMQ",
            "scheme": "amqp",
            "host": "rabbit.example.com",
        }

    def test_rabbitmq__labels_invalid_url(self):
        """Verify labels and repr fall back for an unparsable broker URL."""
        check = RabbitMQHealthCheck(amqp_url="amqp://rabbit.example.com:invalid//")
        assert check.labels == {"check": "RabbitMQ"}
        assert repr(check) == "RabbitMQ()"

    def test_rabbitmq__labels_without_scheme(self):
        """Verify labels never report credentials of a relative URL as scheme."""
        check = RabbitMQHealthCheck(
            amqp_url="admin:supersecret@rabbit.example.com:5672//"
        )
        assert check.labels == {"check": "RabbitMQ"}
        assert repr(check) == "RabbitMQ()"

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_check_status__real_rabbitmq(self, rabbitmq_url):
        """Connect to a real RabbitMQ server."""
        check = RabbitMQHealthCheck(amqp_url=rabbitmq_url)
        result = await check.get_result()
        assert result.error is None
