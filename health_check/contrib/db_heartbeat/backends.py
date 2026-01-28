import dataclasses

from django.db import connections
from django.db.models import Expression

from health_check.backends import HealthCheck
from health_check.exceptions import ServiceUnavailable


class SelectOne(Expression):
    """An expression that represents a simple SELECT 1; query."""

    def as_sql(self, compiler, connection):
        return "SELECT 1", []

    def as_oracle(self, compiler, connection):
        return "SELECT 1 FROM DUAL", []


@dataclasses.dataclass
class DatabaseHeartBeatCheck(HealthCheck):
    """
    Check database connectivity by executing a simple SELECT 1 query.

    Args:
        alias: The alias of the database connection to check.

    """

    alias: str = dataclasses.field(default="default")

    def check_status(self):
        connection = connections[self.alias]
        try:
            result = None
            compiler = connection.ops.compiler("SQLCompiler")(SelectOne(), connection, None)
            with connection.cursor() as cursor:
                cursor.execute(*compiler.compile(SelectOne()))
                result = cursor.fetchone()

            if result != (1,):
                raise ServiceUnavailable("Health Check query did not return the expected result.")
        except Exception as e:
            raise ServiceUnavailable(f"Database health check failed: {e}")
