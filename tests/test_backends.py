import logging
from io import StringIO

import pytest

from health_check.backends import HealthCheck
from health_check.exceptions import HealthCheckException


class TestBaseHealthCheckBackend:
    def test_run_check(self):
        with pytest.raises(NotImplementedError):
            HealthCheck().run_check()

    def test_status(self):
        ht = HealthCheck()
        assert ht.status == 1
        ht.errors = [1]
        assert ht.status == 0

    def test_pretty_status(self):
        ht = HealthCheck()
        assert ht.pretty_status() == "OK"
        ht.errors = ["foo"]
        assert ht.pretty_status() == "foo"
        ht.errors.append("bar")
        assert ht.pretty_status() == "foo\nbar"
        ht.errors.append(123)
        assert ht.pretty_status() == "foo\nbar\n123"

    def test_add_error(self):
        ht = HealthCheck()
        e = HealthCheckException("foo")
        ht.add_error(e)
        assert ht.errors[0] is e

        ht = HealthCheck()
        ht.add_error("bar")
        assert isinstance(ht.errors[0], HealthCheckException)
        assert str(ht.errors[0]) == "unknown error: bar"

        ht = HealthCheck()
        ht.add_error(type)
        assert isinstance(ht.errors[0], HealthCheckException)
        assert str(ht.errors[0]) == "unknown error: unknown error"

    def test_add_error_cause(self):
        ht = HealthCheck()
        logger = logging.getLogger("health-check")
        with StringIO() as stream:
            stream_handler = logging.StreamHandler(stream)
            logger.addHandler(stream_handler)
            try:
                raise Exception("bar")
            except Exception as e:
                ht.add_error("foo", e)

            stream.seek(0)
            log = stream.read()
            assert "foo" in log
            assert "bar" in log
            assert "Traceback" in log
            assert "Exception: bar" in log
            logger.removeHandler(stream_handler)

        with StringIO() as stream:
            stream_handler = logging.StreamHandler(stream)
            logger.addHandler(stream_handler)
            try:
                raise Exception("bar")
            except Exception:
                ht.add_error("foo")

            stream.seek(0)
            log = stream.read()
            assert "foo" in log
            assert "bar" not in log
            assert "Traceback" not in log
            assert "Exception: bar" not in log
            logger.removeHandler(stream_handler)
