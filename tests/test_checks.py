"""Integration tests for health check implementations."""

import tempfile

import pytest
from django.test import TestCase, override_settings

from health_check.checks import Cache, Database, Disk, Mail, Memory, Storage
from health_check.exceptions import ServiceUnavailable


class TestCache(TestCase):
    """Test the Cache health check."""

    def test_run_check__cache_working(self):
        """Cache backend successfully sets and retrieves values."""
        check = Cache()
        check.run_check()
        assert check.errors == [], "Cache should have no errors"


class TestDatabase(TestCase):
    """Test the Database health check."""

    @pytest.mark.django_db
    def test_run_check__database_available(self):
        """Database connection returns successful query result."""
        check = Database()
        check.run_check()
        assert check.errors == [], "Database should have no errors"


class TestDisk(TestCase):
    """Test the Disk health check."""

    def test_run_check__disk_accessible(self):
        """Disk space check completes successfully."""
        check = Disk()
        check.run_check()
        assert check.errors == [], "Disk should have no errors"

    def test_run_check__custom_path(self):
        """Disk check succeeds with custom path."""
        with tempfile.TemporaryDirectory() as tmpdir:
            check = Disk(path=tmpdir)
            check.run_check()
            assert check.errors == [], "Custom path should have no errors"


class TestMemory(TestCase):
    """Test the Memory health check."""

    def test_run_check__memory_available(self):
        """Memory check completes successfully."""
        check = Memory()
        check.run_check()
        assert check.errors == [], "Memory should have no errors"


class TestMail(TestCase):
    """Test the Mail health check."""

    def test_run_check__locmem_backend(self):
        """Mail check completes with locmem backend."""
        with override_settings(
            EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend"
        ):
            check = Mail()
            check.run_check()


class TestStorage(TestCase):
    """Test the Storage health check."""

    def test_run_check__default_storage(self):
        """Storage check completes without exceptions."""
        check = Storage()
        check.run_check()


class TestServiceUnavailable(TestCase):
    """Test ServiceUnavailable exception formatting."""

    def test_str__exception_message(self):
        """Format exception with message type prefix."""
        exc = ServiceUnavailable("Test error")
        assert str(exc) == "unavailable: Test error", (
            "Should format with 'unavailable' prefix"
        )


class TestCheckStatus(TestCase):
    """Test check status and rendering."""

    def test_status__without_errors(self):
        """Status returns 1 when no errors are present."""
        check = Cache()
        check.run_check()
        assert check.status == 1, "Status should be 1 for healthy check"
        assert len(check.errors) == 0, "Should have no errors"

    def test_pretty_status__no_errors(self):
        """Return 'OK' when no errors are present."""
        check = Cache()
        check.errors = []
        assert check.pretty_status() == "OK", "Should display 'OK' for healthy check"
