"""Health check implementations and deployment checks."""

import dataclasses
import datetime
import logging
import smtplib
import socket
import typing
import uuid

import django
import dns.asyncresolver
import httpx
from django import db
from django.conf import settings
from django.core.cache import CacheKeyWarning, caches
from django.core.cache.backends.base import InvalidCacheBackendError
from django.core.checks import Error, Tags, register
from django.core.files.base import ContentFile
from django.core.files.storage import InvalidStorageError, storages
from django.core.files.storage import Storage as DjangoStorage
from django.core.mail import get_connection
from django.core.mail.backends.base import BaseEmailBackend
from dns.nameserver import Nameserver

if django.VERSION >= (6, 1):
    from django.core.mail import DEFAULT_MAILER_ALIAS, mailers
else:  # Django < 6.1
    DEFAULT_MAILER_ALIAS = "default"

from django.db import connections
from django.db.models import Expression
from django.utils.connection import ConnectionDoesNotExist

from health_check.base import HealthCheck
from health_check.exceptions import (
    ServiceReturnedUnexpectedResult,
    ServiceUnavailable,
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


@register(Tags.security, deploy=True)
def check_auth_token(app_configs, **kwargs) -> typing.Iterator[Error]:
    """Yield an error when the auth token setting is empty or invalid."""
    try:
        auth_token = settings.HEALTH_CHECK_AUTH_TOKEN
    except AttributeError:
        return
    if not isinstance(auth_token, str) or not auth_token.strip():
        yield Error(
            "HEALTH_CHECK_AUTH_TOKEN must be a non-empty string.",
            hint="Set a non-empty string or remove the setting to disable authentication.",
            id="health_check.E001",
        )


@dataclasses.dataclass
class Cache(HealthCheck):
    """
    Check that the cache backend is able to set and get a value.

    It can be setup multiple times for different cache aliases if needed.

    Args:
        alias: The cache alias to test against.
        key_prefix: Prefix for the node specific cache key.
        timeout: Time until probe keys expire in the cache backend.

    """

    alias: str = "default"
    key_prefix: str = dataclasses.field(default="djangohealthcheck_test", repr=False)
    timeout: datetime.timedelta = dataclasses.field(
        default=datetime.timedelta(seconds=5), repr=False
    )

    async def run(self):
        try:
            cache = caches[self.alias]
        except InvalidCacheBackendError as e:
            msg = "Cache alias does not exist"
            raise ServiceUnavailable(msg) from e
        # Use an isolated key per probe run to avoid cross-process write races.
        cache_key = f"{self.key_prefix}:{uuid.uuid4().hex}"
        cache_value = f"itworks-{datetime.datetime.now(tz=datetime.UTC).timestamp()}"
        try:
            await cache.aset(
                cache_key,
                cache_value,
                timeout=self.timeout.total_seconds(),
            )
            if await cache.aget(cache_key) != cache_value:
                msg = f"Cache key {cache_key} does not match"
                raise ServiceUnavailable(msg)
        except CacheKeyWarning as e:
            msg = "Cache key warning"
            raise ServiceReturnedUnexpectedResult(msg) from e
        except ValueError as e:
            raise ServiceReturnedUnexpectedResult("ValueError") from e
        except (ConnectionError, RedisError) as e:
            msg = "Connection Error"
            raise ServiceReturnedUnexpectedResult(msg) from e


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
        try:
            connection = connections[self.alias]
        except ConnectionDoesNotExist as e:
            msg = "Database alias does not exist"
            raise ServiceUnavailable(msg) from e
        try:
            compiler = connection.ops.compiler("SQLCompiler")(
                _SelectOne(), connection, None
            )
            with connection.temporary_connection() as cursor:
                cursor.execute(*compiler.compile(_SelectOne()))
                result = cursor.fetchone()
        except db.Error as e:
            raise ServiceUnavailable(str(e).rsplit(":")[0]) from e
        else:
            if result != (1,):
                msg = "Health Check query did not return the expected result."
                raise ServiceUnavailable(msg)


@dataclasses.dataclass
class DNS(HealthCheck):
    """
    Check DNS resolution by resolving the server's hostname.

    Verifies that DNS resolution is working using the system's configured
    DNS servers, as well as nameserver resolution for the provided hostname.

    Args:
        hostname: The hostname to resolve.
        timeout: DNS query timeout.
        nameservers: Optional list of nameservers to use for DNS resolution.
        record_type: DNS record type to query (default is A record).

    """

    hostname: str = dataclasses.field(default_factory=socket.gethostname)
    timeout: datetime.timedelta = dataclasses.field(
        default=datetime.timedelta(seconds=5), repr=False
    )
    nameservers: typing.Sequence[str | Nameserver] = dataclasses.field(
        default_factory=lambda: dns.resolver.get_default_resolver().nameservers
    )
    record_type: str | dns.rdatatype.RdataType = dataclasses.field(
        default=dns.rdatatype.A
    )

    async def run(self):
        logger.debug("Attempting to resolve hostname: %s", self.hostname)

        resolver = dns.asyncresolver.Resolver()
        resolver.lifetime = self.timeout.total_seconds()
        resolver.nameservers = [*self.nameservers]

        try:
            # Perform DNS resolution (A record by default)
            answers = await resolver.resolve(self.hostname, self.record_type)
        except dns.resolver.NXDOMAIN as e:
            msg = f"DNS resolution failed: hostname {self.hostname} does not exist"
            raise ServiceUnavailable(msg) from e
        except dns.resolver.NoAnswer as e:
            msg = f"DNS resolution failed: no answer for {self.hostname}"
            raise ServiceUnavailable(msg) from e
        except dns.resolver.Timeout as e:
            msg = f"DNS resolution failed: timeout resolving {self.hostname}"
            raise ServiceUnavailable(msg) from e
        except dns.resolver.NoNameservers as e:
            msg = "DNS resolution failed: no nameservers available"
            raise ServiceUnavailable(msg) from e
        except dns.exception.DNSException as e:
            msg = f"DNS resolution failed: {e}"
            raise ServiceUnavailable(msg) from e
        else:
            logger.debug(
                "Successfully resolved %s to %s",
                self.hostname,
                [str(rdata) for rdata in answers],
            )


@dataclasses.dataclass
class Mail(HealthCheck):
    """
    Check that an email backend is able to open and close the connection.

    Args:
        backend: The email backend to test against. Legacy, used only on Django < 6.1.
        alias: The mailer alias to test.
        timeout: Timeout for connection to an email server in seconds.

    """

    backend: str | None = dataclasses.field(default=None, repr=False)
    alias: str = DEFAULT_MAILER_ALIAS
    timeout: datetime.timedelta = dataclasses.field(
        default=datetime.timedelta(seconds=15), repr=False
    )

    def _get_connection(self) -> BaseEmailBackend:
        if django.VERSION >= (6, 1):
            return mailers[self.alias]
        return get_connection(self.backend, fail_silently=False)

    def run(self) -> None:
        connection: BaseEmailBackend = self._get_connection()
        connection.timeout = self.timeout.total_seconds()
        logger.debug("Trying to open connection to mail backend.")
        try:
            connection.open()
        except smtplib.SMTPException as e:
            msg = "Failed to open connection with SMTP server"
            raise ServiceUnavailable(msg) from e
        except ConnectionRefusedError as e:
            msg = "Connection refused error"
            raise ServiceUnavailable(msg) from e
        finally:
            connection.close()
        logger.debug("Connection established. Mail backend %r is healthy.", connection)


@dataclasses.dataclass
class RemoteCheck(HealthCheck):
    """
    Check a remote django-health-check endpoint.

    Report every non-OK result as a single error.

    Args:
        url: Absolute URL of the remote health check.
        label: Label that replaces the URL in the check representation.
        timeout: Request timeout.

    """

    url: str = dataclasses.field(repr=False)
    label: str | None = None
    timeout: datetime.timedelta = dataclasses.field(
        default=datetime.timedelta(seconds=10), repr=False
    )

    def __repr__(self) -> str:
        match self.label:
            case None:
                return f"{type(self).__name__}(url={self.url!r})"
            case label:
                return f"{type(self).__name__}(label={label!r})"

    async def run(self) -> None:
        async with httpx.AsyncClient(
            headers={
                "Accept": "application/json",
                "User-Agent": "django-health-check",
            },
            timeout=self.timeout.total_seconds(),
            follow_redirects=True,
        ) as client:
            try:
                response = await client.get(self.url)
            except httpx.TimeoutException as e:
                msg = "Request timed out"
                raise ServiceUnavailable(msg) from e
            except httpx.RequestError as e:
                msg = f"Failed to reach URL: {e}"
                raise ServiceUnavailable(msg) from e

        try:
            errors = "\n".join(
                f"{check}: {result}"
                for check, result in response.json().items()
                if result != "OK"
            )
        except ValueError as e:
            msg = f"Response is not valid JSON (HTTP {response.status_code})"
            raise ServiceReturnedUnexpectedResult(msg) from e
        except AttributeError as e:
            msg = "Response is not a JSON object"
            raise ServiceReturnedUnexpectedResult(msg) from e

        if errors:
            raise ServiceUnavailable(errors)


@dataclasses.dataclass
class Storage(HealthCheck):
    """
    Check file storage backends by saving, reading, and deleting a test file.

    It can be set up multiple times for different storage backends if needed.

    Args:
        alias: The alias of the storage backend to check.

    """

    alias: str = "default"

    @property
    def storage(self) -> DjangoStorage:
        try:
            return storages[self.alias]
        except InvalidStorageError as e:
            msg = "Storage alias does not exist"
            raise ServiceUnavailable(msg) from e

    def get_file_name(self):
        return f"health_check_storage_test/test-{uuid.uuid4()}.txt"

    def get_file_content(self):
        return f"# generated by health_check.Storage at {datetime.datetime.now(tz=datetime.UTC).timestamp()}".encode()

    def check_save(self, file_name, file_content):
        # save the file
        file_name = self.storage.save(file_name, ContentFile(content=file_content))
        # read the file and compare
        if not self.storage.exists(file_name):
            msg = "File does not exist"
            raise ServiceUnavailable(msg)
        with self.storage.open(file_name) as f:
            if f.read() != file_content:
                msg = "File content does not match"
                raise ServiceUnavailable(msg)
        return file_name

    def check_delete(self, file_name):
        # delete the file and make sure it is gone
        self.storage.delete(file_name)
        if self.storage.exists(file_name):
            msg = "File was not deleted"
            raise ServiceUnavailable(msg)

    def run(self):
        # write the file to the storage backend
        file_name = self.get_file_name()
        file_content = self.get_file_content()
        try:
            file_name = self.check_save(file_name, file_content)
            self.check_delete(file_name)
        finally:
            self.storage.delete(file_name)
