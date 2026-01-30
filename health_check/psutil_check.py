import dataclasses
import os
import pathlib
import socket

import psutil

from health_check.backends import HealthCheck
from health_check.conf import HEALTH_CHECK
from health_check.exceptions import ServiceReturnedUnexpectedResult, ServiceWarning


@dataclasses.dataclass()
class Disk(HealthCheck):
    """
    Check system disk usage.

    Args:
        path: Path to check disk usage for.
        max_disk_usage_percent: Maximum disk usage in percent or None to disable the check.

    """

    path: pathlib.Path | str = dataclasses.field(default=os.getcwd())
    max_disk_usage_percent: float | None = dataclasses.field(default=HEALTH_CHECK["DISK_USAGE_MAX"], repr=False)
    hostname: str = dataclasses.field(default_factory=socket.gethostname, init=False)

    def check_status(self):
        try:
            du = psutil.disk_usage(str(self.path))
            if self.max_disk_usage_percent and du.percent >= self.max_disk_usage_percent:
                raise ServiceWarning(f"{du.percent}\u202f% disk usage")
        except ValueError as e:
            self.add_error(ServiceReturnedUnexpectedResult("ValueError"), e)


@dataclasses.dataclass()
class Memory(HealthCheck):
    """
    Check system memory usage.

    Args:
        min_gibibytes_available: Minimum available memory in gibibytes or None to disable the check.
        max_memory_usage_percent: Maximum memory usage in percent or None to disable the check.

    """

    min_gibibytes_available: float | None = dataclasses.field(default=None, repr=False)
    max_memory_usage_percent: float | None = dataclasses.field(default=90.0, repr=False)
    hostname: str = dataclasses.field(default_factory=socket.gethostname, init=False)

    def check_status(self):
        try:
            memory = psutil.virtual_memory()
            available_gibi = memory.available / (1024**3)
            total_gibi = memory.total / (1024**3)
            msg = f"RAM {available_gibi:.1f}/{total_gibi:.1f}GiB ({memory.percent}\u202f%)"
            if self.min_gibibytes_available and available_gibi < self.min_gibibytes_available:
                raise ServiceWarning(msg)
            if self.max_memory_usage_percent and memory.percent >= self.max_memory_usage_percent:
                raise ServiceWarning(msg)
        except ValueError as e:
            self.add_error(ServiceReturnedUnexpectedResult("ValueError"), e)
