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
    async def test_redis__ok(self, monkeypatch):
        """Ping Redis successfully when using redis_url parameter."""
        mock_client = mock.AsyncMock()
        mock_client.ping.return_value = True

        mock_from_url = mock.Mock(return_value=mock_client)
        monkeypatch.setattr(
            "health_check.contrib.redis.RedisClient.from_url", mock_from_url
        )

        check = RedisHealthCheck(redis_url="redis://localhost:6379")
        result = await check.get_result()
        assert result.error is None
        mock_from_url.assert_called_once_with("redis://localhost:6379")
        mock_client.ping.assert_called_once()
        mock_client.aclose.assert_called_once()

    @pytest.mark.asyncio
    async def test_redis__connection_refused(self, monkeypatch):
        """Raise ServiceUnavailable when connection is refused."""
        mock_client = mock.AsyncMock()
        mock_client.ping.side_effect = ConnectionRefusedError("refused")

        mock_from_url = mock.Mock(return_value=mock_client)
        monkeypatch.setattr(
            "health_check.contrib.redis.RedisClient.from_url", mock_from_url
        )

        check = RedisHealthCheck(redis_url="redis://localhost:6379")
        result = await check.get_result()
        assert result.error is not None
        assert isinstance(result.error, ServiceUnavailable)
        mock_client.aclose.assert_called_once()

    @pytest.mark.asyncio
    async def test_redis__timeout(self, monkeypatch):
        """Raise ServiceUnavailable when connection times out."""
        mock_client = mock.AsyncMock()
        mock_client.ping.side_effect = RedisTimeoutError("timeout")

        mock_from_url = mock.Mock(return_value=mock_client)
        monkeypatch.setattr(
            "health_check.contrib.redis.RedisClient.from_url", mock_from_url
        )

        check = RedisHealthCheck(redis_url="redis://localhost:6379")
        result = await check.get_result()
        assert result.error is not None
        assert isinstance(result.error, ServiceUnavailable)
        mock_client.aclose.assert_called_once()

    @pytest.mark.asyncio
    async def test_redis__connection_error(self, monkeypatch):
        """Raise ServiceUnavailable when connection fails."""
        mock_client = mock.AsyncMock()
        mock_client.ping.side_effect = RedisConnectionError("connection error")

        mock_from_url = mock.Mock(return_value=mock_client)
        monkeypatch.setattr(
            "health_check.contrib.redis.RedisClient.from_url", mock_from_url
        )

        check = RedisHealthCheck(redis_url="redis://localhost:6379")
        result = await check.get_result()
        assert result.error is not None
        assert isinstance(result.error, ServiceUnavailable)
        mock_client.aclose.assert_called_once()

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_redis__real_connection(self):
        """Ping real Redis server when REDIS_URL is configured."""
        redis_url = os.getenv("REDIS_URL")
        if not redis_url:
            pytest.skip("REDIS_URL not set; skipping integration test")

        check = RedisHealthCheck(redis_url=redis_url)
        result = await check.get_result()
        assert result.error is None

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_redis__real_sentinel(self):
        """Skip Sentinel test - not supported with URL-based configuration."""
        pytest.skip("Sentinel not supported with redis_url parameter")
