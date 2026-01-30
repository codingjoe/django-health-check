"""Tests for Redis health check."""

import os
from unittest import mock

import pytest

pytest.importorskip("redis")

from redis.exceptions import ConnectionError as RedisConnectionError
from redis.exceptions import TimeoutError as RedisTimeoutError

from health_check.contrib.redis import Redis as RedisHealthCheck
from health_check.exceptions import ServiceUnavailable


class TestRedis:
    """Test Redis health check."""

    def test_check_status__success(self):
        """Ping Redis successfully when connection succeeds."""
        with mock.patch("health_check.contrib.redis.from_url") as mock_from_url:
            mock_conn = mock.MagicMock()
            mock_from_url.return_value.__enter__.return_value = mock_conn
            mock_conn.ping.return_value = True

            check = RedisHealthCheck(url="redis://localhost:6379")
            check.check_status()
            assert check.errors == []

    def test_check_status__connection_refused(self):
        """Raise ServiceUnavailable when connection is refused."""
        with mock.patch("health_check.contrib.redis.from_url") as mock_from_url:
            mock_from_url.return_value.__enter__.side_effect = ConnectionRefusedError(
                "refused"
            )

            check = RedisHealthCheck(url="redis://localhost:6379")
            with pytest.raises(ServiceUnavailable):
                check.check_status()

    def test_check_status__timeout(self):
        """Raise ServiceUnavailable when connection times out."""
        with mock.patch("health_check.contrib.redis.from_url") as mock_from_url:
            mock_from_url.return_value.__enter__.side_effect = RedisTimeoutError(
                "timeout"
            )

            check = RedisHealthCheck(url="redis://localhost:6379")
            with pytest.raises(ServiceUnavailable):
                check.check_status()

    def test_check_status__connection_error(self):
        """Raise ServiceUnavailable when connection fails."""
        with mock.patch("health_check.contrib.redis.from_url") as mock_from_url:
            mock_from_url.return_value.__enter__.side_effect = RedisConnectionError(
                "connection error"
            )

            check = RedisHealthCheck(url="redis://localhost:6379")
            with pytest.raises(ServiceUnavailable):
                check.check_status()

    def test_check_status__unknown_error(self):
        """Raise ServiceUnavailable for unexpected exceptions."""
        with mock.patch("health_check.contrib.redis.from_url") as mock_from_url:
            mock_from_url.return_value.__enter__.side_effect = RuntimeError(
                "unexpected"
            )

            check = RedisHealthCheck(url="redis://localhost:6379")
            with pytest.raises(ServiceUnavailable):
                check.check_status()

    @pytest.mark.integration
    def test_check_status__real_redis(self):
        """Ping real Redis server when REDIS_URL is configured."""
        redis_url = os.getenv("REDIS_URL")
        if not redis_url:
            pytest.skip("REDIS_URL not set; skipping integration test")

        check = RedisHealthCheck(url=redis_url)
        check.check_status()
        assert check.errors == []
