"""Tests for RabbitMQ health check."""

import os
from unittest import mock

import pytest

pytest.importorskip("kombu")

from amqp.exceptions import AccessRefused

from health_check.contrib.rabbitmq import RabbitMQ as RabbitMQHealthCheck
from health_check.exceptions import ServiceUnavailable


class TestRabbitMQ:
    """Test RabbitMQ health check."""

    def test_check_status__success(self):
        """Connect to RabbitMQ successfully."""
        with mock.patch("health_check.contrib.rabbitmq.Connection") as mock_conn_cls:
            mock_conn = mock.MagicMock()
            mock_conn.__enter__.return_value = mock_conn
            mock_conn.__exit__.return_value = False
            mock_conn.connect.return_value = True
            mock_conn_cls.return_value = mock_conn

            check = RabbitMQHealthCheck(url="amqp://guest:guest@localhost:5672//")
            check.check_status()
            assert check.errors == []

    def test_check_status__connection_refused(self):
        """Raise ServiceUnavailable when connection is refused."""
        with mock.patch("health_check.contrib.rabbitmq.Connection") as mock_conn_cls:
            mock_conn = mock.MagicMock()
            mock_conn.__enter__.side_effect = ConnectionRefusedError("refused")
            mock_conn.__exit__.return_value = False
            mock_conn_cls.return_value = mock_conn

            check = RabbitMQHealthCheck(url="amqp://guest:guest@localhost:5672//")
            check.run_check()
            assert len(check.errors) == 1
            assert isinstance(check.errors[0], ServiceUnavailable)

    def test_check_status__authentication_error(self):
        """Raise ServiceUnavailable on authentication failure."""
        with mock.patch("health_check.contrib.rabbitmq.Connection") as mock_conn_cls:
            mock_conn = mock.MagicMock()
            mock_conn.__enter__.side_effect = AccessRefused("auth failed")
            mock_conn.__exit__.return_value = False
            mock_conn_cls.return_value = mock_conn

            check = RabbitMQHealthCheck(url="amqp://guest:guest@localhost:5672//")
            check.run_check()
            assert len(check.errors) == 1
            assert isinstance(check.errors[0], ServiceUnavailable)

    def test_check_status__os_error(self):
        """Raise ServiceUnavailable on OS error."""
        with mock.patch("health_check.contrib.rabbitmq.Connection") as mock_conn_cls:
            mock_conn = mock.MagicMock()
            mock_conn.__enter__.side_effect = OSError("os error")
            mock_conn.__exit__.return_value = False
            mock_conn_cls.return_value = mock_conn

            check = RabbitMQHealthCheck(url="amqp://guest:guest@localhost:5672//")
            check.run_check()
            assert len(check.errors) == 1
            assert isinstance(check.errors[0], ServiceUnavailable)

    def test_check_status__unknown_error(self):
        """Raise ServiceUnavailable on unexpected exceptions."""
        with mock.patch("health_check.contrib.rabbitmq.Connection") as mock_conn_cls:
            mock_conn = mock.MagicMock()
            mock_conn.__enter__.side_effect = RuntimeError("unexpected")
            mock_conn.__exit__.return_value = False
            mock_conn_cls.return_value = mock_conn

            check = RabbitMQHealthCheck(url="amqp://guest:guest@localhost:5672//")
            check.run_check()
            assert len(check.errors) == 1
            assert isinstance(check.errors[0], ServiceUnavailable)

    @pytest.mark.integration
    def test_check_status__real_rabbitmq(self):
        """Connect to real RabbitMQ server when BROKER_URL is configured."""
        broker_url = os.getenv("BROKER_URL") or os.getenv("RABBITMQ_URL")
        if not broker_url:
            pytest.skip("BROKER_URL/RABBITMQ_URL not set; skipping integration test")

        check = RabbitMQHealthCheck(url=broker_url)
        check.check_status()
        assert check.errors == []
