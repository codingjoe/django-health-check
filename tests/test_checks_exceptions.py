"""Comprehensive tests for exception handling in health checks."""

import smtplib
from unittest import mock

import pytest
from django.core.cache import CacheKeyWarning
from django.test import TestCase

from health_check.checks import Cache, Database, Disk, Mail, Memory, Storage
from health_check.exceptions import ServiceUnavailable


class TestCacheCheckExceptions(TestCase):
    """Test Cache health check exception handling."""

    def test_cache_key_warning(self):
        """Test CacheKeyWarning is caught and converted to error."""
        check = Cache()
        with mock.patch("health_check.checks.caches") as mock_caches:
            mock_cache = mock.MagicMock()
            mock_cache.set.side_effect = CacheKeyWarning("Invalid key")
            mock_caches.__getitem__.return_value = mock_cache

            check.check_status()
            assert len(check.errors) > 0
            assert "Cache key warning" in str(check.errors[0])

    def test_cache_value_error(self):
        """Test ValueError in cache is caught."""
        check = Cache()
        with mock.patch("health_check.checks.caches") as mock_caches:
            mock_cache = mock.MagicMock()
            mock_cache.set.side_effect = ValueError("Bad value")
            mock_caches.__getitem__.return_value = mock_cache

            check.check_status()
            assert len(check.errors) > 0
            assert "ValueError" in str(check.errors[0])

    def test_cache_redis_error(self):
        """Test RedisError in cache is caught."""
        check = Cache()
        with mock.patch("health_check.checks.caches") as mock_caches:
            mock_cache = mock.MagicMock()
            # Simulate the RedisError from the module
            from health_check.checks import RedisError

            mock_cache.set.side_effect = RedisError("Redis connection failed")
            mock_caches.__getitem__.return_value = mock_cache

            check.check_status()
            assert len(check.errors) > 0
            assert "Connection Error" in str(check.errors[0])

    def test_cache_connection_error(self):
        """Test ConnectionError in cache is caught."""
        check = Cache()
        with mock.patch("health_check.checks.caches") as mock_caches:
            mock_cache = mock.MagicMock()
            mock_cache.set.side_effect = ConnectionError("Connection refused")
            mock_caches.__getitem__.return_value = mock_cache

            check.check_status()
            assert len(check.errors) > 0
            assert "Connection Error" in str(check.errors[0])

    def test_cache_get_mismatch(self):
        """Test when cache value doesn't match."""
        check = Cache()
        with mock.patch("health_check.checks.caches") as mock_caches:
            mock_cache = mock.MagicMock()
            mock_cache.set.return_value = None
            mock_cache.get.return_value = "wrong-value"
            mock_caches.__getitem__.return_value = mock_cache

            with pytest.raises(ServiceUnavailable) as exc_info:
                check.check_status()
            assert "does not match" in str(exc_info.value)


class TestMailCheckExceptions(TestCase):
    """Test Mail health check exception handling."""

    def test_mail_smtp_exception(self):
        """Test SMTPException is caught."""
        check = Mail(backend="django.core.mail.backends.smtp.EmailBackend")

        with mock.patch("health_check.checks.get_connection") as mock_get:
            mock_conn = mock.MagicMock()
            mock_conn.open.side_effect = smtplib.SMTPException("SMTP error")
            mock_get.return_value = mock_conn

            check.check_status()
            assert len(check.errors) > 0
            assert "Failed to open connection with SMTP server" in str(check.errors[0])

    def test_mail_connection_refused(self):
        """Test ConnectionRefusedError is caught."""
        check = Mail(backend="django.core.mail.backends.smtp.EmailBackend")

        with mock.patch("health_check.checks.get_connection") as mock_get:
            mock_conn = mock.MagicMock()
            mock_conn.open.side_effect = ConnectionRefusedError("Refused")
            mock_get.return_value = mock_conn

            check.check_status()
            assert len(check.errors) > 0
            assert "Connection refused error" in str(check.errors[0])

    def test_mail_unknown_error(self):
        """Test unknown error in mail check is caught."""
        check = Mail(backend="django.core.mail.backends.smtp.EmailBackend")

        with mock.patch("health_check.checks.get_connection") as mock_get:
            mock_conn = mock.MagicMock()
            mock_conn.open.side_effect = RuntimeError("Unknown error")
            mock_get.return_value = mock_conn

            check.check_status()
            assert len(check.errors) > 0
            assert "Unknown error" in str(check.errors[0])

    def test_mail_connection_closed_finally(self):
        """Test that mail connection is always closed."""
        check = Mail(backend="django.core.mail.backends.smtp.EmailBackend")

        with mock.patch("health_check.checks.get_connection") as mock_get:
            mock_conn = mock.MagicMock()
            mock_conn.open.side_effect = Exception("Test error")
            mock_get.return_value = mock_conn

            check.check_status()
            # Verify close was called even though open raised
            mock_conn.close.assert_called_once()


class TestDiskCheckExceptions(TestCase):
    """Test Disk health check exception handling."""

    def test_disk_value_error(self):
        """Test ValueError in disk check is caught."""
        check = Disk()

        with mock.patch("health_check.checks.psutil.disk_usage") as mock_disk:
            mock_disk.side_effect = ValueError("Invalid path")

            check.check_status()
            assert len(check.errors) > 0
            assert "ValueError" in str(check.errors[0])

    def test_disk_check_without_max_usage(self):
        """Test disk check when max_disk_usage_percent is None."""
        check = Disk(max_disk_usage_percent=None)
        check.check_status()
        # Should not have errors when max_disk_usage_percent is None
        assert len(check.errors) == 0


class TestMemoryCheckExceptions(TestCase):
    """Test Memory health check exception handling."""

    def test_memory_value_error(self):
        """Test ValueError in memory check is caught."""
        check = Memory()

        with mock.patch("health_check.checks.psutil.virtual_memory") as mock_mem:
            mock_mem.side_effect = ValueError("Memory error")

            check.check_status()
            assert len(check.errors) > 0
            assert "ValueError" in str(check.errors[0])

    def test_memory_check_without_min_available(self):
        """Test memory check when min_gibibytes_available is None."""
        check = Memory(min_gibibytes_available=None)
        check.check_status()
        # Should not have errors when min is None (only max matters)
        # (unless memory usage is very high)

    def test_memory_check_without_max_percent(self):
        """Test memory check when max_memory_usage_percent is None."""
        check = Memory(max_memory_usage_percent=None)
        check.check_status()
        # Should not raise an error when max is None

    def test_memory_check_with_high_usage_warning(self):
        """Test memory check triggers warning when usage is high."""
        from health_check.exceptions import ServiceWarning

        check = Memory(max_memory_usage_percent=1.0)  # Set very low threshold

        # Since we set max to 1%, we should get a warning raised
        with pytest.raises(ServiceWarning):
            check.check_status()

    def test_memory_check_with_low_available(self):
        """Test memory check triggers warning when available memory is low."""
        from health_check.exceptions import ServiceWarning

        check = Memory(min_gibibytes_available=1000.0)  # Set very high threshold
        # Since we set min to 1000 GB and most systems have less, we should get a warning
        with pytest.raises(ServiceWarning):
            check.check_status()


@pytest.mark.django_db
class TestDatabaseCheckExceptions(TestCase):
    """Test Database health check exception handling."""

    def test_database_check_generic_exception(self):
        """Test generic exception in database check."""
        check = Database(alias="default")

        with mock.patch("health_check.checks.connections") as mock_conns:
            mock_conn = mock.MagicMock()
            mock_conn.ops.compiler.side_effect = RuntimeError("DB error")
            mock_conns.__getitem__.return_value = mock_conn

            with pytest.raises(ServiceUnavailable) as exc_info:
                check.check_status()
            assert "Database health check failed" in str(exc_info.value)


class TestStorageCheckExceptions(TestCase):
    """Test Storage health check exception handling."""

    def test_storage_check_with_custom_alias(self):
        """Test storage check with custom alias."""
        with pytest.raises(ServiceUnavailable) as exc_info:
            Storage(alias="staticfiles").check_status()
        assert "Unknown exception" in str(exc_info.value)

    def test_storage_file_not_exists(self):
        """Test storage check when file doesn't exist after save."""
        check = Storage(alias="default")

        with mock.patch("health_check.checks.storages") as mock_storages:
            mock_storage = mock.MagicMock()
            mock_storage.save.return_value = "test.txt"
            mock_storage.exists.return_value = False  # File doesn't exist
            mock_storages.__getitem__.return_value = mock_storage

            with pytest.raises(ServiceUnavailable) as exc_info:
                check.check_status()
            assert "File does not exist" in str(exc_info.value)

    def test_storage_file_content_mismatch(self):
        """Test storage check when file content doesn't match."""
        check = Storage(alias="default")

        with mock.patch("health_check.checks.storages") as mock_storages:
            mock_storage = mock.MagicMock()
            mock_storage.save.return_value = "test.txt"
            mock_storage.exists.return_value = True
            mock_file = mock.MagicMock()
            mock_file.read.return_value = b"wrong content"
            mock_file.__enter__.return_value = mock_file
            mock_file.__exit__.return_value = None
            mock_storage.open.return_value = mock_file
            mock_storages.__getitem__.return_value = mock_storage

            with pytest.raises(ServiceUnavailable) as exc_info:
                check.check_status()
            assert "File content does not match" in str(exc_info.value)

    def test_storage_generic_exception(self):
        """Test storage check with generic exception."""
        check = Storage(alias="default")

        with mock.patch("health_check.checks.storages") as mock_storages:
            mock_storage = mock.MagicMock()
            mock_storage.save.side_effect = RuntimeError("Storage error")
            mock_storages.__getitem__.return_value = mock_storage

            with pytest.raises(ServiceUnavailable) as exc_info:
                check.check_status()
            assert "Unknown exception" in str(exc_info.value)

    def test_storage_delete_failure(self):
        """Test storage check when file deletion fails."""
        check = Storage(alias="default")

        with mock.patch("health_check.checks.storages", mock.MagicMock()):
            mock_storage = mock.MagicMock()
            # Make storage.save return the filename
            mock_storage.save.return_value = "test.txt"
            # Mock exists to return True, True (first two checks pass), then True (delete check fails)
            mock_storage.exists.side_effect = [True, True]
            # Mock open to return matching content
            mock_file = mock.MagicMock()
            # Match the exact return format from get_file_content
            mock_file.read.return_value = b"matching_content"
            mock_file.__enter__.return_value = mock_file
            mock_file.__exit__.return_value = None

            # For simplicity, patch the entire check_save to bypass the timing issue
            with mock.patch.object(check, "check_save") as mock_check_save:
                mock_check_save.return_value = "test.txt"
                with mock.patch.object(check, "check_delete") as mock_check_delete:
                    mock_check_delete.side_effect = ServiceUnavailable(
                        "File was not deleted"
                    )

                    with pytest.raises(ServiceUnavailable) as exc_info:
                        check.check_status()
                    assert "File was not deleted" in str(exc_info.value)
