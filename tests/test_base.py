import logging
from io import StringIO

import pytest

from health_check.base import HealthCheck
from health_check.exceptions import HealthCheckException


class TestHealthCheck:
    def test_check_status__not_implemented(self):
        """Raise NotImplementedError when check_status is not implemented."""
        with pytest.raises(NotImplementedError):
            HealthCheck().check_status()

    def test_run_check__success(self):
        """Execute check_status without errors."""

        class SuccessCheck(HealthCheck):
            def check_status(self):
                pass

        check = SuccessCheck()
        check.run_check()
        assert check.errors == []

    def test_status__healthy(self):
        """Return 1 when no errors are present."""
        ht = HealthCheck()
        assert ht.status == 1

    def test_status__unhealthy(self):
        """Return 0 when errors are present."""
        ht = HealthCheck()
        ht.errors = [1]
        assert ht.status == 0

    def test_pretty_status__no_errors(self):
        """Return 'OK' when no errors are present."""
        ht = HealthCheck()
        assert ht.pretty_status() == "OK"

    def test_pretty_status__single_error(self):
        """Return error string when single error exists."""
        ht = HealthCheck()
        ht.errors = ["foo"]
        assert ht.pretty_status() == "foo"

    def test_pretty_status__multiple_errors(self):
        """Return newline-separated errors when multiple errors exist."""
        ht = HealthCheck()
        ht.errors = ["foo", "bar", 123]
        assert ht.pretty_status() == "foo\nbar\n123"

    def test_add_error__with_exception(self):
        """Store HealthCheckException as-is when passed."""
        ht = HealthCheck()
        e = HealthCheckException("foo")
        ht.add_error(e)
        assert ht.errors[0] is e

    def test_add_error__with_string(self):
        """Convert string to HealthCheckException."""
        ht = HealthCheck()
        ht.add_error("bar")
        assert isinstance(ht.errors[0], HealthCheckException)
        assert str(ht.errors[0]) == "unknown error: bar"

    def test_add_error__with_non_string_non_exception(self):
        """Convert non-string/non-exception to HealthCheckException with generic message."""
        ht = HealthCheck()
        ht.add_error(type)
        assert isinstance(ht.errors[0], HealthCheckException)
        assert str(ht.errors[0]) == "unknown error: unknown error"

    def test_add_error__with_exception_cause(self):
        """Log exception details when cause is provided."""
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

    def test_add_error__without_exception_cause(self):
        """Log error message without traceback when cause is not provided."""
        ht = HealthCheck()
        logger = logging.getLogger("health-check")
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
