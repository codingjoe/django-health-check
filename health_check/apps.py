from django.apps import AppConfig


class HealthCheckConfig(AppConfig):
    """Configuration for the health check app."""

    name = "health_check"

    def ready(self) -> None:
        """Register the system checks."""
        from health_check import system_checks  # noqa: F401
