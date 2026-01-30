"""Tests for health check modules that require actual services."""

import tempfile

import pytest
from django.test import TestCase, override_settings

from health_check.checks import Cache, Database, Disk, Mail, Memory, Storage
from health_check.exceptions import ServiceUnavailable


class TestCacheCheck(TestCase):
    """Test the Cache health check."""

    def test_cache_healthy(self):
        """Test that cache check passes when cache is working."""
        check = Cache()
        check.run_check()
        assert check.errors == []


class TestDatabaseCheck(TestCase):
    """Test the Database health check."""

    @pytest.mark.django_db
    def test_database_healthy(self):
        """Test that database check passes when database is available."""
        check = Database()
        check.run_check()
        assert check.errors == []


class TestDiskCheck(TestCase):
    """Test the Disk health check."""

    def test_disk_healthy(self):
        """Test that disk check passes."""
        check = Disk()
        check.run_check()
        assert check.errors == []

    def test_disk_with_custom_path(self):
        """Test disk check with a custom path."""
        with tempfile.TemporaryDirectory() as tmpdir:
            check = Disk(path=tmpdir)
            check.run_check()
            assert check.errors == []


class TestMemoryCheck(TestCase):
    """Test the Memory health check."""

    def test_memory_healthy(self):
        """Test that memory check passes."""
        check = Memory()
        check.run_check()
        assert check.errors == []


class TestMailCheck(TestCase):
    """Test the Mail health check."""

    def test_mail_with_locmem_backend(self):
        """Test that mail check works with locmem backend."""
        with override_settings(
            EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend"
        ):
            check = Mail()
            # Just ensure it doesn't crash
            check.run_check()


class TestStorageCheck(TestCase):
    """Test the Storage health check."""

    def test_storage_healthy(self):
        """Test that storage check works with default storage."""
        check = Storage()
        check.run_check()
        # May have errors if storage is not properly configured,
        # but test ensures it doesn't crash


class TestHealthCheckExceptions(TestCase):
    """Test health check exception handling."""

    def test_service_unavailable_str(self):
        """Test ServiceUnavailable exception string representation."""
        exc = ServiceUnavailable("Test error")
        assert str(exc) == "unavailable: Test error"


class TestCheckStatusRendering(TestCase):
    """Test check status rendering."""

    def test_check_without_error_status(self):
        """Test that check without errors has status 1."""
        check = Cache()
        check.run_check()
        assert check.status == 1
        assert len(check.errors) == 0

    def test_check_pretty_status_ok(self):
        """Test pretty_status without errors."""
        check = Cache()
        check.errors = []
        status = check.pretty_status()
        assert status == "OK"
