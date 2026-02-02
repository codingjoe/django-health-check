import dataclasses
import logging
import warnings
from timeit import default_timer as timer

from health_check.exceptions import HealthCheckException

logger = logging.getLogger("health-check")


@dataclasses.dataclass()
class HealthCheck:
    """
    Base class for all health check backends.

    To create your own health check backend, subclass this class
    and implement the ``check_status`` method.
    """

    critical_service: bool = dataclasses.field(init=False, default=True, repr=False)
    errors: list[HealthCheckException] = dataclasses.field(init=False, default_factory=list, repr=False)

    async def __call__(self, *args, **kwargs):
        return self.run_check()

    def check_status(self):
        """
        Execute the health check logic.

        This method should be overridden by subclasses to implement
        specific health check logic. If the check fails, it should
        call `self.add_error` with an appropriate error message or
        raise a `HealthCheckException`.

        Raises:
            HealthCheckException: If the health check fails.
            ServiceWarning: If the health check encounters a warning condition.

        """
        raise NotImplementedError

    def run_check(self):
        start = timer()
        self.errors = []
        try:
            self.check_status()
        except HealthCheckException as e:
            self.add_error(e, e)
        except BaseException:
            logger.exception("Unexpected Error!")
            raise
        finally:
            self.time_taken = timer() - start

    def add_error(self, error, cause=None):
        if isinstance(error, HealthCheckException):
            pass
        elif isinstance(error, str):
            msg = error
            error = HealthCheckException(msg)
        else:
            msg = "unknown error"
            error = HealthCheckException(msg)
        if isinstance(cause, BaseException):
            logger.exception(str(error))
        else:
            logger.error(str(error))
        self.errors.append(error)

    def pretty_status(self):
        if self.errors:
            return "\n".join(str(e) for e in self.errors)
        return "OK"

    @property
    def status(self):
        return int(not self.errors)

    def __repr__(self):
        if hasattr(self, "identifier"):
            warnings.warn(
                "`identifier()` method is deprecated: implement `__repr__()` instead to return a stable identifier. Action: update your backend class to implement `__repr__` and remove `identifier()`. See migration guide: https://codingjoe.dev/django-health-check/migrate-to-v4/ (docs/migrate-to-v4.md).",
                DeprecationWarning,
            )
            return self.identifier()

        return self.__class__.__name__


class BaseHealthCheck(HealthCheck):
    """
    Deprecated base class for health check backends.

    This class is maintained for backward compatibility.
    New health check backends should inherit from `HealthCheck` instead.
    """

    def __init_subclass__(cls, **kwargs):
        warnings.warn(
            f"{cls.__name__} inherits from deprecated `BaseHealthCheck`: inherit from `HealthCheck` instead. Action: update subclass to inherit from `health_check.backends.HealthCheck`. See migration guide: https://codingjoe.dev/django-health-check/migrate-to-v4/ (docs/migrate-to-v4.md).",
            DeprecationWarning,
            stacklevel=2,
        )
        super().__init_subclass__(**kwargs)
