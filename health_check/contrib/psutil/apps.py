import warnings

from django.apps import AppConfig
from django.conf import settings

from health_check.plugins import plugin_dir


class HealthCheckConfig(AppConfig):
    name = "health_check.contrib.psutil"

    def ready(self):
        from .backends import DiskUsage, MemoryUsage

        warnings.warn(
            "The `health_check.contrib.psutil` app is deprecated: checks are now configured via `HealthCheckView` and explicit `checks` lists. Action: remove this sub-app from `INSTALLED_APPS` and add `health_check.Disk` and `health_check.Memory` to your `HealthCheckView.checks`. See migration guide: https://codingjoe.dev/django-health-check/migrate-to-v4/ (docs/migrate-to-v4.md).",
            DeprecationWarning,
        )

        # Ensure checks haven't been explicitly disabled before registering
        if (
            hasattr(settings, "HEALTH_CHECK")
            and ("DISK_USAGE_MAX" in settings.HEALTH_CHECK)
            and (settings.HEALTH_CHECK["DISK_USAGE_MAX"] is None)
        ):
            pass
        else:
            plugin_dir.register(DiskUsage)
        if (
            hasattr(settings, "HEALTH_CHECK")
            and ("DISK_USAGE_MAX" in settings.HEALTH_CHECK)
            and (settings.HEALTH_CHECK["MEMORY_MIN"] is None)
        ):
            pass
        else:
            plugin_dir.register(MemoryUsage)
