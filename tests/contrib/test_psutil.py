import datetime
import tempfile
from unittest import mock

import pytest

pytest.importorskip("psutil")

import psutil

from health_check.contrib.psutil import Battery, CPU, Disk, Memory, Temperature
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
            mock_disk_usage_result = mock.MagicMock()
            mock_disk_usage_result.percent = 95.5
            mock_disk_usage.return_value = mock_disk_usage_result

            check = Disk(max_disk_usage_percent=90.0)
            result = await check.get_result()
            assert result.error is not None
            assert isinstance(result.error, ServiceWarning)
            assert "95.5" in str(result.error)

    @pytest.mark.asyncio
    async def test_check_status__disk_check_disabled(self):
        """No warning when disk usage check is disabled."""
        with mock.patch("psutil.disk_usage") as mock_disk_usage:
            mock_disk_usage_result = mock.MagicMock()
            mock_disk_usage_result.percent = 99.0
            mock_disk_usage.return_value = mock_disk_usage_result

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
            mock_memory = mock.MagicMock()
            mock_memory.available = 0.5 * (1024**3)
            mock_memory.total = 8 * (1024**3)
            mock_memory.percent = 95.0
            mock_virtual_memory.return_value = mock_memory

            check = Memory(min_gibibytes_available=1.0)
            result = await check.get_result()
            assert result.error is not None
            assert isinstance(result.error, ServiceWarning)
            assert "RAM" in str(result.error)

    @pytest.mark.asyncio
    async def test_check_status__max_memory_usage_exceeded(self):
        """Raise ServiceWarning when memory usage exceeds threshold."""
        with mock.patch("psutil.virtual_memory") as mock_virtual_memory:
            mock_memory = mock.MagicMock()
            mock_memory.available = 1 * (1024**3)
            mock_memory.total = 8 * (1024**3)
            mock_memory.percent = 95.0
            mock_virtual_memory.return_value = mock_memory

            check = Memory(max_memory_usage_percent=90.0)
            result = await check.get_result()
            assert result.error is not None
            assert isinstance(result.error, ServiceWarning)
            assert "95" in str(result.error)

    @pytest.mark.asyncio
    async def test_check_status__memory_checks_disabled(self):
        """No warning when memory checks are disabled."""
        with mock.patch("psutil.virtual_memory") as mock_virtual_memory:
            mock_memory = mock.MagicMock()
            mock_memory.available = 0.1 * (1024**3)
            mock_memory.total = 8 * (1024**3)
            mock_memory.percent = 99.0
            mock_virtual_memory.return_value = mock_memory

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


class TestBattery:
    """Test the Battery health check."""

    @pytest.mark.asyncio
    async def test_run_check__battery_ok_when_available(self):
        """Battery check succeeds when battery is above threshold and plugged in."""
        battery_info = mock.MagicMock()
        battery_info.percent = 85.0
        battery_info.power_plugged = True

        with mock.patch("psutil.sensors_battery", return_value=battery_info):
            check = Battery(min_percent_available=20.0, power_plugged=False)
            result = await check.get_result()
            assert result.error is None

    @pytest.mark.asyncio
    async def test_check_status__battery_below_threshold(self):
        """Raise ServiceWarning when battery is below minimum threshold."""
        battery_info = mock.MagicMock()
        battery_info.percent = 15.0
        battery_info.power_plugged = False

        with mock.patch("psutil.sensors_battery", return_value=battery_info):
            check = Battery(min_percent_available=20.0, power_plugged=False)
            result = await check.get_result()
            assert result.error is not None
            assert isinstance(result.error, ServiceWarning)
            assert "15.0" in str(result.error)

    @pytest.mark.asyncio
    async def test_check_status__power_unplugged_when_required(self):
        """Raise ServiceWarning when power is unplugged and power_plugged is True."""
        battery_info = mock.MagicMock()
        battery_info.percent = 85.0
        battery_info.power_plugged = False

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
        battery_info = mock.MagicMock()
        battery_info.percent = 15.0
        battery_info.power_plugged = False

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
        battery_info = mock.MagicMock()
        battery_info.percent = 5.0
        battery_info.power_plugged = False

        with mock.patch("psutil.sensors_battery", return_value=battery_info):
            check = Battery(min_percent_available=None, power_plugged=False)
            result = await check.get_result()
            assert result.error is None


class TestCPU:
    """Test the CPU health check."""

    @pytest.mark.asyncio
    async def test_run_check__cpu_usage_ok(self):
        """CPU check succeeds when usage is below threshold."""
        check = CPU(max_usage_percent=95.0)
        result = await check.get_result()
        # Real CPU usage should be well below 95% in test environment
        assert result.error is None

    @pytest.mark.asyncio
    async def test_run_check__cpu_with_interval(self):
        """CPU check succeeds with explicit interval measurement."""
        check = CPU(max_usage_percent=95.0, interval=datetime.timedelta(seconds=0.1))
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
        sensor = mock.MagicMock()
        sensor.label = "Core 0"
        sensor.current = 45.0
        sensor.high = 80.0

        temperatures = {"coretemp": [sensor]}

        with mock.patch("psutil.sensors_temperatures", return_value=temperatures):
            check = Temperature(device="coretemp", max_temperature_celsius=None)
            result = await check.get_result()
            assert result.error is None

    @pytest.mark.asyncio
    async def test_check_status__temperature_exceeds_max(self):
        """Raise ServiceWarning when temperature exceeds max threshold."""
        sensor = mock.MagicMock()
        sensor.label = "Core 0"
        sensor.current = 85.0
        sensor.high = 90.0

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
        sensor = mock.MagicMock()
        sensor.label = "Core 0"
        sensor.current = 85.0
        sensor.high = 80.0

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
        sensor1 = mock.MagicMock()
        sensor1.label = "Core 0"
        sensor1.current = 45.0
        sensor1.high = 80.0

        sensor2 = mock.MagicMock()
        sensor2.label = "GPU"
        sensor2.current = 95.0
        sensor2.high = 90.0

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
        sensor1 = mock.MagicMock()
        sensor1.label = "Core 0"
        sensor1.current = 45.0
        sensor1.high = 80.0

        sensor2 = mock.MagicMock()
        sensor2.label = "Core 1"
        sensor2.current = 85.0
        sensor2.high = 80.0

        temperatures = {"coretemp": [sensor1, sensor2]}

        with mock.patch("psutil.sensors_temperatures", return_value=temperatures):
            check = Temperature(device="coretemp", max_temperature_celsius=None)
            result = await check.get_result()
            assert result.error is not None
            assert isinstance(result.error, ServiceWarning)
            assert "Core 1" in str(result.error)
            assert "85.0" in str(result.error)
