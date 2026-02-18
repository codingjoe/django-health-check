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
from redis.asyncio import Redis as RedisClient

urlpatterns = [
    # …
    path(
        "health/",
        HealthCheckView.as_view(
            checks=[  # optional, default is all but 3rd party checks
                "health_check.Cache",
                "health_check.DNS",
                "health_check.Database",
                "health_check.Mail",
                "health_check.Storage",
                # 3rd party checks
                "health_check.contrib.psutil.Disk",
                "health_check.contrib.psutil.Memory",
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
                    {
                        "client_factory": lambda: RedisClient.from_url(
                            "redis://localhost:6379"
                        )
                    },
                ),
                # AWS service status check
                (
                    "health_check.contrib.rss.AWS",
                    {"region": "eu-west-1", "service": "s3"},
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
