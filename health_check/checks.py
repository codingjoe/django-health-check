"""Health check implementations for Django built-in services."""

import dataclasses
import datetime
import logging
import os
import pathlib
import smtplib
import socket
import uuid

import dns.asyncresolver
import psutil
from django import db
from django.conf import settings
from django.core.cache import CacheKeyWarning, caches
from django.core.files.base import ContentFile
from django.core.files.storage import Storage as DjangoStorage
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

    It can be setup multiple times for different cache aliases if needed.

    Args:
        alias: The cache alias to test against.
        cache_key: Prefix for the cache key to use for the test.

    """

    alias: str = "default"
    cache_key: str = dataclasses.field(default="djangohealthcheck_test", repr=False)

    async def run(self):
        cache = caches[self.alias]
        ts = datetime.datetime.now().timestamp()
        # Use an isolated key per probe run to avoid cross-process write races.
        cache_key = f"{self.cache_key}:{uuid.uuid4().hex}"
        cache_value = f"itworks-{ts}"
        try:
            await cache.aset(cache_key, cache_value, timeout=30)
            if not await cache.aget(cache_key) == cache_value:
                raise ServiceUnavailable(f"Cache key {cache_key} does not match")
        except CacheKeyWarning as e:
            raise ServiceReturnedUnexpectedResult("Cache key warning") from e
        except ValueError as e:
            raise ServiceReturnedUnexpectedResult("ValueError") from e
        except (ConnectionError, RedisError) as e:
            raise ServiceReturnedUnexpectedResult("Connection Error") from e


class _SelectOne(Expression):
    """An expression that represents a simple SELECT 1; query."""

    def as_sql(self, compiler, connection):
        return "SELECT 1", []

    def as_oracle(self, compiler, connection):
        return "SELECT 1 FROM DUAL", []


@dataclasses.dataclass
class Database(HealthCheck):
    """
    Check database operation by executing a simple SELECT 1 query.

    It can be setup multiple times for different database connections if needed.
    No actual data is read from or written to the database to minimize the performance impact
    and work with conservative database user permissions.

    Args:
        alias: The alias of the database connection to check.

    """

    alias: str = "default"

    def run(self):
        connection = connections[self.alias]
        result = None
        try:
            compiler = connection.ops.compiler("SQLCompiler")(
                _SelectOne(), connection, None
            )
            with connection.cursor() as cursor:
                cursor.execute(*compiler.compile(_SelectOne()))
                result = cursor.fetchone()
        except db.Error as e:
            raise ServiceUnavailable(str(e).rsplit(":")[0]) from e
        else:
            if result != (1,):
                raise ServiceUnavailable(
                    "Health Check query did not return the expected result."
                )
        finally:
            connection.close_if_unusable_or_obsolete()


@dataclasses.dataclass
class DNS(HealthCheck):
    """
    Check DNS resolution by resolving the server's hostname.

    Verifies that DNS resolution is working using the system's configured
    DNS servers, as well as nameserver resolution for the provided hostname.

    Args:
        hostname: The hostname to resolve.
        timeout: DNS query timeout.

    """

    hostname: str = dataclasses.field(default_factory=socket.gethostname)
    timeout: datetime.timedelta = dataclasses.field(
        default=datetime.timedelta(seconds=5), repr=False
    )
    nameservers: list[str] | None = dataclasses.field(default=None, repr=False)

    async def run(self):
        logger.debug("Attempting to resolve hostname: %s", self.hostname)

        resolver = dns.asyncresolver.Resolver()
        resolver.lifetime = self.timeout.total_seconds()
        if self.nameservers is not None:
            resolver.nameservers = self.nameservers

        try:
            # Perform DNS resolution (A record by default)
            answers = await resolver.resolve(self.hostname, "A")
        except dns.resolver.NXDOMAIN as e:
            raise ServiceUnavailable(
                f"DNS resolution failed: hostname {self.hostname} does not exist"
            ) from e
        except dns.resolver.NoAnswer as e:
            raise ServiceUnavailable(
                f"DNS resolution failed: no answer for {self.hostname}"
            ) from e
        except dns.resolver.Timeout as e:
            raise ServiceUnavailable(
                f"DNS resolution failed: timeout resolving {self.hostname}"
            ) from e
        except dns.resolver.NoNameservers as e:
            raise ServiceUnavailable(
                "DNS resolution failed: no nameservers available"
            ) from e
        except dns.exception.DNSException as e:
            raise ServiceUnavailable(f"DNS resolution failed: {e}") from e
        else:
            logger.debug(
                "Successfully resolved %s to %s",
                self.hostname,
                [str(rdata) for rdata in answers],
            )


@dataclasses.dataclass()
class Disk(HealthCheck):
    """
    Warn about disk usage for a given system path.

    It can be setup multiple times at different system paths,
    e.g. one at your application root and one at your media storage root.

    Args:
        path: Path to check disk usage for.
        max_disk_usage_percent: Maximum disk usage in percent or None to disable the check.

    """

    path: pathlib.Path | str = dataclasses.field(default_factory=os.getcwd)
    max_disk_usage_percent: float | None = dataclasses.field(default=90.0, repr=False)
    hostname: str = dataclasses.field(default_factory=socket.gethostname, init=False)

    def run(self):
        try:
            du = psutil.disk_usage(str(self.path))
            if (
                self.max_disk_usage_percent
                and du.percent >= self.max_disk_usage_percent
            ):
                raise ServiceWarning(f"{du.percent}\u202f% disk usage")
        except ValueError as e:
            raise ServiceReturnedUnexpectedResult("ValueError") from e


@dataclasses.dataclass
class Mail(HealthCheck):
    """
    Check that mail backend is able to open and close connection.

    Args:
        backend: The email backend to test against.
        timeout: Timeout for connection to mail server in seconds.

    """

    backend: str = settings.EMAIL_BACKEND
    timeout: datetime.timedelta = dataclasses.field(
        default=datetime.timedelta(seconds=15), repr=False
    )

    def run(self) -> None:
        connection: BaseEmailBackend = get_connection(self.backend, fail_silently=False)
        connection.timeout = self.timeout.total_seconds()
        logger.debug("Trying to open connection to mail backend.")
        try:
            connection.open()
        except smtplib.SMTPException as e:
            raise ServiceUnavailable(
                "Failed to open connection with SMTP server"
            ) from e
        except ConnectionRefusedError as e:
            raise ServiceUnavailable("Connection refused error") from e
        finally:
            connection.close()
        logger.debug(
            "Connection established. Mail backend %r is healthy.", self.backend
        )


@dataclasses.dataclass()
class Memory(HealthCheck):
    """
    Warn about system memory utilization.

    Args:
        min_gibibytes_available: Minimum available memory in gibibytes or None to disable the check.
        max_memory_usage_percent: Maximum memory usage in percent or None to disable the check.

    """

    min_gibibytes_available: float | None = dataclasses.field(default=None, repr=False)
    max_memory_usage_percent: float | None = dataclasses.field(default=90.0, repr=False)
    hostname: str = dataclasses.field(default_factory=socket.gethostname, init=False)

    def run(self):
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
            raise ServiceReturnedUnexpectedResult("ValueError") from e


@dataclasses.dataclass
class Storage(HealthCheck):
    """
    Check file storage backends by saving, reading, and deleting a test file.

    It can be setup multiple times for different storage backends if needed.

    Args:
        alias: The alias of the storage backend to check.

    """

    alias: str = "default"

    @property
    def storage(self) -> DjangoStorage:
        return storages[self.alias]

    def get_file_name(self):
        return f"health_check_storage_test/test-{uuid.uuid4()}.txt"

    def get_file_content(self):
        return f"# generated by health_check.Storage at {datetime.datetime.now().timestamp()}".encode()

    def check_save(self, file_name, file_content):
        # save the file
        file_name = self.storage.save(file_name, ContentFile(content=file_content))
        # read the file and compare
        if not self.storage.exists(file_name):
            raise ServiceUnavailable("File does not exist")
        with self.storage.open(file_name) as f:
            if not f.read() == file_content:
                raise ServiceUnavailable("File content does not match")
        return file_name

    def check_delete(self, file_name):
        # delete the file and make sure it is gone
        self.storage.delete(file_name)
        if self.storage.exists(file_name):
            raise ServiceUnavailable("File was not deleted")

    def run(self):
        # write the file to the storage backend
        file_name = self.get_file_name()
        file_content = self.get_file_content()
        file_name = self.check_save(file_name, file_content)
        self.check_delete(file_name)
