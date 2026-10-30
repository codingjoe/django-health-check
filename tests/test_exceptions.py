"""Unit tests for health_check.exceptions module."""

import datetime

import httpx
import pytest
from django.utils import timezone

from health_check.exceptions import (
    HealthCheckError,
    RemoteServiceReturnedUnexpectedResultError,
    RemoteServiceUnavailableError,
    ServiceReturnedUnexpectedResult,
    ServiceUnavailable,
    ServiceWarning,
    StatusPageWarning,
)


class TestHealthCheckError:
    def test_init__store_message(self):
        """Store message passed to constructor."""
        exc = HealthCheckError("test message")
        assert exc.message == "test message"

    def test_init__timestamp_defaults_to_now(self):
        """Default timestamp to current time when not provided."""
        before = timezone.now()
        exc = HealthCheckError("test message")
        after = timezone.now()
        assert before <= exc.timestamp <= after

    def test_init__store_timestamp(self):
        """Store explicit timestamp passed to constructor."""
        ts = datetime.datetime(2024, 1, 1, tzinfo=datetime.UTC)
        exc = HealthCheckError("test message", timestamp=ts)
        assert exc.timestamp == ts

    def test_str__format_with_type(self):
        """Format string with message type and message."""
        exc = HealthCheckError("foo")
        assert str(exc) == "Unknown Error: foo"

    def test_inherits_from_exception(self):
        """Inherit from Exception base class."""
        exc = HealthCheckError("test")
        assert isinstance(exc, Exception)

    def test_can_raise_and_catch(self):
        """Can be raised and caught."""
        error = HealthCheckError("error message")
        with pytest.raises(HealthCheckError) as exc_info:
            raise error
        assert exc_info.value.message == "error message"


class TestServiceWarning:
    def test_str__format_with_warning_type(self):
        """Format string with 'warning' message type."""
        exc = ServiceWarning("unstable")
        assert str(exc) == "Warning: unstable"

    def test_inherits_from_health_check_exception(self):
        """Inherit from HealthCheckError."""
        exc = ServiceWarning("test")
        assert isinstance(exc, HealthCheckError)
        assert isinstance(exc, Exception)

    def test_can_raise_and_catch_as_exception(self):
        """Can be caught as HealthCheckError."""
        error = ServiceWarning("warning message")
        with pytest.raises(HealthCheckError):
            raise error

    def test_can_raise_and_catch_as_specific_type(self):
        """Can be caught as ServiceWarning specifically."""
        error = ServiceWarning("warning message")
        with pytest.raises(ServiceWarning):
            raise error


class TestServiceUnavailable:
    def test_str__format_with_unavailable_type(self):
        """Format string with 'unavailable' message type."""
        exc = ServiceUnavailable("database down")
        assert str(exc) == "Unavailable: database down"

    def test_inherits_from_health_check_exception(self):
        """Inherit from HealthCheckError."""
        exc = ServiceUnavailable("test")
        assert isinstance(exc, HealthCheckError)
        assert isinstance(exc, Exception)

    def test_can_raise_and_catch_as_exception(self):
        """Can be caught as HealthCheckError."""
        error = ServiceUnavailable("unavailable message")
        with pytest.raises(HealthCheckError):
            raise error

    def test_can_raise_and_catch_as_specific_type(self):
        """Can be caught as ServiceUnavailable specifically."""
        error = ServiceUnavailable("unavailable message")
        with pytest.raises(ServiceUnavailable):
            raise error


class TestServiceReturnedUnexpectedResult:
    def test_str__format_with_unexpected_result_type(self):
        """Format string with 'unexpected result' message type."""
        exc = ServiceReturnedUnexpectedResult("wrong format")
        assert str(exc) == "Unexpected Result: wrong format"

    def test_inherits_from_health_check_exception(self):
        """Inherit from HealthCheckError."""
        exc = ServiceReturnedUnexpectedResult("test")
        assert isinstance(exc, HealthCheckError)
        assert isinstance(exc, Exception)

    def test_can_raise_and_catch_as_exception(self):
        """Can be caught as HealthCheckError."""
        error = ServiceReturnedUnexpectedResult("unexpected result message")
        with pytest.raises(HealthCheckError):
            raise error

    def test_can_raise_and_catch_as_specific_type(self):
        """Can be caught as ServiceReturnedUnexpectedResult specifically."""
        error = ServiceReturnedUnexpectedResult("unexpected result message")
        with pytest.raises(ServiceReturnedUnexpectedResult):
            raise error


class TestRemoteServiceUnavailableError:
    def test_init__include_remote_errors(self):
        """Include remote check errors from the response body."""
        response = httpx.Response(
            500,
            json={"Database": "Unavailable: down", "Cache": "OK"},
        )
        exc = RemoteServiceUnavailableError(response)
        assert exc.message == (
            "Remote health check returned HTTP 500\nDatabase: Unavailable: down"
        )

    def test_init__ignore_ok_entries(self):
        """Report only the status when every remote check is OK."""
        exc = RemoteServiceUnavailableError(
            httpx.Response(500, json={"Database": "OK"})
        )
        assert exc.message == "Remote health check returned HTTP 500"

    def test_init__handle_invalid_json(self):
        """Report only the status when the body is not valid JSON."""
        exc = RemoteServiceUnavailableError(httpx.Response(500, text="not json"))
        assert exc.message == "Remote health check returned HTTP 500"

    def test_init__handle_non_object_json(self):
        """Report only the status when the body is not a JSON object."""
        exc = RemoteServiceUnavailableError(httpx.Response(500, json=["down"]))
        assert exc.message == "Remote health check returned HTTP 500"

    def test_init__store_timestamp(self):
        """Store explicit timestamp passed to constructor."""
        ts = datetime.datetime(2024, 1, 1, tzinfo=datetime.UTC)
        exc = RemoteServiceUnavailableError(httpx.Response(500), timestamp=ts)
        assert exc.timestamp == ts

    def test_str__format_with_unavailable_type(self):
        """Format string with 'unavailable' message type."""
        exc = RemoteServiceUnavailableError(httpx.Response(500))
        assert str(exc) == "Unavailable: Remote health check returned HTTP 500"

    def test_inherits_from_service_unavailable(self):
        """Inherit from ServiceUnavailable."""
        exc = RemoteServiceUnavailableError(httpx.Response(500))
        assert isinstance(exc, ServiceUnavailable)
        assert isinstance(exc, HealthCheckError)


class TestRemoteServiceReturnedUnexpectedResultError:
    def test_init__include_remote_errors(self):
        """Include remote check errors from the response body."""
        response = httpx.Response(404, json={"detail": "Not found"})
        exc = RemoteServiceReturnedUnexpectedResultError(response)
        assert exc.message == (
            "Remote health check returned HTTP 404\ndetail: Not found"
        )

    def test_str__format_with_unexpected_result_type(self):
        """Format string with 'unexpected result' message type."""
        exc = RemoteServiceReturnedUnexpectedResultError(httpx.Response(404))
        assert str(exc) == ("Unexpected Result: Remote health check returned HTTP 404")

    def test_inherits_from_service_returned_unexpected_result(self):
        """Inherit from ServiceReturnedUnexpectedResult."""
        exc = RemoteServiceReturnedUnexpectedResultError(httpx.Response(404))
        assert isinstance(exc, ServiceReturnedUnexpectedResult)
        assert isinstance(exc, HealthCheckError)


class TestStatusPageWarning:
    def test_init__store_message(self):
        """Store message passed to constructor."""
        exc = StatusPageWarning("incident detected")
        assert exc.message == "incident detected"

    def test_init__timestamp_defaults_to_now(self):
        """Default timestamp to current time when not provided."""
        before = timezone.now()
        exc = StatusPageWarning("incident detected")
        after = timezone.now()
        assert before <= exc.timestamp <= after

    def test_init__store_timestamp(self):
        """Store timestamp passed to constructor."""
        ts = datetime.datetime(2024, 1, 1, tzinfo=datetime.UTC)
        exc = StatusPageWarning("incident detected", timestamp=ts)
        assert exc.timestamp == ts

    def test_str__format_with_warning_type(self):
        """Format string with 'warning' message type."""
        exc = StatusPageWarning("incident detected")
        assert str(exc) == "Warning: incident detected"

    def test_inherits_from_service_warning(self):
        """Inherit from ServiceWarning."""
        exc = StatusPageWarning("incident")
        assert isinstance(exc, ServiceWarning)
        assert isinstance(exc, HealthCheckError)

    def test_can_raise_and_catch_as_service_warning(self):
        """Can be caught as ServiceWarning."""
        with pytest.raises(ServiceWarning):
            raise StatusPageWarning("incident")
