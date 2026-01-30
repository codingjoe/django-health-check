"""Health check implementations for Django built-in services."""

import dataclasses
import datetime
import logging
import os
import pathlib
import socket
import uuid

import psutil
from django.conf import settings
from django.core.cache import CacheKeyWarning, caches
from django.core.files.base import ContentFile
from django.core.files.storage import storages
from django.core.mail import get_connection
from django.core.mail.backends.base import BaseEmailBackend
from django.db import connections
from django.db.models import Expression

from health_check.base import HealthCheck
from health_check.exceptions import (
    ServiceReturnedUnexpectedResult,
    ServiceUnavailable,
    ServiceWarning,
)

try:
    # Exceptions thrown by Redis do not subclass builtin exceptions like ConnectionError.
    # Additionally, not only connection errors (ConnectionError -> RedisError) can be raised,
    # but also errors for time-outs (TimeoutError -> RedisError)
    # and if the backend is read-only (ReadOnlyError -> ResponseError -> RedisError).
    # Since we know what we are trying to do here, we are not picky and catch the global exception RedisError.
    from redis.exceptions import RedisError
except ModuleNotFoundError:
    # In case Redis is not installed and another cache backend is used.
    class RedisError(Exception):
        pass


logger = logging.getLogger(__name__)


@dataclasses.dataclass
class Cache(HealthCheck):
    """
    Check that the cache backend is able to set and get a value.

    Args:
        alias: The cache alias to test against.
        cache_key: The cache key to use for the test.

    """

    alias: str = "default"
    cache_key: str = dataclasses.field(default="djangohealthcheck_test", repr=False)

    def check_status(self):
        cache = caches[self.alias]
        ts = datetime.datetime.now().timestamp()
        try:
            cache.set(self.cache_key, f"itworks-{ts}")
            if not cache.get(self.cache_key) == f"itworks-{ts}":
                raise ServiceUnavailable(f"Cache key {self.cache_key} does not match")
        except CacheKeyWarning as e:
            self.add_error(ServiceReturnedUnexpectedResult("Cache key warning"), e)
        except ValueError as e:
            self.add_error(ServiceReturnedUnexpectedResult("ValueError"), e)
        except (ConnectionError, RedisError) as e:
            self.add_error(ServiceReturnedUnexpectedResult("Connection Error"), e)


class _SelectOne(Expression):
    """An expression that represents a simple SELECT 1; query."""

    def as_sql(self, compiler, connection):
        return "SELECT 1", []

    def as_oracle(self, compiler, connection):
        return "SELECT 1 FROM DUAL", []


@dataclasses.dataclass
class Database(HealthCheck):
    """
    Check database connectivity by executing a simple SELECT 1 query.

    Args:
        alias: The alias of the database connection to check.

    """

    alias: str = "default"

    def check_status(self):
        connection = connections[self.alias]
        try:
            result = None
            compiler = connection.ops.compiler("SQLCompiler")(
                _SelectOne(), connection, None
            )
            with connection.cursor() as cursor:
                cursor.execute(*compiler.compile(_SelectOne()))
                result = cursor.fetchone()

            if result != (1,):
                raise ServiceUnavailable(
                    "Health Check query did not return the expected result."
                )
        except Exception as e:
            raise ServiceUnavailable(f"Database health check failed: {e}")


@dataclasses.dataclass()
class Disk(HealthCheck):
    """
    Check system disk usage.

    Args:
        path: Path to check disk usage for.
        max_disk_usage_percent: Maximum disk usage in percent or None to disable the check.

    """

    path: pathlib.Path | str = dataclasses.field(default_factory=os.getcwd)
    max_disk_usage_percent: float | None = dataclasses.field(default=90.0, repr=False)
    hostname: str = dataclasses.field(default_factory=socket.gethostname, init=False)

    def check_status(self):
        try:
            du = psutil.disk_usage(str(self.path))
            if (
                self.max_disk_usage_percent
                and du.percent >= self.max_disk_usage_percent
            ):
                raise ServiceWarning(f"{du.percent}\u202f% disk usage")
        except ValueError as e:
            self.add_error(ServiceReturnedUnexpectedResult("ValueError"), e)


@dataclasses.dataclass
class Mail(HealthCheck):
    """
    Check that mail backend is able to open and close connection.

    Args:
        backend: The email backend to test against. Defaults to settings.EMAIL_BACKEND.
        timeout: Timeout for connection to mail server in seconds.

    """

    backend: str = settings.EMAIL_BACKEND
    timeout: int = dataclasses.field(default=15, repr=False)

    def check_status(self) -> None:
        connection: BaseEmailBackend = get_connection(self.backend, fail_silently=False)
        connection.timeout = self.timeout
        logger.debug("Trying to open connection to mail backend.")
        try:
            connection.open()
        except Exception as error:
            import smtplib

            if isinstance(error, smtplib.SMTPException):
                self.add_error(
                    error=ServiceUnavailable(
                        "Failed to open connection with SMTP server"
                    ),
                    cause=error,
                )
            elif isinstance(error, ConnectionRefusedError):
                self.add_error(
                    error=ServiceUnavailable("Connection refused error"),
                    cause=error,
                )
            else:
                self.add_error(
                    error=ServiceUnavailable(f"Unknown error {error.__class__}"),
                    cause=error,
                )
        finally:
            connection.close()
        logger.debug(
            "Connection established. Mail backend %r is healthy.", self.backend
        )


@dataclasses.dataclass()
class Memory(HealthCheck):
    """
    Check system memory usage.

    Args:
        min_gibibytes_available: Minimum available memory in gibibytes or None to disable the check.
        max_memory_usage_percent: Maximum memory usage in percent or None to disable the check.

    """

    min_gibibytes_available: float | None = dataclasses.field(default=None, repr=False)
    max_memory_usage_percent: float | None = dataclasses.field(default=90.0, repr=False)
    hostname: str = dataclasses.field(default_factory=socket.gethostname, init=False)

    def check_status(self):
        try:
            memory = psutil.virtual_memory()
            available_gibi = memory.available / (1024**3)
            total_gibi = memory.total / (1024**3)
            msg = f"RAM {available_gibi:.1f}/{total_gibi:.1f}GiB ({memory.percent}\u202f%)"
            if (
                self.min_gibibytes_available
                and available_gibi < self.min_gibibytes_available
            ):
                raise ServiceWarning(msg)
            if (
                self.max_memory_usage_percent
                and memory.percent >= self.max_memory_usage_percent
            ):
                raise ServiceWarning(msg)
        except ValueError as e:
            self.add_error(ServiceReturnedUnexpectedResult("ValueError"), e)


@dataclasses.dataclass
class Storage(HealthCheck):
    """
    Check file storage backends by saving, reading, and deleting a test file.

    Args:
        alias: The alias of the storage backend to check. Defaults to "default".

    """

    alias: str = "default"

    def get_storage(self):
        return storages[
            self.storage_alias if hasattr(self, "storage_alias") else self.alias
        ]

    def get_file_name(self):
        return f"health_check_storage_test/test-{uuid.uuid4()}.txt"

    def get_file_content(self):
        return f"# generated by health_check.Storage at {datetime.datetime.now().timestamp()}".encode()

    def check_save(self, file_name, file_content):
        storage = self.get_storage()
        # save the file
        file_name = storage.save(file_name, ContentFile(content=file_content))
        # read the file and compare
        if not storage.exists(file_name):
            raise ServiceUnavailable("File does not exist")
        with storage.open(file_name) as f:
            if not f.read() == file_content:
                raise ServiceUnavailable("File content does not match")
        return file_name

    def check_delete(self, file_name):
        storage = self.get_storage()
        # delete the file and make sure it is gone
        storage.delete(file_name)
        if storage.exists(file_name):
            raise ServiceUnavailable("File was not deleted")

    def check_status(self):
        try:
            # write the file to the storage backend
            file_name = self.get_file_name()
            file_content = self.get_file_content()
            file_name = self.check_save(file_name, file_content)
            self.check_delete(file_name)
        except ServiceUnavailable as e:
            raise e
        except Exception as e:
            raise ServiceUnavailable("Unknown exception") from e
