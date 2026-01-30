import dataclasses
import logging
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
    errors: list[HealthCheckException] = dataclasses.field(
        init=False, default_factory=list, repr=False
    )

    def check_status(self):
        """
        Execute the health check logic.

        This method should be overridden by subclasses to implement
        specific health check logic. If the check fails, it should
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
            self.errors.append(e)
            logger.exception(str(e))
        except BaseException:
            logger.exception("Unexpected Error!")
            raise
        finally:
            self.time_taken = timer() - start

    def pretty_status(self):
        if self.errors:
            return "\n".join(str(e) for e in self.errors)
        return "OK"

    @property
    def status(self):
        return int(not self.errors)
