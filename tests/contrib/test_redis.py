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

    @pytest.mark.asyncio
    async def test_redis__ok(self):
        """Ping Redis successfully when using client parameter."""
        mock_client = mock.AsyncMock()
        mock_client.ping.return_value = True

        check = RedisHealthCheck(client=mock_client)
        result = await check.result
        assert result.error is None
        mock_client.ping.assert_called_once()

    @pytest.mark.asyncio
    async def test_redis__connection_refused(self):
        """Raise ServiceUnavailable when connection is refused."""
        mock_client = mock.AsyncMock()
        mock_client.ping.side_effect = ConnectionRefusedError("refused")

        check = RedisHealthCheck(client=mock_client)
        result = await check.result
        assert result.error is not None
        assert isinstance(result.error, ServiceUnavailable)

    @pytest.mark.asyncio
    async def test_redis__timeout(self):
        """Raise ServiceUnavailable when connection times out."""
        mock_client = mock.AsyncMock()
        mock_client.ping.side_effect = RedisTimeoutError("timeout")

        check = RedisHealthCheck(client=mock_client)
        result = await check.result
        assert result.error is not None
        assert isinstance(result.error, ServiceUnavailable)

    @pytest.mark.asyncio
    async def test_redis__connection_error(self):
        """Raise ServiceUnavailable when connection fails."""
        mock_client = mock.AsyncMock()
        mock_client.ping.side_effect = RedisConnectionError("connection error")

        check = RedisHealthCheck(client=mock_client)
        result = await check.result
        assert result.error is not None
        assert isinstance(result.error, ServiceUnavailable)

    @pytest.mark.asyncio
    async def test_redis__unknown_error(self):
        """Raise ServiceUnavailable for unexpected exceptions."""
        mock_client = mock.AsyncMock()
        mock_client.ping.side_effect = RuntimeError("unexpected")

        check = RedisHealthCheck(client=mock_client)
        result = await check.result
        assert result.error is not None
        assert isinstance(result.error, ServiceUnavailable)

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_redis__real_connection(self):
        """Ping real Redis server when REDIS_URL is configured."""
        redis_url = os.getenv("REDIS_URL")
        if not redis_url:
            pytest.skip("REDIS_URL not set; skipping integration test")

        from redis import Redis as RedisClient

        client = RedisClient.from_url(redis_url)
        check = RedisHealthCheck(client=client)
        result = await check.result
        assert result.error is None
        client.close()

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_redis__real_sentinel(self):
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
        result = await check.result
        assert result.error is None
