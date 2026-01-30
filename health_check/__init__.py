"""Monitor the health of your Django app and its connected services."""

from . import _version  # noqa
from .cache.backends import CacheBackend as Cache
from .contrib.mail.backends import MailHealthCheck as Mail
from .contrib.psutil.backends import DiskUsage as Disk, MemoryUsage as Memory
from .contrib.db_heartbeat.backends import DatabaseHeartBeatCheck as Database
from .storage.backends import StorageHealthCheck as Storage
from .backends import HealthCheck

__version__ = _version.__version__
VERSION = _version.__version_tuple__

Cache.__qualname__ = "Cache"
Database.__qualname__ = "Database"
Disk.__qualname__ = "Disk"
Mail.__qualname__ = "Mail"
Storage.__qualname__ = "Storage"
Memory.__qualname__ = "Memory"
__all__ = [
    "__version__",
    "VERSION",
    "Cache",
    "Database",
    "Disk",
    "Mail",
    "Storage",
    "Memory",
    "HealthCheck",
]
