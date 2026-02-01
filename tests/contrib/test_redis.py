"""Tests for Redis health check."""

import os
from unittest import mock

import pytest

pytest.importorskip("redis")

from redis.exceptions import ConnectionError as RedisConnectionError
from redis.exceptions import TimeoutError as RedisTimeoutError

from health_check.contrib.redis import Redis as RedisHealthCheck
from health_check.contrib.redis import Sentinel as SentinelHealthCheck
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


class TestSentinel:
    """Test Sentinel health check."""

    def test_check_status__success(self):
        """Ping Redis master successfully via Sentinel when connection succeeds."""
        with mock.patch(
            "health_check.contrib.redis.RedisSentinelClient"
        ) as mock_sentinel_class:
            mock_sentinel = mock.MagicMock()
            mock_sentinel_class.return_value = mock_sentinel
            mock_master = mock.MagicMock()
            mock_sentinel.master_for.return_value = mock_master
            mock_master.ping.return_value = True

            check = SentinelHealthCheck(
                sentinels=[("localhost", 26379)], service_name="mymaster"
            )
            check.check_status()
            assert check.errors == []
            mock_sentinel_class.assert_called_once_with([("localhost", 26379)])
            mock_sentinel.master_for.assert_called_once_with("mymaster")
            mock_master.ping.assert_called_once()

    def test_check_status__connection_refused(self):
        """Raise ServiceUnavailable when Sentinel connection is refused."""
        with mock.patch(
            "health_check.contrib.redis.RedisSentinelClient"
        ) as mock_sentinel_class:
            mock_sentinel_class.side_effect = ConnectionRefusedError("refused")

            check = SentinelHealthCheck(
                sentinels=[("localhost", 26379)], service_name="mymaster"
            )
            with pytest.raises(ServiceUnavailable):
                check.check_status()

    def test_check_status__timeout(self):
        """Raise ServiceUnavailable when Sentinel connection times out."""
        with mock.patch(
            "health_check.contrib.redis.RedisSentinelClient"
        ) as mock_sentinel_class:
            mock_sentinel_class.side_effect = RedisTimeoutError("timeout")

            check = SentinelHealthCheck(
                sentinels=[("localhost", 26379)], service_name="mymaster"
            )
            with pytest.raises(ServiceUnavailable):
                check.check_status()

    def test_check_status__connection_error(self):
        """Raise ServiceUnavailable when Sentinel connection fails."""
        with mock.patch(
            "health_check.contrib.redis.RedisSentinelClient"
        ) as mock_sentinel_class:
            mock_sentinel_class.side_effect = RedisConnectionError("connection error")

            check = SentinelHealthCheck(
                sentinels=[("localhost", 26379)], service_name="mymaster"
            )
            with pytest.raises(ServiceUnavailable):
                check.check_status()

    def test_check_status__unknown_error(self):
        """Raise ServiceUnavailable for unexpected exceptions."""
        with mock.patch(
            "health_check.contrib.redis.RedisSentinelClient"
        ) as mock_sentinel_class:
            mock_sentinel_class.side_effect = RuntimeError("unexpected")

            check = SentinelHealthCheck(
                sentinels=[("localhost", 26379)], service_name="mymaster"
            )
            with pytest.raises(ServiceUnavailable):
                check.check_status()

    def test_check_status__multiple_sentinels(self):
        """Connect to Redis via multiple Sentinel nodes."""
        with mock.patch(
            "health_check.contrib.redis.RedisSentinelClient"
        ) as mock_sentinel_class:
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
            check = SentinelHealthCheck(sentinels=sentinels, service_name="mymaster")
            check.check_status()
            assert check.errors == []
            mock_sentinel_class.assert_called_once_with(sentinels)

    def test_check_status__with_connection_options(self):
        """Pass connection options to Sentinel constructor."""
        with mock.patch(
            "health_check.contrib.redis.RedisSentinelClient"
        ) as mock_sentinel_class:
            mock_sentinel = mock.MagicMock()
            mock_sentinel_class.return_value = mock_sentinel
            mock_master = mock.MagicMock()
            mock_sentinel.master_for.return_value = mock_master
            mock_master.ping.return_value = True

            connection_options = {"socket_connect_timeout": 5, "socket_timeout": 10}
            check = SentinelHealthCheck(
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
        with mock.patch(
            "health_check.contrib.redis.RedisSentinelClient"
        ) as mock_sentinel_class:
            mock_sentinel = mock.MagicMock()
            mock_sentinel_class.return_value = mock_sentinel
            mock_master = mock.MagicMock()
            mock_sentinel.master_for.return_value = mock_master
            mock_master.ping.side_effect = RedisConnectionError("ping failed")

            check = SentinelHealthCheck(
                sentinels=[("localhost", 26379)], service_name="mymaster"
            )
            with pytest.raises(ServiceUnavailable):
                check.check_status()

    @pytest.mark.integration
    def test_check_status__real_sentinel(self):
        """Ping real Redis Sentinel when REDIS_SENTINEL_URL is configured."""
        sentinel_url = os.getenv("REDIS_SENTINEL_URL")
        if not sentinel_url:
            pytest.skip("REDIS_SENTINEL_URL not set; skipping integration test")

        # Parse sentinel URL format: redis-sentinel://host:port/service_name
        # or use environment variables for sentinel nodes
        sentinel_nodes = os.getenv("REDIS_SENTINEL_NODES", "localhost:26379")
        service_name = os.getenv("REDIS_SENTINEL_SERVICE_NAME", "mymaster")

        # Parse sentinel nodes from comma-separated list
        sentinels = []
        for node in sentinel_nodes.split(","):
            host, port = node.strip().split(":")
            sentinels.append((host, int(port)))

        check = SentinelHealthCheck(sentinels=sentinels, service_name=service_name)
        check.check_status()
        assert check.errors == []
