import dataclasses
import datetime
import logging
import smtplib

from django.conf import settings
from django.core.mail import get_connection
from django.core.mail.backends.base import BaseEmailBackend

from health_check import backends, conf, exceptions

logger = logging.getLogger(__name__)


@dataclasses.dataclass
class Mail(backends.HealthCheck):
    """
    Check that mail backend is able to open and close connection.

    Args:
        backend: The email backend to test against.
        timeout: Timeout for connection to mail server.

    """

    backend: str = dataclasses.field(default="", repr=False)
    timeout: datetime.timedelta = dataclasses.field(
        default_factory=lambda: datetime.timedelta(seconds=15),
        repr=False,
    )

    def __post_init__(self):
        # Set backend from settings if not explicitly provided
        if not self.backend:
            object.__setattr__(self, "backend", settings.EMAIL_BACKEND)
        # Override timeout from settings if available and using default
        if self.timeout == datetime.timedelta(seconds=15) and hasattr(conf.HEALTH_CHECK, "get"):
            timeout_seconds = conf.HEALTH_CHECK.get("MAIL_TIMEOUT", 15)
            object.__setattr__(self, "timeout", datetime.timedelta(seconds=timeout_seconds))

    def check_status(self) -> None:
        connection: BaseEmailBackend = get_connection(self.backend, fail_silently=False)
        connection.timeout = self.timeout.total_seconds()
        logger.debug("Trying to open connection to mail backend.")
        try:
            connection.open()
        except smtplib.SMTPException as error:
            self.add_error(
                error=exceptions.ServiceUnavailable(
                    "Failed to open connection with SMTP server",
                ),
                cause=error,
            )
        except ConnectionRefusedError as error:
            self.add_error(
                error=exceptions.ServiceUnavailable(
                    "Connection refused error",
                ),
                cause=error,
            )
        except BaseException as error:
            self.add_error(
                error=exceptions.ServiceUnavailable(
                    f"Unknown error {error.__class__}",
                ),
                cause=error,
            )
        finally:
            connection.close()
        logger.debug("Connection established. Mail backend %r is healthy.", self.backend)
