import datetime
import pathlib
import tempfile
from unittest import mock

import pytest

pytest.importorskip("psutil")


# Use psutil's named tuples from _ntuples to minimize mocking risks.
# This private import is intentional to monitor breaking changes in future psutil updates.
from psutil._ntuples import sbattery, sdiskusage, shwtemp, svmem

from health_check.contrib.psutil import (
    CPU,
    Battery,
    Disk,
    Memory,
    Temperature,
    _CgroupMemory,
)
from health_check.exceptions import (
    ServiceReturnedUnexpectedResult,
    ServiceUnavailable,
    ServiceWarning,
)


class TestDisk:
    """Test the Disk health check."""

    @pytest.mark.asyncio
    async def test_run_check__disk_accessible(self):
        """Disk space check completes successfully."""
        check = Disk()
        result = await check.get_result()
        assert result.error is None

    @pytest.mark.asyncio
    async def test_run_check__custom_path(self):
        """Disk check succeeds with custom path."""
        with tempfile.TemporaryDirectory() as tmpdir:
            check = Disk(path=tmpdir)
            result = await check.get_result()
            assert result.error is None

    @pytest.mark.asyncio
    async def test_check_status__disk_usage_exceeds_threshold(self):
        """Raise ServiceWarning when disk usage exceeds threshold."""
        with mock.patch("psutil.disk_usage") as mock_disk_usage:
            mock_disk_usage.return_value = sdiskusage(
                total=100000000000, used=95500000000, free=4500000000, percent=95.5
            )

            check = Disk(max_disk_usage_percent=90.0)
            result = await check.get_result()
            assert result.error is not None
            assert isinstance(result.error, ServiceWarning)
            assert "95.5" in str(result.error)

    @pytest.mark.asyncio
    async def test_check_status__disk_check_disabled(self):
        """No warning when disk usage check is disabled."""
        with mock.patch("psutil.disk_usage") as mock_disk_usage:
            mock_disk_usage.return_value = sdiskusage(
                total=100000000000, used=99000000000, free=1000000000, percent=99.0
            )

            check = Disk(max_disk_usage_percent=None)
            result = await check.get_result()
            assert result.error is None

    @pytest.mark.asyncio
    async def test_check_status__disk_value_error(self):
        """Raise ServiceReturnedUnexpectedResult when ValueError is raised during disk check."""
        with mock.patch("psutil.disk_usage") as mock_disk_usage:
            mock_disk_usage.side_effect = ValueError("Invalid path")

            check = Disk()
            result = await check.get_result()
            assert result.error is not None
            assert isinstance(result.error, ServiceReturnedUnexpectedResult)


class TestMemory:
    """Test the Memory health check."""

    GIB = 1024**3
    MIB = 1024**2

    def write_cgroup(
        self,
        path: pathlib.Path,
        *,
        limit: int | str = GIB,
        current: int = 0,
        inactive_file: int = 0,
    ) -> None:
        """Write the memory control files of a cgroup v2 directory."""
        (path / "memory.max").write_text(f"{limit}\n")
        (path / "memory.current").write_text(f"{current}\n")
        (path / "memory.stat").write_text(f"inactive_file {inactive_file}\n")

    def host_memory(
        self, *, available: int | None = None, percent: float = 95.0
    ) -> svmem:
        """Return a host memory sample with 8 GiB total memory."""
        available = self.GIB if available is None else available
        total = 8 * self.GIB
        values = {
            "total": total,
            "available": available,
            "percent": percent,
            "used": total - available,
            "free": available,
            "active": 0,
            "inactive": 0,
            "buffers": 0,
            "cached": 0,
            "shared": 0,
            "slab": 0,
            "wired": 0,
        }
        return svmem(*(values[field] for field in svmem._fields))

    @pytest.fixture(autouse=True)
    def no_cgroup(self, monkeypatch, tmp_path_factory):
        """Force host memory for tests that do not use a control group."""
        monkeypatch.setattr(
            "health_check.contrib.psutil._CgroupMemory.ROOT",
            tmp_path_factory.mktemp("cgroup"),
        )

    @pytest.fixture
    def cgroup(self, monkeypatch, tmp_path):
        """Point cgroup discovery at a temporary control group."""
        root = tmp_path / "cgroup"
        root.mkdir()
        proc_self_cgroup = tmp_path / "proc-self-cgroup"
        proc_self_cgroup.write_text("0::/\n")
        monkeypatch.setattr("health_check.contrib.psutil._CgroupMemory.ROOT", root)
        monkeypatch.setattr(
            "health_check.contrib.psutil._CgroupMemory.PROC_SELF_CGROUP",
            proc_self_cgroup,
        )
        return root

    @pytest.mark.asyncio
    async def test_run_check__memory_available(self):
        """Memory check completes successfully."""
        check = Memory()
        result = await check.get_result()
        assert result.error is None

    @pytest.mark.asyncio
    async def test_check_status__min_memory_available_exceeded(self):
        """Raise ServiceWarning when available memory is below threshold."""
        with mock.patch("psutil.virtual_memory") as mock_virtual_memory:
            mock_virtual_memory.return_value = self.host_memory(
                available=0.5 * self.GIB, percent=95.0
            )

            check = Memory(min_gibibytes_available=1.0)
            result = await check.get_result()
            assert result.error is not None
            assert isinstance(result.error, ServiceWarning)
            assert "RAM" in str(result.error)

    @pytest.mark.asyncio
    async def test_check_status__max_memory_usage_exceeded(self):
        """Raise ServiceWarning when memory usage exceeds threshold."""
        with mock.patch("psutil.virtual_memory") as mock_virtual_memory:
            mock_virtual_memory.return_value = self.host_memory(
                available=self.GIB, percent=95.0
            )

            check = Memory(max_memory_usage_percent=90.0)
            result = await check.get_result()
            assert result.error is not None
            assert isinstance(result.error, ServiceWarning)
            assert "95" in str(result.error)

    @pytest.mark.asyncio
    async def test_check_status__memory_checks_disabled(self):
        """No warning when memory checks are disabled."""
        with mock.patch("psutil.virtual_memory") as mock_virtual_memory:
            mock_virtual_memory.return_value = self.host_memory(
                available=0.1 * self.GIB, percent=99.0
            )

            check = Memory(min_gibibytes_available=None, max_memory_usage_percent=None)
            result = await check.get_result()
            assert result.error is None

    @pytest.mark.asyncio
    async def test_check_status__memory_value_error(self):
        """Raise ServiceReturnedUnexpectedResult when ValueError is raised during memory check."""
        with mock.patch("psutil.virtual_memory") as mock_virtual_memory:
            mock_virtual_memory.side_effect = ValueError("Invalid memory call")

            check = Memory()
            result = await check.get_result()
            assert result.error is not None
            assert isinstance(result.error, ServiceReturnedUnexpectedResult)

    @pytest.mark.asyncio
    async def test_run_check__cgroup_working_set(self, cgroup):
        """Report the cgroup working set and succeed below the threshold."""
        self.write_cgroup(
            cgroup,
            limit=self.GIB,
            current=400 * self.MIB,
            inactive_file=100 * self.MIB,
        )

        with mock.patch("psutil.virtual_memory") as mock_virtual_memory:
            result = await Memory().get_result()

        assert result.error is None
        mock_virtual_memory.assert_not_called()
        memory = _CgroupMemory.read()
        assert memory.total == self.GIB
        assert memory.available == 724 * self.MIB
        assert memory.percent == pytest.approx(300 / 1024 * 100)

    @pytest.mark.asyncio
    async def test_run_check__cgroup_excludes_inactive_file(self, cgroup):
        """Count reclaimable page cache as available cgroup memory."""
        current = int(0.95 * self.GIB)
        inactive_file = self.GIB // 2
        self.write_cgroup(
            cgroup,
            limit=self.GIB,
            current=current,
            inactive_file=inactive_file,
        )

        with mock.patch("psutil.virtual_memory") as mock_virtual_memory:
            result = await Memory().get_result()

        assert result.error is None
        mock_virtual_memory.assert_not_called()
        memory = _CgroupMemory.read()
        assert memory.available == self.GIB - (current - inactive_file)
        assert memory.percent == pytest.approx(45.0, abs=1e-6)

    @pytest.mark.asyncio
    async def test_check_status__cgroup_memory_usage_exceeded(self, cgroup):
        """Raise ServiceWarning when the cgroup working set exceeds the threshold."""
        self.write_cgroup(
            cgroup,
            limit=self.GIB,
            current=int(1.05 * self.GIB),
            inactive_file=0,
        )

        result = await Memory().get_result()

        assert result.error is not None
        assert isinstance(result.error, ServiceWarning)
        assert "RAM" in str(result.error)
        assert "105.0" in str(result.error)

    @pytest.mark.asyncio
    async def test_check_status__cgroup_min_memory_available_exceeded(self, cgroup):
        """Raise ServiceWarning when cgroup available memory is below the minimum."""
        self.write_cgroup(
            cgroup,
            limit=self.GIB,
            current=self.GIB // 2,
            inactive_file=0,
        )

        result = await Memory(min_gibibytes_available=1.0).get_result()

        assert result.error is not None
        assert isinstance(result.error, ServiceWarning)
        assert "0.5/1.0GiB" in str(result.error)

    @pytest.mark.parametrize("limit", ["max", None], ids=["unlimited", "missing"])
    @pytest.mark.asyncio
    async def test_run_check__cgroup_unavailable_falls_back_to_host(
        self, cgroup, limit
    ):
        """Fall back to host memory when the cgroup limit cannot be read."""
        if limit is not None:
            (cgroup / "memory.max").write_text(f"{limit}\n")

        with mock.patch(
            "psutil.virtual_memory", return_value=self.host_memory()
        ) as mock_virtual_memory:
            result = await Memory().get_result()

        mock_virtual_memory.assert_called_once_with()
        assert result.error is not None
        assert isinstance(result.error, ServiceWarning)
        assert "RAM" in str(result.error)
        assert "8.0GiB" in str(result.error)

    @pytest.mark.asyncio
    async def test_run_check__cgroup_malformed_falls_back_to_host(self, cgroup):
        """Fall back to host memory when a cgroup file is malformed."""
        self.write_cgroup(cgroup, current=self.MIB)
        (cgroup / "memory.stat").write_text("inactive_file nope\n")

        with mock.patch(
            "psutil.virtual_memory", return_value=self.host_memory()
        ) as mock_virtual_memory:
            result = await Memory().get_result()

        mock_virtual_memory.assert_called_once_with()
        assert result.error is not None
        assert isinstance(result.error, ServiceWarning)
        assert "8.0GiB" in str(result.error)

    def test_read__cgroup_v2(self, monkeypatch, tmp_path):
        """Read the cgroup v2 directory of the current process."""
        proc_self_cgroup = tmp_path / "cgroup"
        proc_self_cgroup.write_text("0::/docker/abc\n")
        monkeypatch.setattr("health_check.contrib.psutil._CgroupMemory.ROOT", tmp_path)
        monkeypatch.setattr(
            "health_check.contrib.psutil._CgroupMemory.PROC_SELF_CGROUP",
            proc_self_cgroup,
        )
        cgroup = tmp_path / "docker/abc"
        cgroup.mkdir(parents=True)
        self.write_cgroup(cgroup, current=self.MIB)

        assert _CgroupMemory.read().total == self.GIB

    def test_read__cgroup_v1_falls_back_to_host(self, monkeypatch, tmp_path):
        """Return None on a cgroup v1 host without a v2 memory limit."""
        proc_self_cgroup = tmp_path / "cgroup"
        proc_self_cgroup.write_text("12:memory:/docker/abc\n")
        monkeypatch.setattr("health_check.contrib.psutil._CgroupMemory.ROOT", tmp_path)
        monkeypatch.setattr(
            "health_check.contrib.psutil._CgroupMemory.PROC_SELF_CGROUP",
            proc_self_cgroup,
        )

        assert _CgroupMemory.read() is None

    def test_read__proc_self_cgroup_unavailable(self, monkeypatch, tmp_path):
        """Return None when /proc/self/cgroup cannot be read."""
        monkeypatch.setattr("health_check.contrib.psutil._CgroupMemory.ROOT", tmp_path)
        monkeypatch.setattr(
            "health_check.contrib.psutil._CgroupMemory.PROC_SELF_CGROUP",
            tmp_path / "missing",
        )

        assert _CgroupMemory.read() is None

    def test_read__zero_limit(self, monkeypatch, tmp_path):
        """Return None when the cgroup memory limit is zero."""
        proc_self_cgroup = tmp_path / "cgroup"
        proc_self_cgroup.write_text("0::/\n")
        monkeypatch.setattr("health_check.contrib.psutil._CgroupMemory.ROOT", tmp_path)
        monkeypatch.setattr(
            "health_check.contrib.psutil._CgroupMemory.PROC_SELF_CGROUP",
            proc_self_cgroup,
        )
        self.write_cgroup(tmp_path, limit=0)

        assert _CgroupMemory.read() is None

    def test_read__inactive_file_exceeds_current(self, monkeypatch, tmp_path):
        """Never report negative cgroup memory usage."""
        proc_self_cgroup = tmp_path / "cgroup"
        proc_self_cgroup.write_text("0::/\n")
        monkeypatch.setattr("health_check.contrib.psutil._CgroupMemory.ROOT", tmp_path)
        monkeypatch.setattr(
            "health_check.contrib.psutil._CgroupMemory.PROC_SELF_CGROUP",
            proc_self_cgroup,
        )
        self.write_cgroup(tmp_path, current=self.MIB, inactive_file=2 * self.MIB)

        memory = _CgroupMemory.read()

        assert memory.available == self.GIB
        assert memory.percent == 0.0

    def test_read__memory_stat_without_inactive_file(self, monkeypatch, tmp_path):
        """Treat memory.stat without inactive_file as having no reclaimable memory."""
        proc_self_cgroup = tmp_path / "cgroup"
        proc_self_cgroup.write_text("0::/\n")
        monkeypatch.setattr("health_check.contrib.psutil._CgroupMemory.ROOT", tmp_path)
        monkeypatch.setattr(
            "health_check.contrib.psutil._CgroupMemory.PROC_SELF_CGROUP",
            proc_self_cgroup,
        )
        self.write_cgroup(tmp_path, current=self.MIB)
        (tmp_path / "memory.stat").write_text("anon 0\n")

        memory = _CgroupMemory.read()

        assert memory.available == self.GIB - self.MIB


class TestBattery:
    """Test the Battery health check."""

    @pytest.mark.asyncio
    async def test_run_check__battery_ok_when_available(self):
        """Battery check succeeds when battery is above threshold and plugged in."""
        battery_info = sbattery(percent=85.0, secsleft=3600, power_plugged=True)

        with mock.patch("psutil.sensors_battery", return_value=battery_info):
            check = Battery(min_percent_available=20.0, power_plugged=False)
            result = await check.get_result()
            assert result.error is None

    @pytest.mark.asyncio
    async def test_check_status__battery_below_threshold(self):
        """Raise ServiceWarning when battery is below minimum threshold."""
        battery_info = sbattery(percent=15.0, secsleft=600, power_plugged=False)

        with mock.patch("psutil.sensors_battery", return_value=battery_info):
            check = Battery(min_percent_available=20.0, power_plugged=False)
            result = await check.get_result()
            assert result.error is not None
            assert isinstance(result.error, ServiceWarning)
            assert "15.0" in str(result.error)

    @pytest.mark.asyncio
    async def test_check_status__power_unplugged_when_required(self):
        """Raise ServiceWarning when power is unplugged and power_plugged is True."""
        battery_info = sbattery(percent=85.0, secsleft=3600, power_plugged=False)

        with mock.patch("psutil.sensors_battery", return_value=battery_info):
            check = Battery(min_percent_available=None, power_plugged=True)
            result = await check.get_result()
            assert result.error is not None
            assert isinstance(result.error, ServiceWarning)
            assert "unplugged" in str(result.error).lower()
            assert "85.0" in str(result.error)

    @pytest.mark.asyncio
    async def test_check_status__both_conditions_fail(self):
        """Raise ServiceWarning when both battery low and power unplugged."""
        battery_info = sbattery(percent=15.0, secsleft=600, power_plugged=False)

        with mock.patch("psutil.sensors_battery", return_value=battery_info):
            check = Battery(min_percent_available=20.0, power_plugged=True)
            result = await check.get_result()
            assert result.error is not None
            assert isinstance(result.error, ServiceWarning)

    @pytest.mark.asyncio
    async def test_check_status__battery_not_available(self):
        """Raise ServiceUnavailable when battery info is not available."""
        with mock.patch(
            "psutil.sensors_battery", side_effect=AttributeError("Not supported")
        ):
            check = Battery()
            result = await check.get_result()
            assert result.error is not None
            assert isinstance(result.error, ServiceUnavailable)

    @pytest.mark.asyncio
    async def test_check_status__battery_value_error(self):
        """Raise ServiceReturnedUnexpectedResult when ValueError is raised."""
        with mock.patch("psutil.sensors_battery", side_effect=ValueError("Invalid")):
            check = Battery()
            result = await check.get_result()
            assert result.error is not None
            assert isinstance(result.error, ServiceReturnedUnexpectedResult)

    @pytest.mark.asyncio
    async def test_check_status__battery_checks_disabled(self):
        """No warning when all battery checks are disabled."""
        battery_info = sbattery(percent=5.0, secsleft=300, power_plugged=False)

        with mock.patch("psutil.sensors_battery", return_value=battery_info):
            check = Battery(min_percent_available=None, power_plugged=False)
            result = await check.get_result()
            assert result.error is None


class TestCPU:
    """Test the CPU health check."""

    @pytest.mark.asyncio
    async def test_run_check__cpu_usage_ok(self):
        """CPU check succeeds when usage is below threshold."""
        with mock.patch("psutil.cpu_percent", return_value=50.0):
            check = CPU(max_usage_percent=95.0)
            result = await check.get_result()
            assert result.error is None

    @pytest.mark.asyncio
    async def test_run_check__cpu_with_interval(self):
        """CPU check succeeds with explicit interval measurement."""
        with mock.patch("psutil.cpu_percent", return_value=50.0):
            check = CPU(
                max_usage_percent=95.0, interval=datetime.timedelta(seconds=0.1)
            )
            result = await check.get_result()
            assert result.error is None

    @pytest.mark.asyncio
    async def test_check_status__cpu_exceeds_threshold(self):
        """Raise ServiceWarning when CPU usage exceeds threshold."""
        with mock.patch("psutil.cpu_percent", return_value=95.5):
            check = CPU(max_usage_percent=90.0)
            result = await check.get_result()
            assert result.error is not None
            assert isinstance(result.error, ServiceWarning)
            assert "95.5" in str(result.error)

    @pytest.mark.asyncio
    async def test_check_status__cpu_check_disabled(self):
        """No warning when CPU check is disabled."""
        with mock.patch("psutil.cpu_percent", return_value=99.9):
            check = CPU(max_usage_percent=None)
            result = await check.get_result()
            assert result.error is None

    @pytest.mark.asyncio
    async def test_check_status__cpu_value_error(self):
        """Raise ServiceReturnedUnexpectedResult when ValueError is raised."""
        with mock.patch("psutil.cpu_percent", side_effect=ValueError("Invalid")):
            check = CPU()
            result = await check.get_result()
            assert result.error is not None
            assert isinstance(result.error, ServiceReturnedUnexpectedResult)

    @pytest.mark.asyncio
    async def test_run_check__cpu_interval_conversion(self):
        """CPU check correctly converts timedelta to seconds."""
        interval = datetime.timedelta(seconds=0.1)
        check = CPU(interval=interval)

        with mock.patch("psutil.cpu_percent") as mock_cpu:
            mock_cpu.return_value = 50.0
            result = await check.get_result()
            mock_cpu.assert_called_once_with(interval=0.1)
            assert result.error is None


class TestTemperature:
    """Test the Temperature health check."""

    @pytest.mark.asyncio
    async def test_run_check__temperature_ok_with_device(self):
        """Temperature check succeeds when temps are below threshold."""
        sensor = shwtemp(label="Core 0", current=45.0, high=80.0, critical=90.0)
        temperatures = {"coretemp": [sensor]}

        with mock.patch("psutil.sensors_temperatures", return_value=temperatures):
            check = Temperature(device="coretemp", max_temperature_celsius=None)
            result = await check.get_result()
            assert result.error is None

    @pytest.mark.asyncio
    async def test_check_status__temperature_exceeds_max(self):
        """Raise ServiceWarning when temperature exceeds max threshold."""
        sensor = shwtemp(label="Core 0", current=85.0, high=90.0, critical=95.0)
        temperatures = {"coretemp": [sensor]}

        with mock.patch("psutil.sensors_temperatures", return_value=temperatures):
            check = Temperature(device="coretemp", max_temperature_celsius=80.0)
            result = await check.get_result()
            assert result.error is not None
            assert isinstance(result.error, ServiceWarning)
            assert "85.0" in str(result.error)
            assert "Core 0" in str(result.error)

    @pytest.mark.asyncio
    async def test_check_status__temperature_exceeds_sensor_high(self):
        """Raise ServiceWarning when temperature exceeds sensor's high threshold."""
        sensor = shwtemp(label="Core 0", current=85.0, high=80.0, critical=90.0)
        temperatures = {"coretemp": [sensor]}

        with mock.patch("psutil.sensors_temperatures", return_value=temperatures):
            # When max_temperature_celsius is None, use sensor.high
            check = Temperature(device="coretemp", max_temperature_celsius=None)
            result = await check.get_result()
            assert result.error is not None
            assert isinstance(result.error, ServiceWarning)
            assert "85.0" in str(result.error)

    @pytest.mark.asyncio
    async def test_check_status__temperature_all_devices(self):
        """Check all devices when device is None."""
        sensor1 = shwtemp(label="Core 0", current=45.0, high=80.0, critical=90.0)
        sensor2 = shwtemp(label="GPU", current=95.0, high=90.0, critical=100.0)
        temperatures = {"coretemp": [sensor1], "gpu": [sensor2]}

        with mock.patch("psutil.sensors_temperatures", return_value=temperatures):
            check = Temperature(device=None, max_temperature_celsius=90.0)
            result = await check.get_result()
            assert result.error is not None
            assert isinstance(result.error, ServiceWarning)
            assert "95.0" in str(result.error)

    @pytest.mark.asyncio
    async def test_check_status__temperature_device_not_found(self):
        """Raise ServiceUnavailable when specified device is not found."""
        temperatures = {"other_device": []}

        with mock.patch("psutil.sensors_temperatures", return_value=temperatures):
            check = Temperature(device="coretemp")
            result = await check.get_result()
            assert result.error is not None
            assert isinstance(result.error, ServiceUnavailable)
            assert "not found" in str(result.error).lower()

    @pytest.mark.asyncio
    async def test_check_status__temperature_not_available(self):
        """Raise ServiceUnavailable when temperature info is not available."""
        with mock.patch(
            "psutil.sensors_temperatures",
            side_effect=AttributeError("Not supported"),
        ):
            check = Temperature()
            result = await check.get_result()
            assert result.error is not None
            assert isinstance(result.error, ServiceUnavailable)

    @pytest.mark.asyncio
    async def test_check_status__temperature_multiple_sensors_in_device(self):
        """Check all sensors in a device."""
        sensor1 = shwtemp(label="Core 0", current=45.0, high=80.0, critical=90.0)
        sensor2 = shwtemp(label="Core 1", current=85.0, high=80.0, critical=90.0)
        temperatures = {"coretemp": [sensor1, sensor2]}

        with mock.patch("psutil.sensors_temperatures", return_value=temperatures):
            check = Temperature(device="coretemp", max_temperature_celsius=None)
            result = await check.get_result()
            assert result.error is not None
            assert isinstance(result.error, ServiceWarning)
            assert "Core 1" in str(result.error)
            assert "85.0" in str(result.error)
