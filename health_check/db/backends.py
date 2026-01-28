from django.db import DatabaseError, IntegrityError

from health_check.backends import HealthCheck
from health_check.deprecation import deprecated
from health_check.exceptions import ServiceReturnedUnexpectedResult, ServiceUnavailable

from .models import TestModel


@deprecated(
    "`DatabaseBackend` is deprecated: use `health_check.Database` (new view-based Database check) instead. Action: remove legacy DatabaseBackend subclasses and configure `HealthCheckView` with `health_check.Database` in your `checks` list. See migration guide: https://codingjoe.dev/django-health-check/migrate-to-v4/ (docs/migrate-to-v4.md)."
)
class DatabaseBackend(HealthCheck):
    def check_status(self):
        try:
            obj = TestModel.objects.create(title="test")
            obj.title = "newtest"
            obj.save()
            obj.delete()
        except IntegrityError:
            raise ServiceReturnedUnexpectedResult("Integrity Error")
        except DatabaseError:
            raise ServiceUnavailable("Database error")
