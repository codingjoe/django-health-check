import asyncio
import dataclasses
from unittest.mock import MagicMock, patch

import pytest

from health_check.base import HealthCheck, HealthCheckResult
from health_check.exceptions import HealthCheckException


class TestHealthCheck:
    @pytest.mark.asyncio
    async def test_run__success(self):
        """Execute run without errors."""

        class SuccessCheck(HealthCheck):
            async def run(self):
                pass

        check = SuccessCheck()
        result = await check.get_result()
        assert result.error is None
        assert isinstance(result, HealthCheckResult)
        assert result.check is check

    @pytest.mark.asyncio
    async def test_run__unexpected_exception_handled(self):
        """Catch unexpected exceptions and convert to HealthCheckException."""

        class UnexpectedErrorCheck(HealthCheck):
            async def run(self):
                raise RuntimeError("Unexpected error")

        check = UnexpectedErrorCheck()
        result = await check.get_result()
        assert result.error is not None
        assert isinstance(result.error, HealthCheckException)
        assert str(result.error) == "Unknown Error: unknown error"

    @pytest.mark.asyncio
    async def test_run__sync_check(self):
        """Execute synchronous run method in thread."""

        class SyncCheck(HealthCheck):
            def run(self):
                pass

        check = SyncCheck()
        result = await check.get_result()
        assert result.error is None
        assert isinstance(result, HealthCheckResult)

    @pytest.mark.asyncio
    async def test_run__sync_check_uses_custom_executor(self):
        """Pass custom executor to run_in_executor for synchronous checks."""

        class SyncCheck(HealthCheck):
            def run(self):
                pass

        check = SyncCheck()
        custom_executor = MagicMock()
        loop = asyncio.get_running_loop()
        with patch.object(loop, "run_in_executor", wraps=loop.run_in_executor) as mock:
            await check.get_result(executor=custom_executor)
        mock.assert_called_once_with(custom_executor, check.run)

    @pytest.mark.asyncio
    async def test_run__sync_check_default_executor(self):
        """Use default executor (None) for synchronous checks when none is supplied."""

        class SyncCheck(HealthCheck):
            def run(self):
                pass

        check = SyncCheck()
        loop = asyncio.get_running_loop()
        with patch.object(loop, "run_in_executor", wraps=loop.run_in_executor) as mock:
            result = await check.get_result()
        mock.assert_called_once_with(None, check.run)
        assert result.error is None

    @pytest.mark.asyncio
    async def test_result__timing(self):
        """Result includes execution time."""

        class SlowCheck(HealthCheck):
            async def run(self):
                import asyncio

                await asyncio.sleep(0.01)

        check = SlowCheck()
        result = await check.get_result()
        assert result.time_taken > 0

    def test_labels(self):
        """Labels include class name and dataclass fields, excluding secret fields."""

        @dataclasses.dataclass
        class LabeledCheck(HealthCheck):
            foo: str = "bar"
            version: float = 1.0
            secret_key: str = dataclasses.field(default="secret", repr=False)
            missing_value: str | None = None

            async def run(self):
                pass

        check = LabeledCheck()
        assert check.labels == {"check": "LabeledCheck", "foo": "bar", "version": "1.0"}
