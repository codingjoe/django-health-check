import dataclasses
import datetime
import os
import pathlib
import socket

import psutil

from health_check import HealthCheck
from health_check.exceptions import (
    ServiceReturnedUnexpectedResult,
    ServiceUnavailable,
    ServiceWarning,
)


@dataclasses.dataclass
class Battery(HealthCheck):
    """
    Warn about system battery status and power connection.

    Args:
        min_percent_available: Minimum battery percentage available or None to disable the check.
        power_plugged: Whether to warn if the power is unplugged.

    """

    min_percent_available: float | None = dataclasses.field(default=20.0, repr=False)
    power_plugged: bool = dataclasses.field(default=False, repr=False)
    hostname: str = dataclasses.field(default_factory=socket.gethostname, init=False)

    def run(self):
        try:
            battery = psutil.sensors_battery()
        except AttributeError as e:
            raise ServiceUnavailable("Battery information not available") from e
        except ValueError as e:
            raise ServiceReturnedUnexpectedResult("ValueError") from e
        else:
            if (
                self.min_percent_available
                and battery.percent <= self.min_percent_available
            ):
                raise ServiceWarning(f"Battery {battery.percent:.1f}\u202f%")
            if self.power_plugged and not battery.power_plugged:
                raise ServiceWarning(
                    f"Power unplugged with battery at {battery.percent:.1f}\u202f%"
                )


@dataclasses.dataclass
class CPU(HealthCheck):
    """
    Warn about system CPU utilization.

    The utilization represents an interval rather than a point in time measurement.
    The interval starts with the previous execution of this check and with the current
    unless an explicit interval is provided. An explicit interval will cause a blocking
    measurement and increases the execution time of the check by the length of the interval.

    Args:
        max_usage_percent: Maximum CPU usage in percent or None to disable the check.
        interval: The interval to measure CPU usage over or None to use the interval since the last check execution.

    """

    max_usage_percent: float | None = dataclasses.field(default=80.0, repr=False)
    interval: datetime.timedelta | None = dataclasses.field(default=None, repr=False)
    hostname: str = dataclasses.field(default_factory=socket.gethostname, init=False)

    def run(self):
        try:
            usage_percent = psutil.cpu_percent(
                interval=self.interval.total_seconds() if self.interval else None
            )
            msg = f"CPU {usage_percent:.1f}\u202f%"
            if self.max_usage_percent and usage_percent >= self.max_usage_percent:
                raise ServiceWarning(msg)
        except ValueError as e:
            raise ServiceReturnedUnexpectedResult("ValueError") from e


@dataclasses.dataclass()
class Disk(HealthCheck):
    """
    Warn about disk usage for a given system path.

    It can be setup multiple times at different system paths,
    e.g. one at your application root and one at your media storage root.

    Args:
        path: Path to check disk usage for.
        max_disk_usage_percent: Maximum disk usage in percent or None to disable the check.

    """

    path: pathlib.Path | str = dataclasses.field(default_factory=os.getcwd)
    max_disk_usage_percent: float | None = dataclasses.field(default=90.0, repr=False)
    hostname: str = dataclasses.field(default_factory=socket.gethostname, init=False)

    def run(self):
        try:
            du = psutil.disk_usage(str(self.path))
            if (
                self.max_disk_usage_percent
                and du.percent >= self.max_disk_usage_percent
            ):
                raise ServiceWarning(f"{du.percent}\u202f% disk usage")
        except ValueError as e:
            raise ServiceReturnedUnexpectedResult("ValueError") from e


@dataclasses.dataclass()
class Memory(HealthCheck):
    """
    Warn about system memory utilization.

    Args:
        min_gibibytes_available: Minimum available memory in gibibytes or None to disable the check.
        max_memory_usage_percent: Maximum memory usage in percent or None to disable the check.

    """

    min_gibibytes_available: float | None = dataclasses.field(default=None, repr=False)
    max_memory_usage_percent: float | None = dataclasses.field(default=90.0, repr=False)
    hostname: str = dataclasses.field(default_factory=socket.gethostname, init=False)

    def run(self):
        try:
            memory = psutil.virtual_memory()
            available_gibi = memory.available / (1024**3)
            total_gibi = memory.total / (1024**3)
            msg = f"RAM {available_gibi:.1f}/{total_gibi:.1f}GiB ({memory.percent}\u202f%)"
            if (
                self.min_gibibytes_available
                and available_gibi < self.min_gibibytes_available
            ):
                raise ServiceWarning(msg)
            if (
                self.max_memory_usage_percent
                and memory.percent >= self.max_memory_usage_percent
            ):
                raise ServiceWarning(msg)
        except ValueError as e:
            raise ServiceReturnedUnexpectedResult("ValueError") from e


@dataclasses.dataclass
class Temperature(HealthCheck):
    """
    Warn about system temperature.

    If no maximum temperature is specified, the sensor's high threshold will be used.

    Args:
        device: The device to check temperature for, e.g. 'coretemp' for CPU temperature on many systems. If None, check all available sensors.
        max_temperature_celsius: Maximum temperature in degree Celsius or None to disable the check.

    """

    device: str | None = dataclasses.field(default="coretemp")
    max_temperature_celsius: float | None = dataclasses.field(default=None, repr=False)
    hostname: str = dataclasses.field(default_factory=socket.gethostname, init=False)

    def run(self):
        try:
            temperatures = psutil.sensors_temperatures()
        except AttributeError as e:
            raise ServiceUnavailable("Temperature information not available") from e
        else:
            if self.device:
                try:
                    sensors = temperatures[self.device]
                except KeyError:
                    raise ServiceUnavailable(
                        f"Sensor {self.device!r} not found"
                    ) from None
                else:
                    for sensor in sensors:
                        if sensor.current >= (
                            self.max_temperature_celsius or sensor.high
                        ):
                            raise ServiceWarning(
                                f"{sensor.label} {sensor.current:.1f}\u202f°C"
                            )
            else:
                for device, sensors in temperatures.items():
                    for sensor in sensors:
                        if sensor.current >= (
                            self.max_temperature_celsius or sensor.high
                        ):
                            raise ServiceWarning(
                                f"{device} {sensor.label} {sensor.current:.1f}\u202f°C"
                            )
