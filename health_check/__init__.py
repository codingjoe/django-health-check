"""Monitor the health of your Django app and its connected services."""

from . import _version  # noqa
from .base import HealthCheck
from .checks import Cache, DNS, Database, Disk, Mail, Memory, Storage

__version__ = _version.__version__
VERSION = _version.__version_tuple__

__all__ = [
    "__version__",
    "VERSION",
    "HealthCheck",
    "Cache",
    "DNS",
    "Database",
    "Disk",
    "Mail",
    "Memory",
    "Storage",
]
