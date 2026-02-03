from __future__ import annotations

import abc
import asyncio
import dataclasses
import inspect
import logging
import timeit
from functools import cached_property

from health_check.exceptions import HealthCheckException

logger = logging.getLogger(__name__)


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

    Subclasses should be [dataclases][dataclasses.dataclass] or implement their own `__repr__` method
    to provide meaningful representations in health check reports.

    Warning:
        The `__repr__` method is used in health check reports.
        Consider setting `repr=False` for sensitive dataclass fields
        to avoid leaking sensitive information or credentials.

    """

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

    @cached_property
    async def result(self: HealthCheck) -> HealthCheckResult:
        start = timeit.default_timer()
        try:
            await self.run() if inspect.iscoroutinefunction(
                self.run
            ) else await asyncio.to_thread(self.run)
        except HealthCheckException as e:
            error = e
        except BaseException as e:
            logger.exception("Unexpected exception during health check: %s", e)
            error = HealthCheckException("unknown error")
        else:
            error = None
        return HealthCheckResult(
            check=self,
            error=error,
            time_taken=timeit.default_timer() - start,
        )
