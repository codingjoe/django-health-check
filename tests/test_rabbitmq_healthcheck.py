import pytest

pytest.importorskip("amqp")
from unittest.mock import patch

from amqp.exceptions import AccessRefused

from health_check.contrib.rabbitmq.backends import RabbitMQHealthCheck
from health_check.exceptions import ServiceUnavailable


def test_rabbitmq_connect_success(monkeypatch):
    chk = RabbitMQHealthCheck()

    class FakeConn:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def connect(self):
            return True

    with patch("health_check.contrib.rabbitmq.backends.Connection") as fake_conn_cls:
        fake_conn_cls.return_value = FakeConn()
        chk.check_status()
        assert not chk.errors


def test_rabbitmq_connection_refused():
    chk = RabbitMQHealthCheck()

    # simulate ConnectionRefusedError when entering context
    class FakeConn:
        def __enter__(self):
            raise ConnectionRefusedError("refused")

        def __exit__(self, exc_type, exc, tb):
            return False

    with patch("health_check.contrib.rabbitmq.backends.Connection") as fake_conn_cls:
        fake_conn_cls.return_value = FakeConn()
        chk.check_status()
        assert chk.errors
        assert any(isinstance(e, ServiceUnavailable) for e in chk.errors)


def test_rabbitmq_access_refused():
    chk = RabbitMQHealthCheck()

    class FakeConn:
        def __enter__(self):
            raise AccessRefused("auth")

        def __exit__(self, exc_type, exc, tb):
            return False

    with patch("health_check.contrib.rabbitmq.backends.Connection") as fake_conn_cls:
        fake_conn_cls.return_value = FakeConn()
        chk.check_status()
        assert chk.errors
        assert any(isinstance(e, ServiceUnavailable) for e in chk.errors)


def test_rabbitmq_oserror():
    chk = RabbitMQHealthCheck()

    class FakeConn:
        def __enter__(self):
            raise OSError("io")

        def __exit__(self, exc_type, exc, tb):
            return False

    with patch("health_check.contrib.rabbitmq.backends.Connection") as fake_conn_cls:
        fake_conn_cls.return_value = FakeConn()
        chk.check_status()
        assert chk.errors
        assert any(isinstance(e, ServiceUnavailable) for e in chk.errors)


def test_rabbitmq_unknown_error():
    chk = RabbitMQHealthCheck()

    class FakeConn:
        def __enter__(self):
            raise RuntimeError("boom")

        def __exit__(self, exc_type, exc, tb):
            return False

    with patch("health_check.contrib.rabbitmq.backends.Connection") as fake_conn_cls:
        fake_conn_cls.return_value = FakeConn()
        chk.check_status()
        assert chk.errors
        assert any(isinstance(e, ServiceUnavailable) for e in chk.errors)
