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
        result = await check.result
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
        result = await check.result
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
        result = await check.result
        assert result.error is None
        assert isinstance(result, HealthCheckResult)

    @pytest.mark.asyncio
    async def test_result__timing(self):
        """Result includes execution time."""

        class SlowCheck(HealthCheck):
            async def run(self):
                import asyncio
                await asyncio.sleep(0.01)

        check = SlowCheck()
        result = await check.result
        assert result.time_taken > 0
