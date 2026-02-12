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
                "health_check.Database",
                "health_check.Mail",
                "health_check.Storage",
                # 3rd party checks
                "health_check.contrib.psutil.Disk",
                (
                    "health_check.contrib.psutil.Memory",
                    {  # tuple with options
                        "min_gibibytes_available": 0.1,  # 0.1 GiB (~100 MiB)
                        "max_memory_usage_percent": 80.0,
                    },
                ),
                "health_check.contrib.celery.Ping",
                (  # tuple with options
                    "health_check.contrib.rabbitmq.RabbitMQ",
                    {"amqp_url": "amqp://guest:guest@localhost:5672//"},
                ),
                (
                    "health_check.contrib.redis.Redis",
                    {"client": Redis.from_url("redis://localhost:6379")},
                ),
            ],
        ),
    ),
]
```

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
