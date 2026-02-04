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
