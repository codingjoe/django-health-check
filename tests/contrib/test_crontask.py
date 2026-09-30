from unittest import mock

import pytest

pytest.importorskip("redis")

from django.test import override_settings
from redis.asyncio import Redis as RedisClient
from redis.exceptions import ConnectionError as RedisConnectionError

from health_check.contrib.crontask import Scheduler as CrontaskScheduler
from health_check.contrib.crontask import create_client_from_settings
from health_check.exceptions import ServiceUnavailable


class TestCrontask:
    """Test the django-crontask scheduler health check."""

    @pytest.mark.asyncio
    async def test_crontask__lock_present(self):
        """Report healthy when the crontask lock exists in Redis."""
        mock_client = mock.AsyncMock()
        mock_client.exists.return_value = 1

        check = CrontaskScheduler(client_factory=lambda: mock_client)
        result = await check.get_result()

        assert result.error is None
        mock_client.exists.assert_awaited_once_with("crontask-lock")
        mock_client.aclose.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_crontask__lock_absent(self):
        """Raise ServiceUnavailable when the crontask lock is missing."""
        mock_client = mock.AsyncMock()
        mock_client.exists.return_value = 0

        check = CrontaskScheduler(client_factory=lambda: mock_client)
        result = await check.get_result()

        assert result.error is not None
        assert isinstance(result.error, ServiceUnavailable)
        assert "No django-crontask scheduler is running." in str(result.error)
        mock_client.aclose.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_crontask__redis_error(self):
        """Raise ServiceUnavailable when Redis cannot be queried."""
        mock_client = mock.AsyncMock()
        mock_client.exists.side_effect = RedisConnectionError("connection refused")

        check = CrontaskScheduler(client_factory=lambda: mock_client)
        result = await check.get_result()

        assert result.error is not None
        assert isinstance(result.error, ServiceUnavailable)
        assert "Unable to query the crontask lock." in str(result.error)
        assert isinstance(result.error.__cause__, RedisConnectionError)
        mock_client.aclose.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_crontask__redis_url_not_configured(self):
        """Report unavailable when CRONTASK["REDIS_URL"] is not configured."""
        with override_settings(CRONTASK=None):
            result = await CrontaskScheduler().get_result()

        assert result.error is not None
        assert isinstance(result.error, ServiceUnavailable)
        assert "CRONTASK['REDIS_URL'] is not configured" in str(result.error)

    def test_crontask__factory_without_crontask_setting(self):
        """Raise ServiceUnavailable when the CRONTASK setting is absent."""
        with (
            override_settings(CRONTASK=None),
            pytest.raises(ServiceUnavailable, match=r"CRONTASK\['REDIS_URL'\]"),
        ):
            create_client_from_settings()

    def test_crontask__factory_without_redis_url(self):
        """Raise ServiceUnavailable when CRONTASK has no REDIS_URL."""
        with (
            override_settings(CRONTASK={"LOCK_TIMEOUT": 10}),
            pytest.raises(ServiceUnavailable, match=r"CRONTASK\['REDIS_URL'\]"),
        ):
            create_client_from_settings()

    @pytest.mark.asyncio
    async def test_crontask__factory_uses_configured_timeouts(self):
        """Build a client for CRONTASK["REDIS_URL"] with a one second I/O budget."""
        with override_settings(
            CRONTASK={"REDIS_URL": "redis://cache.example.com:6379/3"}
        ):
            client = create_client_from_settings()

        kwargs = client.connection_pool.connection_kwargs
        try:
            assert kwargs["host"] == "cache.example.com"
            assert kwargs["port"] == 6379
            assert kwargs["db"] == 3
            assert kwargs["socket_timeout"] == 1
            assert kwargs["socket_connect_timeout"] == 1
        finally:
            await client.aclose()

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_crontask__real_redis_lock_absent(self, redis_url):
        """Report unavailable when a real Redis holds no crontask lock."""
        client = RedisClient.from_url(redis_url)
        await client.delete("crontask-lock")
        await client.aclose()

        with override_settings(CRONTASK={"REDIS_URL": redis_url}):
            result = await CrontaskScheduler().get_result()

        assert result.error is not None
        assert isinstance(result.error, ServiceUnavailable)
        assert "No django-crontask scheduler is running." in str(result.error)

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_crontask__real_redis_lock_present(self, redis_url):
        """Report healthy when a real Redis holds the crontask lock."""
        client = RedisClient.from_url(redis_url)
        await client.set("crontask-lock", "test-token", px=10_000)
        try:
            with override_settings(CRONTASK={"REDIS_URL": redis_url}):
                result = await CrontaskScheduler().get_result()
        finally:
            await client.delete("crontask-lock")
            await client.aclose()

        assert result.error is None
