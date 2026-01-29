from unittest.mock import patch

from redis import exceptions as redis_exceptions

from health_check.contrib.redis.backends import RedisHealthCheck
from health_check.exceptions import ServiceUnavailable


def test_redis_ping_success():
    chk = RedisHealthCheck()

    class FakeConn:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def ping(self):
            return True

    with patch("health_check.contrib.redis.backends.from_url") as fake_from_url:
        fake_from_url.return_value = FakeConn()
        chk.check_status()
        assert not chk.errors


def test_redis_connection_refused():
    chk = RedisHealthCheck()

    class FakeConn:
        def __enter__(self):
            raise ConnectionRefusedError("refused")

        def __exit__(self, exc_type, exc, tb):
            return False

    with patch("health_check.contrib.redis.backends.from_url") as fake_from_url:
        fake_from_url.return_value = FakeConn()
        chk.check_status()
        assert chk.errors
        assert any(isinstance(e, ServiceUnavailable) for e in chk.errors)


def test_redis_timeout_error():
    chk = RedisHealthCheck()

    class FakeConn:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def ping(self):
            raise redis_exceptions.TimeoutError("timeout")

    with patch("health_check.contrib.redis.backends.from_url") as fake_from_url:
        fake_from_url.return_value = FakeConn()
        chk.check_status()
        assert chk.errors
        assert any(isinstance(e, ServiceUnavailable) for e in chk.errors)


def test_redis_connection_error():
    chk = RedisHealthCheck()

    class FakeConn:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def ping(self):
            raise redis_exceptions.ConnectionError("conn")

    with patch("health_check.contrib.redis.backends.from_url") as fake_from_url:
        fake_from_url.return_value = FakeConn()
        chk.check_status()
        assert chk.errors
        assert any(isinstance(e, ServiceUnavailable) for e in chk.errors)


def test_redis_unknown_error():
    chk = RedisHealthCheck()

    class FakeConn:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def ping(self):
            raise RuntimeError("boom")

    with patch("health_check.contrib.redis.backends.from_url") as fake_from_url:
        fake_from_url.return_value = FakeConn()
        chk.check_status()
        assert chk.errors
        assert any(isinstance(e, ServiceUnavailable) for e in chk.errors)
