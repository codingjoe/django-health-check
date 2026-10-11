from django.utils import timezone


class HealthCheckError(Exception):
    """Base class for all health check errors."""

    message_type: str = "Unknown Error"

    def __init__(self, message, *, timestamp=None):
        self.message = message
        self.timestamp = timezone.now() if timestamp is None else timestamp

    def __str__(self):
        return f"{self.message_type}: {self.message}"


# Alias kept for backwards compatibility. The concrete exceptions inherit from
# it, so their long-established public names stay unchanged.
HealthCheckException = HealthCheckError


class ServiceWarning(HealthCheckException):
    """Warning of service misbehavior."""

    message_type = "Warning"


class ServiceUnavailable(HealthCheckException):
    message_type = "Unavailable"


class ServiceReturnedUnexpectedResult(HealthCheckException):
    message_type = "Unexpected Result"


class StatusPageWarning(ServiceWarning):
    """Warning from an external status page, carrying the source incident timestamp."""
