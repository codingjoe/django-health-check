"""Tests for Redis health check."""

import os
from unittest import mock

import pytest

pytest.importorskip("redis")

from redis.exceptions import ConnectionError as RedisConnectionError
from redis.exceptions import TimeoutError as RedisTimeoutError

from health_check.contrib.redis import Redis as RedisHealthCheck
from health_check.contrib.redis import RedisSentinel as RedisSentinelHealthCheck
from health_check.exceptions import ServiceUnavailable


class TestRedis:
    """Test Redis health check."""

    def test_check_status__success(self):
        """Ping Redis successfully when connection succeeds."""
        with mock.patch("health_check.contrib.redis.from_url") as mock_from_url:
            mock_conn = mock.MagicMock()
            mock_from_url.return_value.__enter__.return_value = mock_conn
            mock_conn.ping.return_value = True

            check = RedisHealthCheck(redis_url="redis://localhost:6379")
            check.check_status()
            assert check.errors == []

    def test_check_status__connection_refused(self):
        """Raise ServiceUnavailable when connection is refused."""
        with mock.patch("health_check.contrib.redis.from_url") as mock_from_url:
            mock_from_url.return_value.__enter__.side_effect = ConnectionRefusedError(
                "refused"
            )

            check = RedisHealthCheck(redis_url="redis://localhost:6379")
            with pytest.raises(ServiceUnavailable):
                check.check_status()

    def test_check_status__timeout(self):
        """Raise ServiceUnavailable when connection times out."""
        with mock.patch("health_check.contrib.redis.from_url") as mock_from_url:
            mock_from_url.return_value.__enter__.side_effect = RedisTimeoutError(
                "timeout"
            )

            check = RedisHealthCheck(redis_url="redis://localhost:6379")
            with pytest.raises(ServiceUnavailable):
                check.check_status()

    def test_check_status__connection_error(self):
        """Raise ServiceUnavailable when connection fails."""
        with mock.patch("health_check.contrib.redis.from_url") as mock_from_url:
            mock_from_url.return_value.__enter__.side_effect = RedisConnectionError(
                "connection error"
            )

            check = RedisHealthCheck(redis_url="redis://localhost:6379")
            with pytest.raises(ServiceUnavailable):
                check.check_status()

    def test_check_status__unknown_error(self):
        """Raise ServiceUnavailable for unexpected exceptions."""
        with mock.patch("health_check.contrib.redis.from_url") as mock_from_url:
            mock_from_url.return_value.__enter__.side_effect = RuntimeError(
                "unexpected"
            )

            check = RedisHealthCheck(redis_url="redis://localhost:6379")
            with pytest.raises(ServiceUnavailable):
                check.check_status()

    @pytest.mark.integration
    def test_check_status__real_redis(self):
        """Ping real Redis server when REDIS_URL is configured."""
        redis_url = os.getenv("REDIS_URL")
        if not redis_url:
            pytest.skip("REDIS_URL not set; skipping integration test")

        check = RedisHealthCheck(redis_url=redis_url)
        check.check_status()
        assert check.errors == []


class TestRedisSentinel:
    """Test Redis Sentinel health check."""

    def test_check_status__success(self):
        """Ping Redis master successfully via Sentinel when connection succeeds."""
        with mock.patch("health_check.contrib.redis.Sentinel") as mock_sentinel_class:
            mock_sentinel = mock.MagicMock()
            mock_sentinel_class.return_value = mock_sentinel
            mock_master = mock.MagicMock()
            mock_sentinel.master_for.return_value = mock_master
            mock_master.ping.return_value = True

            check = RedisSentinelHealthCheck(
                sentinels=[("localhost", 26379)], service_name="mymaster"
            )
            check.check_status()
            assert check.errors == []
            mock_sentinel_class.assert_called_once_with([("localhost", 26379)])
            mock_sentinel.master_for.assert_called_once_with("mymaster")
            mock_master.ping.assert_called_once()

    def test_check_status__connection_refused(self):
        """Raise ServiceUnavailable when Sentinel connection is refused."""
        with mock.patch("health_check.contrib.redis.Sentinel") as mock_sentinel_class:
            mock_sentinel_class.side_effect = ConnectionRefusedError("refused")

            check = RedisSentinelHealthCheck(
                sentinels=[("localhost", 26379)], service_name="mymaster"
            )
            with pytest.raises(ServiceUnavailable):
                check.check_status()

    def test_check_status__timeout(self):
        """Raise ServiceUnavailable when Sentinel connection times out."""
        with mock.patch("health_check.contrib.redis.Sentinel") as mock_sentinel_class:
            mock_sentinel_class.side_effect = RedisTimeoutError("timeout")

            check = RedisSentinelHealthCheck(
                sentinels=[("localhost", 26379)], service_name="mymaster"
            )
            with pytest.raises(ServiceUnavailable):
                check.check_status()

    def test_check_status__connection_error(self):
        """Raise ServiceUnavailable when Sentinel connection fails."""
        with mock.patch("health_check.contrib.redis.Sentinel") as mock_sentinel_class:
            mock_sentinel_class.side_effect = RedisConnectionError("connection error")

            check = RedisSentinelHealthCheck(
                sentinels=[("localhost", 26379)], service_name="mymaster"
            )
            with pytest.raises(ServiceUnavailable):
                check.check_status()

    def test_check_status__unknown_error(self):
        """Raise ServiceUnavailable for unexpected exceptions."""
        with mock.patch("health_check.contrib.redis.Sentinel") as mock_sentinel_class:
            mock_sentinel_class.side_effect = RuntimeError("unexpected")

            check = RedisSentinelHealthCheck(
                sentinels=[("localhost", 26379)], service_name="mymaster"
            )
            with pytest.raises(ServiceUnavailable):
                check.check_status()

    def test_check_status__multiple_sentinels(self):
        """Connect to Redis via multiple Sentinel nodes."""
        with mock.patch("health_check.contrib.redis.Sentinel") as mock_sentinel_class:
            mock_sentinel = mock.MagicMock()
            mock_sentinel_class.return_value = mock_sentinel
            mock_master = mock.MagicMock()
            mock_sentinel.master_for.return_value = mock_master
            mock_master.ping.return_value = True

            sentinels = [
                ("localhost", 26379),
                ("localhost", 26380),
                ("localhost", 26381),
            ]
            check = RedisSentinelHealthCheck(
                sentinels=sentinels, service_name="mymaster"
            )
            check.check_status()
            assert check.errors == []
            mock_sentinel_class.assert_called_once_with(sentinels)

    def test_check_status__with_connection_options(self):
        """Pass connection options to Sentinel constructor."""
        with mock.patch("health_check.contrib.redis.Sentinel") as mock_sentinel_class:
            mock_sentinel = mock.MagicMock()
            mock_sentinel_class.return_value = mock_sentinel
            mock_master = mock.MagicMock()
            mock_sentinel.master_for.return_value = mock_master
            mock_master.ping.return_value = True

            connection_options = {"socket_connect_timeout": 5, "socket_timeout": 10}
            check = RedisSentinelHealthCheck(
                sentinels=[("localhost", 26379)],
                service_name="mymaster",
                sentinel_connection_options=connection_options,
            )
            check.check_status()
            assert check.errors == []
            mock_sentinel_class.assert_called_once_with(
                [("localhost", 26379)], **connection_options
            )

    def test_check_status__ping_failure(self):
        """Raise ServiceUnavailable when ping to master fails."""
        with mock.patch("health_check.contrib.redis.Sentinel") as mock_sentinel_class:
            mock_sentinel = mock.MagicMock()
            mock_sentinel_class.return_value = mock_sentinel
            mock_master = mock.MagicMock()
            mock_sentinel.master_for.return_value = mock_master
            mock_master.ping.side_effect = RedisConnectionError("ping failed")

            check = RedisSentinelHealthCheck(
                sentinels=[("localhost", 26379)], service_name="mymaster"
            )
            with pytest.raises(ServiceUnavailable):
                check.check_status()

    def test_init__empty_sentinels(self):
        """Raise ValueError when sentinels list is empty."""
        with pytest.raises(
            ValueError, match="At least one sentinel node must be provided"
        ):
            RedisSentinelHealthCheck(sentinels=[], service_name="mymaster")

    def test_init__empty_service_name(self):
        """Raise ValueError when service_name is empty."""
        with pytest.raises(ValueError, match="Service name must not be empty"):
            RedisSentinelHealthCheck(sentinels=[("localhost", 26379)], service_name="")
