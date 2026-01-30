import logging

from health_check.deprecation import deprecated
from health_check.storage.backends import StorageHealthCheck


@deprecated(
    "`S3BotoStorageHealthCheck` is deprecated: use `health_check.Storage` instead. Action: remove legacy storage checks and add `health_check.Storage` to your `HealthCheckView.checks`. See migration guide: https://codingjoe.dev/django-health-check/migrate-to-v4/ (docs/migrate-to-v4.md)."
)
class S3BotoStorageHealthCheck(StorageHealthCheck):
    """
    Tests the status of a `S3BotoStorage` file storage backend.

    S3BotoStorage is included in the `django-storages` package
    and recommended by for example Amazon and Heroku for Django
    static and media file storage on cloud platforms.

    ``django-storages`` can be found at https://git.io/v1lGx
    ``S3BotoStorage`` can be found at https://git.io/v1lGF
    """

    logger = logging.getLogger(__name__)
    storage = "storages.backends.s3boto.S3BotoStorage"

    def check_delete(self, file_name):
        storage = self.get_storage()
        storage.delete(file_name)
