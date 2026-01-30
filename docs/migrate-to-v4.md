# Migration to version 4.x

1. If you have `health_check.db` in your `INSTALLED_APPS`, remove revert the migration to drop the `TestModel` table:

   ```shell
   python manage.py migrate health_check.db zero
   ```

1. Remove these `health_check.*` sub‑apps from `INSTALLED_APPS` but keep `health_check`!

1. Remove all `HEALTH_CHECK_*` settings from your settings file.

1. Replace the URL include with the view and explicit `checks` list.
   Before:

   ```python
   # urls.py
   path("ht/", include("health_check.urls"))
   ```

   After (example):

   ```python
   # urls.py
   from health_check.views import HealthCheckView

   path(
       "ht/",
       HealthCheckView.as_view(
           checks=[
               "health_check.Cache",
               "health_check.Database",
               "health_check.Disk",
               "health_check.Mail",
               "health_check.Memory",
               "health_check.Storage",
               # 3rd party checks
               "health_check.contrib.celery.Ping",
               "health_check.contrib.rabbitmq.RabbitMQ",
               "health_check.contrib.redis.Redis",
           ]
       ),
   )
   ```

## Removals and Replacements

- `StorageHealthCheck`, `DefaultFileStorageHealthCheck`, `S3BotoStorageHealthCheck`, `S3Boto3StorageHealthCheck` have been replaced with [Storage][health_check.Storage].
- `CeleryHealthCheck` has been replaced with [Ping][health_check.contrib.celery.Ping].
- `MigrationsHealthCheck` has been removed; its functionality is covered by [Django's check framework](https://docs.djangoproject.com/en/stable/topics/checks/).
- `DatabaseHealthCheck` has been replaced with [Database][health_check.Database] which doesn't require a table and supports multiple database aliases.
