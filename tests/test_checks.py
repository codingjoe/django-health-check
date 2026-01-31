"""Integration tests for health check implementations."""

import logging
import tempfile
from unittest import mock

import pytest
from django.core.cache import CacheKeyWarning
from django.test import override_settings

from health_check.checks import DNS, Cache, Database, Disk, Mail, Memory, Storage
from health_check.exceptions import (
    ServiceReturnedUnexpectedResult,
    ServiceUnavailable,
    ServiceWarning,
)


class TestCache:
    """Test the Cache health check."""

    def test_run_check__cache_working(self):
        """Cache backend successfully sets and retrieves values."""
        check = Cache()
        check.run_check()
        assert check.errors == []


class TestDatabase:
    """Test the Database health check."""

    @pytest.mark.django_db
    def test_run_check__database_available(self):
        """Database connection returns successful query result."""
        check = Database()
        check.run_check()
        assert check.errors == []


class TestDNS:
    """Test the DNS health check."""

    def test_run_check__dns_working(self):
        """DNS resolution completes successfully for localhost."""
        check = DNS(hostname="localhost")
        check.run_check()
        assert check.errors == []

    def test_run_check__system_hostname(self):
        """DNS resolution completes successfully for system hostname."""
        # This tests the default behavior using socket.gethostname()
        check = DNS()
        check.run_check()
        # We don't assert no errors because the system hostname might not be resolvable
        # in all environments, but the check should complete without crashing


class TestDisk:
    """Test the Disk health check."""

    def test_run_check__disk_accessible(self):
        """Disk space check completes successfully."""
        check = Disk()
        check.run_check()
        assert check.errors == []

    def test_run_check__custom_path(self):
        """Disk check succeeds with custom path."""
        with tempfile.TemporaryDirectory() as tmpdir:
            check = Disk(path=tmpdir)
            check.run_check()
            assert check.errors == []


class TestMemory:
    """Test the Memory health check."""

    def test_run_check__memory_available(self):
        """Memory check completes successfully."""
        check = Memory()
        check.run_check()
        assert check.errors == []


class TestMail:
    """Test the Mail health check."""

    def test_run_check__locmem_backend(self):
        """Mail check completes with locmem backend."""
        with override_settings(
            EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend"
        ):
            check = Mail()
            check.run_check()


class TestStorage:
    """Test the Storage health check."""

    def test_run_check__default_storage(self):
        """Storage check completes without exceptions."""
        check = Storage()
        check.run_check()


class TestServiceUnavailable:
    """Test ServiceUnavailable exception formatting."""

    def test_str__exception_message(self):
        """Format exception with message type prefix."""
        exc = ServiceUnavailable("Test error")
        assert str(exc) == "Unavailable: Test error"


class TestCheckStatus:
    """Test check status and rendering."""

    def test_status__without_errors(self):
        """Status returns 1 when no errors are present."""
        check = Cache()
        check.run_check()
        assert check.status == 1
        assert len(check.errors) == 0

    def test_pretty_status__no_errors(self):
        """Return 'OK' when no errors are present."""
        check = Cache()
        check.errors = []
        assert check.pretty_status() == "OK"


class TestCacheExceptionHandling:
    """Test Cache exception handling for uncovered code paths."""

    def test_check_status__cache_key_warning(self):
        """Raise ServiceReturnedUnexpectedResult when CacheKeyWarning is raised during set."""
        with mock.patch("health_check.checks.caches") as mock_caches:
            mock_cache = mock.MagicMock()
            mock_caches.__getitem__.return_value = mock_cache
            mock_cache.set.side_effect = CacheKeyWarning("Invalid key")

            check = Cache()
            with pytest.raises(ServiceReturnedUnexpectedResult) as exc_info:
                check.check_status()
            assert "Cache key warning" in str(exc_info.value)

    def test_check_status__value_error(self):
        """Raise ServiceReturnedUnexpectedResult when ValueError is raised during cache operation."""
        with mock.patch("health_check.checks.caches") as mock_caches:
            mock_cache = mock.MagicMock()
            mock_caches.__getitem__.return_value = mock_cache
            mock_cache.set.side_effect = ValueError("Invalid value")

            check = Cache()
            with pytest.raises(ServiceReturnedUnexpectedResult) as exc_info:
                check.check_status()
            assert "ValueError" in str(exc_info.value)

    def test_check_status__connection_error(self):
        """Raise ServiceReturnedUnexpectedResult when ConnectionError is raised during cache operation."""
        with mock.patch("health_check.checks.caches") as mock_caches:
            mock_cache = mock.MagicMock()
            mock_caches.__getitem__.return_value = mock_cache
            mock_cache.set.side_effect = ConnectionError("Connection failed")

            check = Cache()
            with pytest.raises(ServiceReturnedUnexpectedResult) as exc_info:
                check.check_status()
            assert "Connection Error" in str(exc_info.value)

    def test_check_status__cache_value_mismatch(self):
        """Raise ServiceUnavailable when cached value does not match set value."""
        with mock.patch("health_check.checks.caches") as mock_caches:
            mock_cache = mock.MagicMock()
            mock_caches.__getitem__.return_value = mock_cache
            mock_cache.set.return_value = None
            mock_cache.get.return_value = "wrong-value"

            check = Cache()
            with pytest.raises(ServiceUnavailable) as exc_info:
                check.check_status()
            assert "does not match" in str(exc_info.value)


class TestDatabaseExceptionHandling:
    """Test Database exception handling for uncovered code paths."""

    @pytest.mark.django_db
    def test_check_status__query_returns_unexpected_result(self):
        """Raise ServiceUnavailable when query does not return (1,)."""
        with mock.patch("health_check.checks.connections") as mock_connections:
            mock_connection = mock.MagicMock()
            mock_connections.__getitem__.return_value = mock_connection
            mock_cursor = mock.MagicMock()
            mock_connection.cursor.return_value.__enter__.return_value = mock_cursor
            mock_cursor.fetchone.return_value = (0,)
            mock_connection.ops.compiler.return_value = mock.MagicMock(
                return_value=mock.MagicMock(compile=lambda x: ("SELECT 0", []))
            )

            check = Database()
            with pytest.raises(ServiceUnavailable) as exc_info:
                check.check_status()
            assert "did not return the expected result" in str(exc_info.value)

    @pytest.mark.django_db
    def test_check_status__database_exception(self):
        """Raise ServiceUnavailable on database exception."""
        with mock.patch("health_check.checks.connections") as mock_connections:
            mock_connection = mock.MagicMock()
            mock_connections.__getitem__.return_value = mock_connection
            mock_connection.ops.compiler.side_effect = RuntimeError("Database error")

            check = Database()
            with pytest.raises(ServiceUnavailable) as exc_info:
                check.check_status()
            assert "Database health check failed" in str(exc_info.value)


class TestDNSExceptionHandling:
    """Test DNS exception handling for uncovered code paths."""

    def test_check_status__nonexistent_hostname(self):
        """Raise ServiceUnavailable when hostname does not exist."""
        check = DNS(hostname="this-domain-does-not-exist-12345.invalid")
        check.run_check()
        assert len(check.errors) == 1
        assert "does not exist" in str(check.errors[0])


class TestDiskExceptionHandling:
    """Test Disk exception handling for uncovered code paths."""

    def test_check_status__disk_usage_exceeds_threshold(self):
        """Raise ServiceWarning when disk usage exceeds threshold."""
        with mock.patch("health_check.checks.psutil.disk_usage") as mock_disk_usage:
            mock_disk_usage_result = mock.MagicMock()
            mock_disk_usage_result.percent = 95.5
            mock_disk_usage.return_value = mock_disk_usage_result

            check = Disk(max_disk_usage_percent=90.0)
            with pytest.raises(ServiceWarning) as exc_info:
                check.check_status()
            assert "95.5" in str(exc_info.value)

    def test_check_status__disk_check_disabled(self):
        """No warning when disk usage check is disabled."""
        with mock.patch("health_check.checks.psutil.disk_usage") as mock_disk_usage:
            mock_disk_usage_result = mock.MagicMock()
            mock_disk_usage_result.percent = 99.0
            mock_disk_usage.return_value = mock_disk_usage_result

            check = Disk(max_disk_usage_percent=None)
            check.check_status()
            assert check.errors == []

    def test_check_status__disk_value_error(self):
        """Raise ServiceReturnedUnexpectedResult when ValueError is raised during disk check."""
        with mock.patch("health_check.checks.psutil.disk_usage") as mock_disk_usage:
            mock_disk_usage.side_effect = ValueError("Invalid path")

            check = Disk()
            with pytest.raises(ServiceReturnedUnexpectedResult):
                check.check_status()


class TestMailExceptionHandling:
    """Test Mail exception handling for uncovered code paths."""

    @override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
    def test_check_status__success(self, caplog):
        """Successfully open and close connection logs debug message."""
        with mock.patch("health_check.checks.get_connection") as mock_get_connection:
            mock_connection = mock.MagicMock()
            mock_get_connection.return_value = mock_connection
            mock_connection.open.return_value = None

            check = Mail()
            with caplog.at_level(logging.DEBUG, logger="health_check.checks"):
                check.check_status()
            assert check.errors == []
            # Verify debug logging was called
            assert any(
                "Trying to open connection to mail backend" in record.message
                or "Connection established" in record.message
                for record in caplog.records
            )

    @override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
    def test_check_status__smtp_exception(self):
        """Raise ServiceUnavailable when SMTPException is raised."""
        import smtplib

        with mock.patch("health_check.checks.get_connection") as mock_get_connection:
            mock_connection = mock.MagicMock()
            mock_get_connection.return_value = mock_connection
            mock_connection.open.side_effect = smtplib.SMTPException("SMTP error")

            check = Mail()
            with pytest.raises(ServiceUnavailable) as exc_info:
                check.check_status()
            assert "SMTP server" in str(exc_info.value)
            mock_connection.close.assert_called_once()

    @override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
    def test_check_status__connection_refused_error(self):
        """Raise ServiceUnavailable when ConnectionRefusedError is raised."""
        with mock.patch("health_check.checks.get_connection") as mock_get_connection:
            mock_connection = mock.MagicMock()
            mock_get_connection.return_value = mock_connection
            mock_connection.open.side_effect = ConnectionRefusedError(
                "Connection refused"
            )

            check = Mail()
            with pytest.raises(ServiceUnavailable) as exc_info:
                check.check_status()
            assert "Connection refused" in str(exc_info.value)
            mock_connection.close.assert_called_once()

    @override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
    def test_check_status__mail_unknown_exception(self):
        """Raise ServiceUnavailable for unknown exceptions during mail check."""
        with mock.patch("health_check.checks.get_connection") as mock_get_connection:
            mock_connection = mock.MagicMock()
            mock_get_connection.return_value = mock_connection
            mock_connection.open.side_effect = RuntimeError("Unknown error")

            check = Mail()
            with pytest.raises(ServiceUnavailable) as exc_info:
                check.check_status()
            assert "Unknown error" in str(exc_info.value)
            mock_connection.close.assert_called_once()


class TestMemoryExceptionHandling:
    """Test Memory exception handling for uncovered code paths."""

    def test_check_status__min_memory_available_exceeded(self):
        """Raise ServiceWarning when available memory is below threshold."""
        with mock.patch(
            "health_check.checks.psutil.virtual_memory"
        ) as mock_virtual_memory:
            mock_memory = mock.MagicMock()
            mock_memory.available = 0.5 * (1024**3)
            mock_memory.total = 8 * (1024**3)
            mock_memory.percent = 95.0
            mock_virtual_memory.return_value = mock_memory

            check = Memory(min_gibibytes_available=1.0)
            with pytest.raises(ServiceWarning) as exc_info:
                check.check_status()
            assert "RAM" in str(exc_info.value)

    def test_check_status__max_memory_usage_exceeded(self):
        """Raise ServiceWarning when memory usage exceeds threshold."""
        with mock.patch(
            "health_check.checks.psutil.virtual_memory"
        ) as mock_virtual_memory:
            mock_memory = mock.MagicMock()
            mock_memory.available = 1 * (1024**3)
            mock_memory.total = 8 * (1024**3)
            mock_memory.percent = 95.0
            mock_virtual_memory.return_value = mock_memory

            check = Memory(max_memory_usage_percent=90.0)
            with pytest.raises(ServiceWarning) as exc_info:
                check.check_status()
            assert "95" in str(exc_info.value)

    def test_check_status__memory_checks_disabled(self):
        """No warning when memory checks are disabled."""
        with mock.patch(
            "health_check.checks.psutil.virtual_memory"
        ) as mock_virtual_memory:
            mock_memory = mock.MagicMock()
            mock_memory.available = 0.1 * (1024**3)
            mock_memory.total = 8 * (1024**3)
            mock_memory.percent = 99.0
            mock_virtual_memory.return_value = mock_memory

            check = Memory(min_gibibytes_available=None, max_memory_usage_percent=None)
            check.check_status()
            assert check.errors == []

    def test_check_status__memory_value_error(self):
        """Raise ServiceReturnedUnexpectedResult when ValueError is raised during memory check."""
        with mock.patch(
            "health_check.checks.psutil.virtual_memory"
        ) as mock_virtual_memory:
            mock_virtual_memory.side_effect = ValueError("Invalid memory call")

            check = Memory()
            with pytest.raises(ServiceReturnedUnexpectedResult):
                check.check_status()


class TestStorageExceptionHandling:
    """Test Storage exception handling for uncovered code paths."""

    def test_check_status__success(self):
        """Storage check completes successfully without exceptions."""
        with (
            mock.patch("health_check.checks.storages") as mock_storages,
            mock.patch(
                "health_check.checks.Storage.get_file_content"
            ) as get_file_content,
        ):
            mock_storage = mock.MagicMock()
            mock_storages.__getitem__.return_value = mock_storage
            mock_storage.save.return_value = "test-file.txt"
            mock_storage.exists.side_effect = [True, False]
            mock_file = mock.MagicMock()
            mock_file.read.return_value = b"# generated by health_check.Storage at"
            mock_storage.open.return_value.__enter__.return_value = mock_file

            get_file_content.return_value = b"# generated by health_check.Storage at"

            check = Storage()
            check.check_status()
            assert check.errors == []

    def test_check_status__not_deleted(self):
        """Storage check completes successfully without exceptions."""
        with (
            mock.patch("health_check.checks.storages") as mock_storages,
            mock.patch(
                "health_check.checks.Storage.get_file_content"
            ) as get_file_content,
        ):
            mock_storage = mock.MagicMock()
            mock_storages.__getitem__.return_value = mock_storage
            mock_storage.save.return_value = "test-file.txt"
            mock_storage.exists.return_value = True
            mock_file = mock.MagicMock()
            mock_file.read.return_value = b"# generated by health_check.Storage at"
            mock_storage.open.return_value.__enter__.return_value = mock_file

            get_file_content.return_value = b"# generated by health_check.Storage at"

            check = Storage()
            with pytest.raises(ServiceUnavailable) as exc_info:
                check.check_status()
            assert "File was not deleted" in str(exc_info.value)

    def test_check_status__file_not_saved(self):
        """Raise ServiceUnavailable when file does not exist after save."""
        with mock.patch("health_check.checks.storages") as mock_storages:
            mock_storage = mock.MagicMock()
            mock_storages.__getitem__.return_value = mock_storage
            mock_storage.save.return_value = "test-file.txt"
            mock_storage.exists.return_value = False

            check = Storage()
            with pytest.raises(ServiceUnavailable) as exc_info:
                check.check_status()
            assert "does not exist" in str(exc_info.value)

    def test_check_status__file_content_mismatch(self):
        """Raise ServiceUnavailable when file content does not match."""
        with mock.patch("health_check.checks.storages") as mock_storages:
            mock_storage = mock.MagicMock()
            mock_storages.__getitem__.return_value = mock_storage
            mock_storage.save.return_value = "test-file.txt"
            mock_storage.exists.return_value = True
            mock_file = mock.MagicMock()
            mock_file.read.return_value = b"wrong content"
            mock_storage.open.return_value.__enter__.return_value = mock_file

            check = Storage()
            with pytest.raises(ServiceUnavailable) as exc_info:
                check.check_status()
            assert "does not match" in str(exc_info.value)

    def test_check_status__storage_unknown_exception(self):
        """Raise ServiceUnavailable for unknown exceptions."""
        with mock.patch("health_check.checks.storages") as mock_storages:
            mock_storage = mock.MagicMock()
            mock_storages.__getitem__.return_value = mock_storage
            mock_storage.save.side_effect = RuntimeError("Unknown error")

            check = Storage()
            with pytest.raises(ServiceUnavailable) as exc_info:
                check.check_status()
            assert "Unknown exception" in str(exc_info.value)

    def test_check_status__service_unavailable_passthrough(self):
        """Re-raise ServiceUnavailable exceptions."""
        with mock.patch("health_check.checks.storages") as mock_storages:
            mock_storage = mock.MagicMock()
            mock_storages.__getitem__.return_value = mock_storage
            mock_storage.save.side_effect = ServiceUnavailable("Service down")

            check = Storage()
            with pytest.raises(ServiceUnavailable) as exc_info:
                check.check_status()
            assert "Service down" in str(exc_info.value)


class TestSelectOneExpression:
    """Test _SelectOne expression for database queries."""

    @pytest.mark.django_db
    def test_oracle_query__generates_correct_sql(self):
        """Generate Oracle-specific SQL query with DUAL table."""
        from unittest.mock import MagicMock

        from health_check.checks import _SelectOne

        expr = _SelectOne()
        mock_compiler = MagicMock()
        mock_connection = MagicMock()

        sql, params = expr.as_oracle(mock_compiler, mock_connection)
        assert sql == "SELECT 1 FROM DUAL"
        assert params == []

    @pytest.mark.django_db
    def test_standard_query__generates_correct_sql(self):
        """Generate standard SQL query."""
        from unittest.mock import MagicMock

        from health_check.checks import _SelectOne

        expr = _SelectOne()
        mock_compiler = MagicMock()
        mock_connection = MagicMock()

        sql, params = expr.as_sql(mock_compiler, mock_connection)
        assert sql == "SELECT 1"
        assert params == []
