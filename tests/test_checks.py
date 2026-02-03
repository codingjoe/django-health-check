"""Integration tests for health check implementations."""

import datetime
import logging
import tempfile
from unittest import mock

import pytest
from django import db
from django.core.cache import CacheKeyWarning

from health_check.checks import DNS, Cache, Database, Disk, Mail, Memory, Storage
from health_check.exceptions import (
    ServiceReturnedUnexpectedResult,
    ServiceUnavailable,
    ServiceWarning,
)


class TestCache:
    """Test the Cache health check."""

    @pytest.mark.asyncio
    async def test_run_check__cache_working(self):
        """Cache backend successfully sets and retrieves values."""
        check = Cache()
        result = await check.result
        assert result.error is None


class TestDatabase:
    """Test the Database health check."""

    @pytest.mark.django_db
    @pytest.mark.asyncio
    async def test_run_check__database_available(self):
        """Database connection returns successful query result."""
        check = Database()
        result = await check.result
        assert result.error is None


class TestDNS:
    """Test the DNS health check."""

    @pytest.mark.asyncio
    async def test_run_check__dns_working(self):
        """DNS resolution completes successfully for localhost."""
        check = DNS(hostname="github.com")
        result = await check.result
        assert result.error is None


class TestDisk:
    """Test the Disk health check."""

    @pytest.mark.asyncio
    async def test_run_check__disk_accessible(self):
        """Disk space check completes successfully."""
        check = Disk()
        result = await check.result
        assert result.error is None

    @pytest.mark.asyncio
    async def test_run_check__custom_path(self):
        """Disk check succeeds with custom path."""
        with tempfile.TemporaryDirectory() as tmpdir:
            check = Disk(path=tmpdir)
            result = await check.result
            assert result.error is None


class TestMemory:
    """Test the Memory health check."""

    @pytest.mark.asyncio
    async def test_run_check__memory_available(self):
        """Memory check completes successfully."""
        check = Memory()
        result = await check.result
        assert result.error is None


class TestMail:
    """Test the Mail health check."""

    @pytest.mark.asyncio
    async def test_run_check__locmem_backend(self):
        """Mail check completes with locmem backend."""
        check = Mail(backend="django.core.mail.backends.locmem.EmailBackend")
        result = await check.result
        assert result.error is None


class TestStorage:
    """Test the Storage health check."""

    @pytest.mark.asyncio
    async def test_run_check__default_storage(self):
        """Storage check completes without exceptions."""
        check = Storage()
        result = await check.result
        assert result.error is None


class TestServiceUnavailable:
    """Test ServiceUnavailable exception formatting."""

    def test_str__exception_message(self):
        """Format exception with message type prefix."""
        exc = ServiceUnavailable("Test error")
        assert str(exc) == "Unavailable: Test error"


class TestCacheExceptionHandling:
    """Test Cache exception handling for uncovered code paths."""

    @pytest.mark.asyncio
    async def test_check_status__cache_key_warning(self):
        """Raise ServiceReturnedUnexpectedResult when CacheKeyWarning is raised during set."""
        with mock.patch("health_check.checks.caches") as mock_caches:
            mock_cache = mock.MagicMock()
            mock_caches.__getitem__.return_value = mock_cache
            mock_cache.aset = mock.AsyncMock(side_effect=CacheKeyWarning("Invalid key"))

            check = Cache()
            result = await check.result
            assert result.error is not None
            assert isinstance(result.error, ServiceReturnedUnexpectedResult)
            assert "Cache key warning" in str(result.error)

    @pytest.mark.asyncio
    async def test_check_status__value_error(self):
        """Raise ServiceReturnedUnexpectedResult when ValueError is raised during cache operation."""
        with mock.patch("health_check.checks.caches") as mock_caches:
            mock_cache = mock.MagicMock()
            mock_caches.__getitem__.return_value = mock_cache
            mock_cache.aset = mock.AsyncMock(side_effect=ValueError("Invalid value"))

            check = Cache()
            result = await check.result
            assert result.error is not None
            assert isinstance(result.error, ServiceReturnedUnexpectedResult)
            assert "ValueError" in str(result.error)

    @pytest.mark.asyncio
    async def test_check_status__connection_error(self):
        """Raise ServiceReturnedUnexpectedResult when ConnectionError is raised during cache operation."""
        with mock.patch("health_check.checks.caches") as mock_caches:
            mock_cache = mock.MagicMock()
            mock_caches.__getitem__.return_value = mock_cache
            mock_cache.aset = mock.AsyncMock(
                side_effect=ConnectionError("Connection failed")
            )

            check = Cache()
            result = await check.result
            assert result.error is not None
            assert isinstance(result.error, ServiceReturnedUnexpectedResult)
            assert "Connection Error" in str(result.error)

    @pytest.mark.asyncio
    async def test_check_status__cache_value_mismatch(self):
        """Raise ServiceUnavailable when cached value does not match set value."""
        with mock.patch("health_check.checks.caches") as mock_caches:
            mock_cache = mock.MagicMock()
            mock_caches.__getitem__.return_value = mock_cache
            mock_cache.aset = mock.AsyncMock(return_value=None)
            mock_cache.aget = mock.AsyncMock(return_value="wrong-value")

            check = Cache()
            result = await check.result
            assert result.error is not None
            assert isinstance(result.error, ServiceUnavailable)
            assert "does not match" in str(result.error)


class TestDatabaseExceptionHandling:
    """Test Database exception handling for uncovered code paths."""

    @pytest.mark.django_db
    @pytest.mark.asyncio
    async def test_check_status__query_returns_unexpected_result(self):
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
            result = await check.result
            assert result.error is not None
            assert isinstance(result.error, ServiceUnavailable)
            assert "did not return the expected result" in str(result.error)

    @pytest.mark.django_db
    @pytest.mark.asyncio
    async def test_check_status__database_exception(self):
        """Raise ServiceUnavailable on database exception."""
        with mock.patch("health_check.checks.connections") as mock_connections:
            mock_connection = mock.MagicMock()
            mock_connections.__getitem__.return_value = mock_connection
            # Raise a database error (not a generic RuntimeError)
            mock_connection.ops.compiler.side_effect = db.Error("Database error")

            check = Database()
            result = await check.result
            assert result.error is not None
            assert isinstance(result.error, ServiceUnavailable)


class TestDNSExceptionHandling:
    """Test DNS exception handling for uncovered code paths."""

    @pytest.mark.asyncio
    async def test_check_status__nonexistent_hostname(self):
        """Raise ServiceUnavailable when hostname does not exist."""
        check = DNS(hostname="this-domain-does-not-exist-12345.invalid")
        result = await check.result
        assert result.error is not None
        assert "does not exist" in str(result.error)

    @pytest.mark.asyncio
    async def test_check_status__no_answer(self):
        """Raise ServiceUnavailable when DNS returns no answer for A record."""
        # Test with a hostname that has no A record (MX-only domain for example)
        # Using a TXT-only record subdomain or similar
        check = DNS(hostname="_dmarc.github.com")
        result = await check.result
        assert result.error is not None
        # Will get either no answer or NXDOMAIN
        error_msg = str(result.error).lower()
        assert "no answer" in error_msg or "does not exist" in error_msg

    @pytest.mark.asyncio
    async def test_check_status__timeout(self):
        """Raise ServiceUnavailable when DNS query times out."""
        # Use a very short timeout to trigger timeout error
        check = DNS(
            hostname="example.com",
            timeout=datetime.timedelta(microseconds=1),
        )
        result = await check.result
        assert result.error is not None
        assert "timeout" in str(result.error).lower()

    @pytest.mark.asyncio
    async def test_check_status__not_a_nameserver(self):
        """Raise ServiceUnavailable when nameserver is unreachable."""
        # Use an invalid/unreachable nameserver
        check = DNS(hostname="example.com", nameservers=["192.0.2.1"])
        result = await check.result
        assert result.error is not None
        # Could be timeout or no nameservers error
        error_msg = str(result.error).lower()
        assert "timeout" in error_msg or "nameserver" in error_msg

    @pytest.mark.asyncio
    async def test_check_status__no_nameservers(self):
        """Raise ServiceUnavailable when nameserver is unreachable."""
        # Use an invalid/unreachable nameserver
        check = DNS(hostname="example.com", nameservers=[])
        result = await check.result
        assert result.error is not None
        # Could be timeout or no nameservers error
        error_msg = str(result.error).lower()
        assert "timeout" in error_msg or "nameserver" in error_msg

    @pytest.mark.asyncio
    async def test_check_status__dns_exception(self):
        """Raise ServiceUnavailable on general DNS exception."""
        import dns.exception

        with mock.patch(
            "health_check.checks.dns.asyncresolver.Resolver"
        ) as mock_resolver_class:
            mock_resolver = mock.MagicMock()
            mock_resolver_class.return_value = mock_resolver
            mock_resolver.resolve = mock.AsyncMock(
                side_effect=dns.exception.DNSException("DNS error")
            )

            check = DNS(hostname="example.com")
            result = await check.result
            assert result.error is not None
            assert isinstance(result.error, ServiceUnavailable)
            assert "DNS resolution failed" in str(result.error)

    @pytest.mark.asyncio
    async def test_check_status__unknown_exception(self):
        """Raise ServiceUnavailable on unknown exception."""
        with mock.patch(
            "health_check.checks.dns.asyncresolver.Resolver"
        ) as mock_resolver_class:
            mock_resolver = mock.MagicMock()
            mock_resolver_class.return_value = mock_resolver
            mock_resolver.resolve = mock.AsyncMock(
                side_effect=RuntimeError("Unexpected error")
            )

            check = DNS(hostname="example.com")
            result = await check.result
            assert result.error is not None
            assert isinstance(result.error, ServiceUnavailable)
            assert "Unknown DNS error" in str(result.error)


class TestDiskExceptionHandling:
    """Test Disk exception handling for uncovered code paths."""

    @pytest.mark.asyncio
    async def test_check_status__disk_usage_exceeds_threshold(self):
        """Raise ServiceWarning when disk usage exceeds threshold."""
        with mock.patch("health_check.checks.psutil.disk_usage") as mock_disk_usage:
            mock_disk_usage_result = mock.MagicMock()
            mock_disk_usage_result.percent = 95.5
            mock_disk_usage.return_value = mock_disk_usage_result

            check = Disk(max_disk_usage_percent=90.0)
            result = await check.result
            assert result.error is not None
            assert isinstance(result.error, ServiceWarning)
            assert "95.5" in str(result.error)

    @pytest.mark.asyncio
    async def test_check_status__disk_check_disabled(self):
        """No warning when disk usage check is disabled."""
        with mock.patch("health_check.checks.psutil.disk_usage") as mock_disk_usage:
            mock_disk_usage_result = mock.MagicMock()
            mock_disk_usage_result.percent = 99.0
            mock_disk_usage.return_value = mock_disk_usage_result

            check = Disk(max_disk_usage_percent=None)
            result = await check.result
            assert result.error is None

    @pytest.mark.asyncio
    async def test_check_status__disk_value_error(self):
        """Raise ServiceReturnedUnexpectedResult when ValueError is raised during disk check."""
        with mock.patch("health_check.checks.psutil.disk_usage") as mock_disk_usage:
            mock_disk_usage.side_effect = ValueError("Invalid path")

            check = Disk()
            result = await check.result
            assert result.error is not None
            assert isinstance(result.error, ServiceReturnedUnexpectedResult)


class TestMailExceptionHandling:
    """Test Mail exception handling for uncovered code paths."""

    @pytest.mark.asyncio
    async def test_check_status__success(self, caplog):
        """Successfully open and close connection logs debug message."""
        with mock.patch("health_check.checks.get_connection") as mock_get_connection:
            mock_connection = mock.MagicMock()
            mock_get_connection.return_value = mock_connection
            mock_connection.open.return_value = None

            check = Mail(backend="django.core.mail.backends.locmem.EmailBackend")
            with caplog.at_level(logging.DEBUG, logger="health_check.checks"):
                result = await check.result
            assert result.error is None
            # Verify debug logging was called
            assert any(
                "Trying to open connection to mail backend" in record.message
                or "Connection established" in record.message
                for record in caplog.records
            )

    @pytest.mark.asyncio
    async def test_check_status__smtp_exception(self):
        """Raise ServiceUnavailable when SMTPException is raised."""
        import smtplib

        with mock.patch("health_check.checks.get_connection") as mock_get_connection:
            mock_connection = mock.MagicMock()
            mock_get_connection.return_value = mock_connection
            mock_connection.open.side_effect = smtplib.SMTPException("SMTP error")

            check = Mail(backend="django.core.mail.backends.locmem.EmailBackend")
            result = await check.result
            assert result.error is not None
            assert isinstance(result.error, ServiceUnavailable)
            assert "SMTP server" in str(result.error)
            mock_connection.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_check_status__connection_refused_error(self):
        """Raise ServiceUnavailable when ConnectionRefusedError is raised."""
        with mock.patch("health_check.checks.get_connection") as mock_get_connection:
            mock_connection = mock.MagicMock()
            mock_get_connection.return_value = mock_connection
            mock_connection.open.side_effect = ConnectionRefusedError(
                "Connection refused"
            )

            check = Mail(backend="django.core.mail.backends.locmem.EmailBackend")
            result = await check.result
            assert result.error is not None
            assert isinstance(result.error, ServiceUnavailable)
            assert "Connection refused" in str(result.error)
            mock_connection.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_check_status__mail_unknown_exception(self):
        """Raise ServiceUnavailable for unknown exceptions during mail check."""
        with mock.patch("health_check.checks.get_connection") as mock_get_connection:
            mock_connection = mock.MagicMock()
            mock_get_connection.return_value = mock_connection
            mock_connection.open.side_effect = RuntimeError("Unknown error")

            check = Mail(backend="django.core.mail.backends.locmem.EmailBackend")
            result = await check.result
            assert result.error is not None
            assert isinstance(result.error, ServiceUnavailable)
            assert "Unknown error" in str(result.error)
            mock_connection.close.assert_called_once()


class TestMemoryExceptionHandling:
    """Test Memory exception handling for uncovered code paths."""

    @pytest.mark.asyncio
    async def test_check_status__min_memory_available_exceeded(self):
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
            result = await check.result
            assert result.error is not None
            assert isinstance(result.error, ServiceWarning)
            assert "RAM" in str(result.error)

    @pytest.mark.asyncio
    async def test_check_status__max_memory_usage_exceeded(self):
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
            result = await check.result
            assert result.error is not None
            assert isinstance(result.error, ServiceWarning)
            assert "95" in str(result.error)

    @pytest.mark.asyncio
    async def test_check_status__memory_checks_disabled(self):
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
            result = await check.result
            assert result.error is None

    @pytest.mark.asyncio
    async def test_check_status__memory_value_error(self):
        """Raise ServiceReturnedUnexpectedResult when ValueError is raised during memory check."""
        with mock.patch(
            "health_check.checks.psutil.virtual_memory"
        ) as mock_virtual_memory:
            mock_virtual_memory.side_effect = ValueError("Invalid memory call")

            check = Memory()
            result = await check.result
            assert result.error is not None
            assert isinstance(result.error, ServiceReturnedUnexpectedResult)


class TestStorageExceptionHandling:
    """Test Storage exception handling for uncovered code paths."""

    @pytest.mark.asyncio
    async def test_check_status__success(self):
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
            result = await check.result
            assert result.error is None

    @pytest.mark.asyncio
    async def test_check_status__not_deleted(self):
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
            result = await check.result
            assert result.error is not None
            assert isinstance(result.error, ServiceUnavailable)
            assert "File was not deleted" in str(result.error)

    @pytest.mark.asyncio
    async def test_check_status__file_not_saved(self):
        """Raise ServiceUnavailable when file does not exist after save."""
        with mock.patch("health_check.checks.storages") as mock_storages:
            mock_storage = mock.MagicMock()
            mock_storages.__getitem__.return_value = mock_storage
            mock_storage.save.return_value = "test-file.txt"
            mock_storage.exists.return_value = False

            check = Storage()
            result = await check.result
            assert result.error is not None
            assert isinstance(result.error, ServiceUnavailable)
            assert "does not exist" in str(result.error)

    @pytest.mark.asyncio
    async def test_check_status__file_content_mismatch(self):
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
            result = await check.result
            assert result.error is not None
            assert isinstance(result.error, ServiceUnavailable)
            assert "does not match" in str(result.error)

    @pytest.mark.asyncio
    async def test_check_status__storage_unknown_exception(self):
        """Raise ServiceUnavailable for unknown exceptions."""
        with mock.patch("health_check.checks.storages") as mock_storages:
            mock_storage = mock.MagicMock()
            mock_storages.__getitem__.return_value = mock_storage
            mock_storage.save.side_effect = RuntimeError("Unknown error")

            check = Storage()
            result = await check.result
            assert result.error is not None
            assert isinstance(result.error, ServiceUnavailable)
            assert "Unknown exception" in str(result.error)

    @pytest.mark.asyncio
    async def test_check_status__service_unavailable_passthrough(self):
        """Re-raise ServiceUnavailable exceptions."""
        with mock.patch("health_check.checks.storages") as mock_storages:
            mock_storage = mock.MagicMock()
            mock_storages.__getitem__.return_value = mock_storage
            mock_storage.save.side_effect = ServiceUnavailable("Service down")

            check = Storage()
            result = await check.result
            assert result.error is not None
            assert isinstance(result.error, ServiceUnavailable)
            assert "Service down" in str(result.error)


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
