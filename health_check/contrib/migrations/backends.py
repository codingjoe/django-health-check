import logging

from django.conf import settings
from django.db import DEFAULT_DB_ALIAS, DatabaseError, connections
from django.db.migrations.executor import MigrationExecutor

from health_check.backends import HealthCheck
from health_check.deprecation import deprecated
from health_check.exceptions import ServiceUnavailable

logger = logging.getLogger(__name__)


@deprecated(
    "`MigrationsHealthCheck` is deprecated and removed: Django's system check framework covers migrations. Action: remove this check and rely on Django's check framework or add an alternative check to `HealthCheckView.checks`. See migration guide: https://codingjoe.dev/django-health-check/migrate-to-v4/ (docs/migrate-to-v4.md)."
)
class MigrationsHealthCheck(HealthCheck):
    def get_migration_plan(self, executor):
        return executor.migration_plan(executor.loader.graph.leaf_nodes())

    def check_status(self):
        db_alias = getattr(settings, "HEALTHCHECK_MIGRATIONS_DB", DEFAULT_DB_ALIAS)
        try:
            executor = MigrationExecutor(connections[db_alias])
            plan = self.get_migration_plan(executor)
            if plan:
                self.add_error(ServiceUnavailable("There are migrations to apply"))
        except DatabaseError as e:
            self.add_error(ServiceUnavailable("Database is not ready"), e)
        except Exception as e:
            self.add_error(ServiceUnavailable("Unexpected error"), e)
