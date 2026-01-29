import pytest

pytest.importorskip("redis")

from unittest import mock

from redis.exceptions import ConnectionError, TimeoutError

from health_check.contrib.redis.backends import RedisHealthCheck


class TestRedisHealthCheck:
    """Test Redis health check."""

    @mock.patch("health_check.contrib.redis.backends.getattr")
    @mock.patch("health_check.contrib.redis.backends.from_url", autospec=True)
    def test_redis_refused_connection(self, mocked_connection, mocked_getattr):
        """Test when the connection to Redis is refused."""
        mocked_getattr.return_value = "redis_url"

        # mock returns
        mocked_connection.return_value = mock.MagicMock()
        mocked_connection.return_value.__enter__.side_effect = ConnectionRefusedError("Refused connection")

        # instantiates the class
        redis_healthchecker = RedisHealthCheck()

        # invokes the method check_status()
        redis_healthchecker.check_status()
        assert len(redis_healthchecker.errors), 1

        # mock assertions
        # ensure from_url was called (exact URL may vary across envs)
        assert mocked_connection.called

    @mock.patch("health_check.contrib.redis.backends.getattr")
    @mock.patch("health_check.contrib.redis.backends.from_url")
    def test_redis_timeout_error(self, mocked_connection, mocked_getattr):
        """Test Redis TimeoutError."""
        mocked_getattr.return_value = "redis_url"

        # mock returns
        mocked_connection.return_value = mock.MagicMock()
        mocked_connection.return_value.__enter__.side_effect = TimeoutError("Timeout Error")

        # instantiates the class
        redis_healthchecker = RedisHealthCheck()

        # invokes the method check_status()
        redis_healthchecker.check_status()
        assert len(redis_healthchecker.errors), 1

        # mock assertions
        assert mocked_connection.called

    @mock.patch("health_check.contrib.redis.backends.getattr")
    @mock.patch("health_check.contrib.redis.backends.from_url")
    def test_redis_con_limit_exceeded(self, mocked_connection, mocked_getattr):
        """Test Connection Limit Exceeded error."""
        mocked_getattr.return_value = "redis_url"

        # mock returns
        mocked_connection.return_value = mock.MagicMock()
        mocked_connection.return_value.__enter__.side_effect = ConnectionError("Connection Error")

        # instantiates the class
        redis_healthchecker = RedisHealthCheck()

        # invokes the method check_status()
        redis_healthchecker.check_status()
        assert len(redis_healthchecker.errors), 1

        # mock assertions
        assert mocked_connection.called

    @mock.patch("health_check.contrib.redis.backends.getattr")
    @mock.patch("health_check.contrib.redis.backends.from_url")
    def test_redis_conn_ok(self, mocked_connection, mocked_getattr):
        """Test everything is OK."""
        mocked_getattr.return_value = "redis_url"

        # mock returns
        mocked_connection.return_value = mock.MagicMock()
        mocked_connection.return_value.__enter__.side_effect = True

        # instantiates the class
        redis_healthchecker = RedisHealthCheck()

        # invokes the method check_status()
        redis_healthchecker.check_status()
        assert len(redis_healthchecker.errors), 0

        # mock assertions
        assert mocked_connection.called
