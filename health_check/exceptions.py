class HealthCheckException(Exception):
    message_type: str = "Unknown Error"

    def __init__(self, message):
        self.message = message

    def __str__(self):
        return f"{self.message_type}: {self.message}"


class ServiceWarning(HealthCheckException):
    """Warning of service misbehavior."""

    message_type = "Warning"


class ServiceUnavailable(HealthCheckException):
    message_type = "Unavailable"


class ServiceReturnedUnexpectedResult(HealthCheckException):
    message_type = "Unexpected Result"


class StatusPageWarning(ServiceWarning):
    """Warning from an external status page, carrying the source incident timestamp."""

    def __init__(self, message, *, timestamp=None):
        super().__init__(message)
        self.timestamp = timestamp
