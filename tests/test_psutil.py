from unittest.mock import patch

import pytest

from health_check.contrib.psutil.backends import DiskUsage, MemoryUsage
from health_check.exceptions import ServiceReturnedUnexpectedResult, ServiceWarning


class _FakeDiskUsage:
    def __init__(self, percent):
        self.percent = percent


class _FakeMemory:
    def __init__(self, total, available, percent):
        self.total = total
        self.available = available
        self.percent = percent


def test_disk_usage_ok():
    # healthy disk usage below threshold
    disk = DiskUsage(path="/", max_disk_usage_percent=95)
    with patch("health_check.contrib.psutil.backends.psutil.disk_usage") as mock_du:
        mock_du.return_value = _FakeDiskUsage(percent=50)
        disk.run_check()
        assert not disk.errors
        assert disk.status == 1


def test_disk_usage_warns_on_high_percent():
    disk = DiskUsage(path="/", max_disk_usage_percent=50)
    with patch("health_check.contrib.psutil.backends.psutil.disk_usage") as mock_du:
        mock_du.return_value = _FakeDiskUsage(percent=75)
        # run_check wraps warnings as errors via HEALTH_CHECK setting; expect ServiceWarning added
        with pytest.raises(ServiceWarning):
            # run_check may propagate exceptions depending on behavior; call check_status directly to inspect warnings
            disk.check_status()


def test_memory_usage_ok():
    mem = MemoryUsage(min_gibibytes_available=None, max_memory_usage_percent=95)
    with patch("health_check.contrib.psutil.backends.psutil.virtual_memory") as mock_vm:
        # create a memory object with plenty available
        mock_vm.return_value = _FakeMemory(total=8 * 1024**3, available=6 * 1024**3, percent=25)
        mem.run_check()
        assert not mem.errors
        assert mem.status == 1


def test_memory_usage_warns_on_low_available():
    mem = MemoryUsage(min_gibibytes_available=4, max_memory_usage_percent=None)
    with patch("health_check.contrib.psutil.backends.psutil.virtual_memory") as mock_vm:
        mock_vm.return_value = _FakeMemory(total=8 * 1024**3, available=2 * 1024**3, percent=75)
        # check_status should raise/add a ServiceWarning
        with pytest.raises(ServiceWarning):
            mem.check_status()


def test_psutil_value_error_is_converted_to_error():
    disk = DiskUsage(path="/", max_disk_usage_percent=90)
    with patch("health_check.contrib.psutil.backends.psutil.disk_usage") as mock_du:
        mock_du.side_effect = ValueError("bad path")
        disk.run_check()
        assert disk.errors
        assert any(isinstance(e, ServiceReturnedUnexpectedResult) for e in disk.errors)

    mem = MemoryUsage(min_gibibytes_available=None, max_memory_usage_percent=90)
    with patch("health_check.contrib.psutil.backends.psutil.virtual_memory") as mock_vm:
        mock_vm.side_effect = ValueError("bad mem")
        mem.run_check()
        assert mem.errors
        assert any(isinstance(e, ServiceReturnedUnexpectedResult) for e in mem.errors)
