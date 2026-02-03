import pytest

from health_check.base import HealthCheck


class TestHealthCheck:
    def test_check_status__not_implemented(self):
        """Raise NotImplementedError when check_status is not implemented."""
        with pytest.raises(NotImplementedError):
            HealthCheck().check_status()

    def test_run_check__success(self):
        """Execute check_status without errors."""

        class SuccessCheck(HealthCheck):
            async def run(self):
                pass

        check = SuccessCheck()
        check.run_check()
        assert check.errors == []

    def test_run_check__unexpected_exception_reraised(self):
        """Re-raise unexpected exceptions that are not HealthCheckException."""

        class UnexpectedErrorCheck(HealthCheck):
            async def run(self):
                raise RuntimeError("Unexpected error")

        check = UnexpectedErrorCheck()
        with pytest.raises(RuntimeError) as exc_info:
            check.run_check()
        assert str(exc_info.value) == "Unexpected error"

    def test_status__healthy(self):
        """Return 1 when no errors are present."""
        ht = HealthCheck()
        assert ht.status == 1

    def test_status__unhealthy(self):
        """Return 0 when errors are present."""
        ht = HealthCheck()
        ht.errors = [1]
        assert ht.status == 0

    def test_pretty_status__no_errors(self):
        """Return 'OK' when no errors are present."""
        ht = HealthCheck()
        assert ht.pretty_status() == "OK"

    def test_pretty_status__single_error(self):
        """Return error string when single error exists."""
        ht = HealthCheck()
        ht.errors = ["foo"]
        assert ht.pretty_status() == "foo"

    def test_pretty_status__multiple_errors(self):
        """Return newline-separated errors when multiple errors exist."""
        ht = HealthCheck()
        ht.errors = ["foo", "bar", 123]
        assert ht.pretty_status() == "foo\nbar\n123"
