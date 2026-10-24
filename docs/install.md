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
from django.tasks import default_task_backend
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
                "health_check.contrib.crontask.Scheduler",
                *(
                    (
                        "health_check.contrib.threadmill.Threadmill",
                        {"queue_name": queue_name},
                    )
                    for queue_name in default_task_backend.queues
                ),
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
        name="health_check",
    ),
]
```

> [!NOTE]
> The `name` argument is required — the `health_check` command needs it to
> resolve this endpoint URL via `reverse()`. When you run the command, pass this name as
> the `endpoint` argument, for example `django-admin health_check health_check`.

## Security

Keep the health check endpoint private with a bearer token.

1. Enable HTTPS.
1. Generate a strong token with Django's helper:
   ```shell
   python -c "from django.utils.crypto import get_random_string; print(get_random_string(64))"
   ```
   `get_random_string` draws from `secrets`. 64 characters give about 380 bits of entropy.
   > [!WARNING]
   > Do NOT use Django's `SECRET_KEY` setting!
1. Store it in your settings, ideally from the environment:
   ```python
   # settings.py
   import os

   HEALTH_CHECK_TOKEN = os.environ["HEALTH_CHECK_TOKEN"]
   ```
1. Pass it to the view:
   ```python
   # urls.py
   from django.conf import settings
   from django.urls import path
   from health_check.views import HealthCheckView

   urlpatterns = [
       path(
           "health/",
           HealthCheckView.as_view(authentication_token=settings.HEALTH_CHECK_TOKEN),
           name="health_check",
       ),
   ]
   ```
1. Send the token as `Authorization: Bearer <token>`. Requests without it get HTTP 403.

Set `allow_anonymous=True` to keep the endpoint public. Requests with a valid
token still bypass the cache. See
[Caching and authentication](usage.md#caching-and-authentication) for that
combination.
