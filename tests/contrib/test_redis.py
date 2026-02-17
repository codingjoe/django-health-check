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
        """Ping Redis successfully when using client_factory parameter."""
        mock_client = mock.AsyncMock()
        mock_client.ping.return_value = True

        check = RedisHealthCheck(client_factory=lambda: mock_client)
        result = await check.get_result()
        assert result.error is None
        mock_client.ping.assert_called_once()
        mock_client.aclose.assert_called_once()

    @pytest.mark.asyncio
    async def test_redis__connection_refused(self):
        """Raise ServiceUnavailable when connection is refused."""
        mock_client = mock.AsyncMock()
        mock_client.ping.side_effect = ConnectionRefusedError("refused")

        check = RedisHealthCheck(client_factory=lambda: mock_client)
        result = await check.get_result()
        assert result.error is not None
        assert isinstance(result.error, ServiceUnavailable)
        mock_client.aclose.assert_called_once()

    @pytest.mark.asyncio
    async def test_redis__timeout(self):
        """Raise ServiceUnavailable when connection times out."""
        mock_client = mock.AsyncMock()
        mock_client.ping.side_effect = RedisTimeoutError("timeout")

        check = RedisHealthCheck(client_factory=lambda: mock_client)
        result = await check.get_result()
        assert result.error is not None
        assert isinstance(result.error, ServiceUnavailable)
        mock_client.aclose.assert_called_once()

    @pytest.mark.asyncio
    async def test_redis__connection_error(self):
        """Raise ServiceUnavailable when connection fails."""
        mock_client = mock.AsyncMock()
        mock_client.ping.side_effect = RedisConnectionError("connection error")

        check = RedisHealthCheck(client_factory=lambda: mock_client)
        result = await check.get_result()
        assert result.error is not None
        assert isinstance(result.error, ServiceUnavailable)
        mock_client.aclose.assert_called_once()

    @pytest.mark.asyncio
    async def test_redis__client_deprecated(self):
        """Verify DeprecationWarning is raised when using client parameter."""
        mock_client = mock.AsyncMock()
        mock_client.ping.return_value = True

        with pytest.warns(DeprecationWarning, match="client.*deprecated.*client_factory"):
            check = RedisHealthCheck(client=mock_client)

        result = await check.get_result()
        assert result.error is None
        mock_client.ping.assert_called_once()
        mock_client.aclose.assert_not_called()

    @pytest.mark.asyncio
    async def test_redis__factory_creates_new_client_per_request(self):
        """Verify client_factory creates a new client instance per request."""
        call_count = 0
        clients = []

        def factory():
            nonlocal call_count
            call_count += 1
            client = mock.AsyncMock()
            client.ping.return_value = True
            clients.append(client)
            return client

        check = RedisHealthCheck(client_factory=factory)

        # First request
        result1 = await check.get_result()
        assert result1.error is None
        assert call_count == 1, "Factory should be called once for first request"
        assert len(clients) == 1
        clients[0].ping.assert_called_once()
        clients[0].aclose.assert_called_once()

        # Second request
        result2 = await check.get_result()
        assert result2.error is None
        assert call_count == 2, "Factory should be called again for second request"
        assert len(clients) == 2
        assert clients[0] is not clients[1], "Each request should get a new client"
        clients[1].ping.assert_called_once()
        clients[1].aclose.assert_called_once()

    @pytest.mark.asyncio
    async def test_redis__client_not_closed_when_provided_directly(self):
        """Verify user-provided client is not closed by health check."""
        mock_client = mock.AsyncMock()
        mock_client.ping.return_value = True

        with pytest.warns(DeprecationWarning):
            check = RedisHealthCheck(client=mock_client)

        result = await check.get_result()
        assert result.error is None
        mock_client.ping.assert_called_once()
        mock_client.aclose.assert_not_called()

    @pytest.mark.asyncio
    async def test_redis__requires_client_or_factory(self):
        """Verify ValueError is raised when neither client nor factory is provided."""
        with pytest.raises(ValueError, match="Either 'client_factory' or 'client' must be provided"):
            RedisHealthCheck()

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_redis__real_connection(self):
        """Ping real Redis server when REDIS_URL is configured."""
        redis_url = os.getenv("REDIS_URL")
        if not redis_url:
            pytest.skip("REDIS_URL not set; skipping integration test")

        from redis.asyncio import Redis as RedisClient

        check = RedisHealthCheck(
            client_factory=lambda: RedisClient.from_url(redis_url)
        )
        result = await check.get_result()
        assert result.error is None

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_redis__real_sentinel(self):
        """Ping real Redis Sentinel when configured."""
        sentinel_url = os.getenv("REDIS_SENTINEL_URL")
        if not sentinel_url:
            pytest.skip("REDIS_SENTINEL_URL not set; skipping integration test")

        from redis.asyncio import Sentinel

        # Parse sentinel configuration from environment
        sentinel_nodes = os.getenv("REDIS_SENTINEL_NODES", "localhost:26379")
        service_name = os.getenv("REDIS_SENTINEL_SERVICE_NAME", "mymaster")

        # Parse sentinel nodes from comma-separated list
        sentinels = []
        for node in sentinel_nodes.split(","):
            host, port = node.strip().split(":")
            sentinels.append((host, int(port)))

        # Create factory that returns Sentinel master client
        def factory():
            sentinel = Sentinel(sentinels)
            return sentinel.master_for(service_name)

        check = RedisHealthCheck(client_factory=factory)
        result = await check.get_result()
        assert result.error is None
