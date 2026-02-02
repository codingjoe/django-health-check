# Installation

Add the `django-health-check` package to your project:

```shell
uv add django-health-check
# or
pip install django-health-check
```

Add `health_check` and any desired plugins to your `INSTALLED_APPS` in `settings.py`:

```python
# settings.py
INSTALLED_APPS = [
    # …
    "health_check",  # required
]
```

Add a health check view to your URL configuration. For example:

```python
# urls.py
from django.urls import include, path
from health_check.views import HealthCheckView
from redis import Redis

urlpatterns = [
    # …
    path(
        "health/",
        HealthCheckView.as_view(
            checks=[  # optional, default is all but 3rd party checks
                "health_check.Cache",
                "health_check.DNS",
                "health_check.Database",
                "health_check.Disk",
                "health_check.Mail",
                "health_check.Memory",
                "health_check.Storage",
                # 3rd party checks
                "health_check.contrib.celery.Ping",
                (
                    "health_check.contrib.kafka.Kafka",
                    {"bootstrap_servers": ["localhost:9092"]},
                ),
                (  # tuple with options
                    "health_check.contrib.rabbitmq.RabbitMQ",
                    {"amqp_url": "amqp://guest:guest@localhost:5672//"},
                ),
                (
                    "health_check.contrib.redis.Redis",
                    {"client": Redis.from_url("redis://localhost:6379")},
                ),
                # AWS service status check
                (
                    "health_check.contrib.rss.AWS",
                    {"region": "eu-west-1", "service": "s3"},
                ),
            ],
            use_threading=True,  # optional, default is True
            warnings_as_errors=True,  # optional, default is True
        ),
    ),
]
```

## Threading

Django Health Check runs each check in a separate thread by default to improve performance. If you prefer to run the checks sequentially, you can set the `use_threading` parameter to `False` when instantiating the `HealthCheckView`, as shown in the example above.

This can be useful in environments where threads are not closing IO connections properly, leading to resource leaks.
However, for Django's database connections, threading is generally safe and recommended for better performance.

## Warnings as Errors

Treats `ServiceWarning` as errors, meaning they will cause the views to respond with a 500 status code. Default is `True`.
If set to `False` warnings will be displayed in the template or in the JSON response but the status code will remain a 200.

## Security

You can protect the health check endpoint by adding a secure token to your URL.

1. Setup HTTPS. Seriously…
1. Generate a strong secret token:
   ```shell
   python -c "import secrets; print(secrets.token_urlsafe())"
   ```
   > [!WARNING]
   > Do NOT use Django's `SECRET_KEY` setting!
1. Add it to your URL configuration:
   ```python
   #  urls.py
   from django.urls import include, path
   from health_check.views import HealthCheckView

   urlpatterns = [
       # …
       path("health/super_secret_token/", HealthCheckView.as_view()),
   ]
   ```
