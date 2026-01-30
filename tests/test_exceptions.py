"""Unit tests for health_check.exceptions module."""

import pytest

from health_check.exceptions import (
    HealthCheckException,
    ServiceReturnedUnexpectedResult,
    ServiceUnavailable,
    ServiceWarning,
)


class TestHealthCheckException:
    def test_init__store_message(self):
        """Store message passed to constructor."""
        exc = HealthCheckException("test message")
        assert exc.message == "test message"

    def test_str__format_with_type(self):
        """Format string with message type and message."""
        exc = HealthCheckException("foo")
        assert str(exc) == "Unknown Error: foo"

    def test_inherits_from_exception(self):
        """Inherit from Exception base class."""
        exc = HealthCheckException("test")
        assert isinstance(exc, Exception)

    def test_can_raise_and_catch(self):
        """Can be raised and caught."""
        with pytest.raises(HealthCheckException) as exc_info:
            raise HealthCheckException("error message")
        assert exc_info.value.message == "error message"


class TestServiceWarning:
    def test_str__format_with_warning_type(self):
        """Format string with 'warning' message type."""
        exc = ServiceWarning("unstable")
        assert str(exc) == "Warning: unstable"

    def test_inherits_from_health_check_exception(self):
        """Inherit from HealthCheckException."""
        exc = ServiceWarning("test")
        assert isinstance(exc, HealthCheckException)
        assert isinstance(exc, Exception)

    def test_can_raise_and_catch_as_exception(self):
        """Can be caught as HealthCheckException."""
        with pytest.raises(HealthCheckException):
            raise ServiceWarning("warning message")

    def test_can_raise_and_catch_as_specific_type(self):
        """Can be caught as ServiceWarning specifically."""
        with pytest.raises(ServiceWarning):
            raise ServiceWarning("warning message")


class TestServiceUnavailable:
    def test_str__format_with_unavailable_type(self):
        """Format string with 'unavailable' message type."""
        exc = ServiceUnavailable("database down")
        assert str(exc) == "Unavailable: database down"

    def test_inherits_from_health_check_exception(self):
        """Inherit from HealthCheckException."""
        exc = ServiceUnavailable("test")
        assert isinstance(exc, HealthCheckException)
        assert isinstance(exc, Exception)

    def test_can_raise_and_catch_as_exception(self):
        """Can be caught as HealthCheckException."""
        with pytest.raises(HealthCheckException):
            raise ServiceUnavailable("unavailable message")

    def test_can_raise_and_catch_as_specific_type(self):
        """Can be caught as ServiceUnavailable specifically."""
        with pytest.raises(ServiceUnavailable):
            raise ServiceUnavailable("unavailable message")


class TestServiceReturnedUnexpectedResult:
    def test_str__format_with_unexpected_result_type(self):
        """Format string with 'unexpected result' message type."""
        exc = ServiceReturnedUnexpectedResult("wrong format")
        assert str(exc) == "Unexpected Result: wrong format"

    def test_inherits_from_health_check_exception(self):
        """Inherit from HealthCheckException."""
        exc = ServiceReturnedUnexpectedResult("test")
        assert isinstance(exc, HealthCheckException)
        assert isinstance(exc, Exception)

    def test_can_raise_and_catch_as_exception(self):
        """Can be caught as HealthCheckException."""
        with pytest.raises(HealthCheckException):
            raise ServiceReturnedUnexpectedResult("unexpected result message")

    def test_can_raise_and_catch_as_specific_type(self):
        """Can be caught as ServiceReturnedUnexpectedResult specifically."""
        with pytest.raises(ServiceReturnedUnexpectedResult):
            raise ServiceReturnedUnexpectedResult("unexpected result message")
