"""Tests for Redis health check."""

import os
from unittest import mock

import pytest

pytest.importorskip("redis")

from redis.exceptions import ConnectionError as RedisConnectionError
from redis.exceptions import TimeoutError as RedisTimeoutError

from health_check.contrib.redis import Redis as RedisHealthCheck
from health_check.exceptions import ServiceUnavailable


class TestRedisWithClient:
    """Test Redis health check with client parameter."""

    def test_check_status__success(self):
        """Ping Redis successfully when using client parameter."""
        mock_client = mock.MagicMock()
        mock_client.ping.return_value = True

        check = RedisHealthCheck(client=mock_client)
        check.check_status()
        assert check.errors == []
        mock_client.ping.assert_called_once()

    def test_check_status__connection_refused(self):
        """Raise ServiceUnavailable when connection is refused."""
        mock_client = mock.MagicMock()
        mock_client.ping.side_effect = ConnectionRefusedError("refused")

        check = RedisHealthCheck(client=mock_client)
        with pytest.raises(ServiceUnavailable):
            check.check_status()

    def test_check_status__timeout(self):
        """Raise ServiceUnavailable when connection times out."""
        mock_client = mock.MagicMock()
        mock_client.ping.side_effect = RedisTimeoutError("timeout")

        check = RedisHealthCheck(client=mock_client)
        with pytest.raises(ServiceUnavailable):
            check.check_status()

    def test_check_status__connection_error(self):
        """Raise ServiceUnavailable when connection fails."""
        mock_client = mock.MagicMock()
        mock_client.ping.side_effect = RedisConnectionError("connection error")

        check = RedisHealthCheck(client=mock_client)
        with pytest.raises(ServiceUnavailable):
            check.check_status()

    def test_check_status__unknown_error(self):
        """Raise ServiceUnavailable for unexpected exceptions."""
        mock_client = mock.MagicMock()
        mock_client.ping.side_effect = RuntimeError("unexpected")

        check = RedisHealthCheck(client=mock_client)
        with pytest.raises(ServiceUnavailable):
            check.check_status()

    def test_check_status__sentinel_client(self):
        """Work with Sentinel master client."""
        mock_sentinel_master = mock.MagicMock()
        mock_sentinel_master.ping.return_value = True

        check = RedisHealthCheck(client=mock_sentinel_master)
        check.check_status()
        assert check.errors == []
        mock_sentinel_master.ping.assert_called_once()

    def test_check_status__cluster_client(self):
        """Work with Cluster client."""
        mock_cluster_client = mock.MagicMock()
        mock_cluster_client.ping.return_value = True

        check = RedisHealthCheck(client=mock_cluster_client)
        check.check_status()
        assert check.errors == []
        mock_cluster_client.ping.assert_called_once()

    def test_check_status__no_client_or_url(self):
        """Raise ValueError when neither client nor redis_url is provided."""
        check = RedisHealthCheck()
        with pytest.raises(
            ValueError, match="Either 'client' or 'redis_url' must be provided"
        ):
            check.check_status()


class TestRedisWithURL:
    """Test Redis health check with deprecated redis_url parameter."""

    def test_check_status__success(self):
        """Ping Redis successfully when connection succeeds."""
        with mock.patch("health_check.contrib.redis.from_url") as mock_from_url:
            mock_conn = mock.MagicMock()
            mock_from_url.return_value.__enter__.return_value = mock_conn
            mock_conn.ping.return_value = True

            with pytest.warns(DeprecationWarning, match="redis_url.*deprecated"):
                check = RedisHealthCheck(redis_url="redis://localhost:6379")
                check.check_status()
            assert check.errors == []

    def test_check_status__connection_refused(self):
        """Raise ServiceUnavailable when connection is refused."""
        with mock.patch("health_check.contrib.redis.from_url") as mock_from_url:
            mock_from_url.return_value.__enter__.side_effect = ConnectionRefusedError(
                "refused"
            )

            with pytest.warns(DeprecationWarning):
                check = RedisHealthCheck(redis_url="redis://localhost:6379")
                with pytest.raises(ServiceUnavailable):
                    check.check_status()

    def test_check_status__timeout(self):
        """Raise ServiceUnavailable when connection times out."""
        with mock.patch("health_check.contrib.redis.from_url") as mock_from_url:
            mock_from_url.return_value.__enter__.side_effect = RedisTimeoutError(
                "timeout"
            )

            with pytest.warns(DeprecationWarning):
                check = RedisHealthCheck(redis_url="redis://localhost:6379")
                with pytest.raises(ServiceUnavailable):
                    check.check_status()

    def test_check_status__connection_error(self):
        """Raise ServiceUnavailable when connection fails."""
        with mock.patch("health_check.contrib.redis.from_url") as mock_from_url:
            mock_from_url.return_value.__enter__.side_effect = RedisConnectionError(
                "connection error"
            )

            with pytest.warns(DeprecationWarning):
                check = RedisHealthCheck(redis_url="redis://localhost:6379")
                with pytest.raises(ServiceUnavailable):
                    check.check_status()

    def test_check_status__unknown_error(self):
        """Raise ServiceUnavailable for unexpected exceptions."""
        with mock.patch("health_check.contrib.redis.from_url") as mock_from_url:
            mock_from_url.return_value.__enter__.side_effect = RuntimeError(
                "unexpected"
            )

            with pytest.warns(DeprecationWarning):
                check = RedisHealthCheck(redis_url="redis://localhost:6379")
                with pytest.raises(ServiceUnavailable):
                    check.check_status()

    @pytest.mark.integration
    def test_check_status__real_redis(self):
        """Ping real Redis server when REDIS_URL is configured."""
        redis_url = os.getenv("REDIS_URL")
        if not redis_url:
            pytest.skip("REDIS_URL not set; skipping integration test")

        with pytest.warns(DeprecationWarning):
            check = RedisHealthCheck(redis_url=redis_url)
            check.check_status()
        assert check.errors == []


class TestRedisIntegration:
    """Integration tests for Redis health check."""

    @pytest.mark.integration
    def test_check_status__real_redis_with_client(self):
        """Ping real Redis server using client parameter."""
        redis_url = os.getenv("REDIS_URL")
        if not redis_url:
            pytest.skip("REDIS_URL not set; skipping integration test")

        from redis import Redis as RedisClient

        # Parse URL to get connection params
        # For simplicity, we'll just use from_url but with client approach
        client = RedisClient.from_url(redis_url)
        check = RedisHealthCheck(client=client)
        check.check_status()
        assert check.errors == []
        client.close()

    @pytest.mark.integration
    def test_check_status__real_sentinel(self):
        """Ping real Redis Sentinel when configured."""
        sentinel_url = os.getenv("REDIS_SENTINEL_URL")
        if not sentinel_url:
            pytest.skip("REDIS_SENTINEL_URL not set; skipping integration test")

        from redis.sentinel import Sentinel

        # Parse sentinel configuration from environment
        sentinel_nodes = os.getenv("REDIS_SENTINEL_NODES", "localhost:26379")
        service_name = os.getenv("REDIS_SENTINEL_SERVICE_NAME", "mymaster")

        # Parse sentinel nodes from comma-separated list
        sentinels = []
        for node in sentinel_nodes.split(","):
            host, port = node.strip().split(":")
            sentinels.append((host, int(port)))

        # Create Sentinel and get master client
        sentinel = Sentinel(sentinels)
        master = sentinel.master_for(service_name)

        # Use the unified Redis check with the master client
        check = RedisHealthCheck(client=master)
        check.check_status()
        assert check.errors == []
