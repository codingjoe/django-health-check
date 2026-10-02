from __future__ import annotations

import abc
import asyncio
import dataclasses
import datetime
import inspect
import logging
import timeit
from concurrent.futures import Executor

from health_check.exceptions import HealthCheckException, ServiceUnavailable

logger = logging.getLogger("health_check")


@dataclasses.dataclass
class HealthCheckResult:
    """Result of a health check execution."""

    check: HealthCheck
    error: HealthCheckException | None
    time_taken: float


@dataclasses.dataclass
class HealthCheck(abc.ABC):
    """
    Base class for defining health checks.

    Subclasses should implement the `run` method to perform the actual health check logic.
    The `run` method can be either synchronous or asynchronous.

    Examples:
        >>> import dataclasses
        >>> from health_check.base import HealthCheck
        >>>
        >>> @dataclasses.dataclass
        >>> class MyHealthCheck(HealthCheck):
        ...
        ...    async def run(self):
        ...        # Implement health check logic here

    Subclasses should be [dataclasses][dataclasses.dataclass] or implement their own `__repr__` method
    to provide meaningful representations in health check reports.

    Warning:
        The `__repr__` method is used in health check reports.
        Consider setting `repr=False` for sensitive dataclass fields
        to avoid leaking sensitive information or credentials.

    """

    # A dataclass field here would become the first parameter of every check.
    timeout = datetime.timedelta(seconds=5)
    """Wall-clock budget for the probe; a check declaring its own timeout overrides it."""

    @abc.abstractmethod
    async def run(self) -> None:
        """
        Run the health check logic and raise human-readable exceptions as needed.

        Exception must be reraised to indicate the health status and provide context.
        Any unexpected exceptions will be caught and logged for security purposes
        while returning a generic error message.

        Warning:
            Exception messages must not contain sensitive information.

        Raises:
            ServiceWarning: If the service is at a critical state but still operational.
            ServiceUnavailable: If the service is not operational.
            ServiceReturnedUnexpectedResult: If the check performs a computation that returns an unexpected result.

        """
        ...

    def pretty_status(self) -> str:
        """Return a human-readable status string, always 'OK' for the check itself."""
        return "OK"

    @property
    def labels(self) -> dict[str, str]:
        """Return a human-readable label for the check, defaulting to the class name."""
        return {
            "check": self.__class__.__name__,
        } | {
            field.name: str(value)
            for field in dataclasses.fields(self)
            if field.repr and (value := getattr(self, field.name)) is not None
        }

    async def get_result(self, executor: Executor | None = None) -> HealthCheckResult:
        loop = asyncio.get_running_loop()
        start = timeit.default_timer()
        try:
            await asyncio.wait_for(
                self.run()
                if inspect.iscoroutinefunction(self.run)
                else loop.run_in_executor(executor, self.run),
                # Give a check's own client timeout a second to report first.
                self.timeout.total_seconds() + 1,
            )
        except HealthCheckException as e:
            error = e
            logger.warning("Health check %r failed", self, exc_info=True)
        except asyncio.TimeoutError:
            error = ServiceUnavailable(
                f"Timed out after {self.timeout.total_seconds():g} seconds"
            )
            logger.warning("Health check %r failed", self, exc_info=True)
        except asyncio.CancelledError:
            raise
        except BaseException:
            logger.exception("Unexpected exception during health check")
            error = HealthCheckException("unknown error")
        else:
            error = None
        return HealthCheckResult(
            check=self,
            error=error,
            time_taken=timeit.default_timer() - start,
        )
