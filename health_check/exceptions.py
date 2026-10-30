import httpx
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


class RemoteHealthCheckError(HealthCheckError):
    """Remote health check endpoint returned a non-2xx response."""

    @staticmethod
    def _matches_component(check: str, component: str) -> bool:
        """Return whether a remote check belongs to the component."""
        return check == component or check.startswith(f"{component}(")

    def __init__(
        self,
        response: httpx.Response,
        *,
        component: str | None = None,
        timestamp=None,
    ):
        suffix = f" for {component!r}" if component else ""
        message = f"Remote health check returned HTTP {response.status_code}{suffix}"
        try:
            errors = "\n".join(
                f"{check}: {result}"
                for check, result in response.json().items()
                if result != "OK"
                and (
                    component in (None, "") or self._matches_component(check, component)
                )
            )
        except ValueError, AttributeError:
            errors = ""
        super().__init__(
            f"{message}\n{errors}" if errors else message, timestamp=timestamp
        )


class RemoteServiceUnavailableError(RemoteHealthCheckError, ServiceUnavailable):
    """Remote health check endpoint returned a 5xx response."""


class RemoteServiceReturnedUnexpectedResultError(
    RemoteHealthCheckError, ServiceReturnedUnexpectedResult
):
    """Remote health check endpoint returned a non-5xx error response."""


class StatusPageWarning(ServiceWarning):
    """Warning from an external status page, carrying the source incident timestamp."""
