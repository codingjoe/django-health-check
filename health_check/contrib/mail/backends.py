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
class MailHealthCheck(backends.HealthCheck):
    """
    Check that mail backend is able to open and close connection.

    Args:
        backend: The email backend to test against.
        timeout: Timeout for connection to mail server.

    """

    backend: str = settings.EMAIL_BACKEND
    timeout: datetime.timedelta = dataclasses.field(
        default=datetime.timedelta(seconds=conf.HEALTH_CHECK.get("MAIL_TIMEOUT", 15)),
        repr=False,
    )

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
