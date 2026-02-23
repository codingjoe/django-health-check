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

        with pytest.warns(
            DeprecationWarning, match="client.*deprecated.*client_factory"
        ):
            check = RedisHealthCheck(client=mock_client)

        result = await check.get_result()
        assert result.error is None
        mock_client.ping.assert_called_once()
        # User-provided client should NOT be closed by the health check
        mock_client.aclose.assert_not_called()

    @pytest.mark.asyncio
    async def test_redis__factory_called_for_each_result(self):
        """Verify client_factory is called per result and each client is closed."""
        call_count = 0
        created_clients = []

        def factory():
            nonlocal call_count, created_clients
            call_count += 1
            client = mock.AsyncMock()
            client.ping.return_value = True
            created_clients.append(client)
            return client

        check = RedisHealthCheck(client_factory=factory)
        # Factory should not be called eagerly during initialization
        assert call_count == 0, "Factory should not be called during initialization"

        # Each request should use a newly created client
        result1 = await check.get_result()
        assert result1.error is None
        assert call_count == 1, "Factory should be called once for first request"

        result2 = await check.get_result()
        assert result2.error is None
        assert call_count == 2, "Factory should be called again for second request"

        # Ensure a distinct client was created and closed for each result
        assert len(created_clients) == 2
        assert created_clients[0] is not created_clients[1], (
            "Each request should create a distinct client"
        )
        created_clients[0].aclose.assert_called_once()
        created_clients[1].aclose.assert_called_once()

    @pytest.mark.asyncio
    async def test_redis__client_not_closed_when_user_provided(self):
        """Verify user-provided client is NOT closed by health check."""
        mock_client = mock.AsyncMock()
        mock_client.ping.return_value = True

        with pytest.warns(DeprecationWarning):
            check = RedisHealthCheck(client=mock_client)

        result = await check.get_result()
        assert result.error is None
        mock_client.ping.assert_called_once()
        # User is responsible for closing their own client
        mock_client.aclose.assert_not_called()

    @pytest.mark.asyncio
    async def test_redis__validation_both_params(self):
        """Verify error when both client and client_factory are provided."""
        mock_client = mock.AsyncMock()
        with pytest.raises(
            ValueError, match="Provide exactly one of `client` or `client_factory`"
        ):
            RedisHealthCheck(client=mock_client, client_factory=lambda: mock_client)

    @pytest.mark.asyncio
    async def test_redis__validation_neither_param(self):
        """Verify error when neither client nor client_factory is provided."""
        with pytest.raises(
            ValueError, match="You must provide either `client`.*or `client_factory`"
        ):
            RedisHealthCheck()

    def test_redis__repr_standard_client(self):
        """Verify repr includes host and db for a standard Redis client."""
        from redis.asyncio import Redis as RedisClient

        check = RedisHealthCheck(
            client_factory=lambda: RedisClient(host="myhost", port=6379, db=2)
        )
        assert repr(check) == "Redis(client=RedisClient(host=myhost, db=2))"

    def test_redis__repr_from_url(self):
        """Verify repr includes host and db when client is created via from_url."""
        from redis.asyncio import Redis as RedisClient

        check = RedisHealthCheck(
            client_factory=lambda: RedisClient.from_url(
                "redis://cache.example.com:6379/3"
            )
        )
        assert "host=cache.example.com" in repr(check), (
            "repr should include the host from the Redis URL"
        )
        assert "db=3" in repr(check), (
            "repr should include the db from the Redis URL"
        )

    def test_redis__repr_deprecated_client(self):
        """Verify repr includes host and db when using deprecated client parameter."""
        from redis.asyncio import Redis as RedisClient

        with pytest.warns(DeprecationWarning):
            check = RedisHealthCheck(client=RedisClient(host="oldhost", port=6379, db=5))
        assert "host=oldhost" in repr(check), (
            "repr should include the host from the deprecated client"
        )
        assert "db=5" in repr(check), (
            "repr should include the db from the deprecated client"
        )

    def test_redis__repr_sentinel_client(self):
        """Verify repr falls back gracefully for Sentinel clients without host/db."""
        from redis.asyncio import Sentinel

        check = RedisHealthCheck(
            client_factory=lambda: Sentinel([("localhost", 26379)]).master_for(
                "mymaster"
            )
        )
        # Sentinel clients don't expose host/db in connection_pool.connection_kwargs
        # __repr__ should fall back to the default dataclass repr without raising
        assert repr(check) == "Redis()"

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_redis__real_connection(self):
        """Ping real Redis server when REDIS_URL is configured."""
        redis_url = os.getenv("REDIS_URL")
        if not redis_url:
            pytest.skip("REDIS_URL not set; skipping integration test")

        from redis.asyncio import Redis as RedisClient

        check = RedisHealthCheck(client_factory=lambda: RedisClient.from_url(redis_url))
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
