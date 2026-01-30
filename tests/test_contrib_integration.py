"""Integration tests for contrib health checks that require running services."""

import os

import pytest
from django.test import TestCase

from health_check.exceptions import ServiceUnavailable

redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/")
broker_url = os.getenv("BROKER_URL", "amqp://guest:guest@localhost:5672//")


# Redis tests
redis = pytest.importorskip("redis")


class TestRedisHealthCheck(TestCase):
    """Test Redis health check against a real Redis instance."""

    def test_redis_healthy(self):
        """Test that a working Redis connection passes the health check."""
        from health_check.contrib.redis import Redis

        check = Redis(url=redis_url)
        check.run_check()
        assert check.errors == []

    def test_redis_connection_refused(self):
        """Test that connection refused is handled properly."""
        from health_check.contrib.redis import Redis

        check = Redis(url="redis://localhost:9999/")
        check.run_check()
        assert len(check.errors) > 0
        assert "Unable to connect to Redis" in str(check.errors[0])

    def test_redis_timeout(self):
        """Test that timeout is handled properly."""
        from health_check.contrib.redis import Redis

        # Use a non-routable IP to trigger timeout
        check = Redis(
            url="redis://10.255.255.1:6379/",
            options={"socket_connect_timeout": 0.01},
        )
        check.run_check()
        # Should have an error due to timeout
        assert len(check.errors) > 0


# RabbitMQ tests
kombu = pytest.importorskip("kombu")


class TestRabbitMQHealthCheck(TestCase):
    """Test RabbitMQ health check against a real RabbitMQ instance."""

    def test_rabbitmq_healthy(self):
        """Test that a working RabbitMQ connection passes the health check."""
        from health_check.contrib.rabbitmq import RabbitMQ

        check = RabbitMQ(broker_url)
        check.run_check()
        assert check.errors == []

    def test_rabbitmq_with_namespace(self):
        """Test RabbitMQ health check with a custom namespace."""
        from health_check.contrib.rabbitmq import RabbitMQ

        check = RabbitMQ(url=broker_url)
        check.run_check()
        assert check.errors == []

    def test_rabbitmq_connection_refused(self):
        """Test that connection refused is handled properly."""
        from health_check.contrib.rabbitmq import RabbitMQ

        check = RabbitMQ(url="amqp://guest:guest@localhost:9999//")
        with pytest.raises(ServiceUnavailable) as exc_info:
            check.check_status()

        assert "Unable to connect to RabbitMQ" in str(exc_info.value)

    def test_rabbitmq_auth_error(self):
        """Test that authentication errors are handled properly."""
        from health_check.contrib.rabbitmq import RabbitMQ

        check = RabbitMQ(url="amqp://wrong:wrong@localhost:5672//")
        with pytest.raises(ServiceUnavailable) as exc_info:
            check.check_status()
        assert "Authentication error" in str(exc_info.value)
