# Migration to version 4.x

> [!IMPORTANT]
> Version 3.21 started deprecating the old settings, checks, and APIs.
> To make the switch easier, versions >=3.21 still support both the OLD and NEW configuration styles.

1. If you have `health_check.db` in your `INSTALLED_APPS`, revert the migration to drop the `TestModel` table:

   ```shell
   python manage.py migrate db zero
   ```

1. Update the dependencies. Include the extras for the checks you want to use.

   ```shell
   uv add 'django-health-check[psutil,celery,kafka,rabbitmq,redis,rss,atlassian]>=4.0.0'
   ```

1. Remove these `health_check.*` sub‑apps from `INSTALLED_APPS`. Keep `health_check`!

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
               "health_check.Mail",
               "health_check.Storage",
               # 3rd party checks
               "health_check.contrib.psutil.Disk",
               "health_check.contrib.psutil.Memory",
               "health_check.contrib.celery.Ping",
               "health_check.contrib.rabbitmq.RabbitMQ",
               "health_check.contrib.redis.Redis",
           ]
       ),
       name="health_check",
   )
   ```

## Removals and Replacements

- The classes `StorageHealthCheck`, `DefaultFileStorageHealthCheck`, `S3BotoStorageHealthCheck`, and `S3Boto3StorageHealthCheck` are replaced with [Storage][health_check.Storage].
- `CeleryHealthCheck` is replaced with [Ping][health_check.contrib.celery.Ping].
- `MigrationsHealthCheck` is removed. [Django's check framework](https://docs.djangoproject.com/en/stable/topics/checks/) covers its function.
- `DatabaseHealthCheck` is replaced with [Database][health_check.Database]. It does not require a table. It supports multiple database aliases.
