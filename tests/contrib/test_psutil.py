import tempfile
from unittest import mock

import pytest

pytest.importorskip("psutil")

from health_check import Disk, Memory
from health_check.exceptions import ServiceReturnedUnexpectedResult, ServiceWarning


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
