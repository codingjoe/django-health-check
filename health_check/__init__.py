"""Monitor the health of your Django app and its connected services."""

from . import _version  # noqa
from .backends import HealthCheck
from .cache_check import Cache
from .db_check import Database
from .mail_check import Mail
from .psutil_check import Disk, Memory
from .storage_check import Storage

__version__ = _version.__version__
VERSION = _version.__version_tuple__

__all__ = [
    "__version__",
    "VERSION",
    "HealthCheck",
    "Cache",
    "Database",
    "Disk",
    "Mail",
    "Memory",
    "Storage",
]
