# Installation

Add the `django-health-check` package to your project:

```shell
uv add django-health-check
# or
pip install django-health-check
```

Add `health_check` and the plugins that you want to `INSTALLED_APPS` in `settings.py`:

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
> The `name` argument is required. The `health_check` command uses it to resolve
> this endpoint URL with `reverse()`. When you run the command, pass this name as
> the `endpoint` argument. For example, `django-admin health_check health_check`.

## Security

Protect the health check endpoint with a bearer token.

1. Enable HTTPS.

2. Generate a strong secret token:

    ```shell
    python -c "import secrets; print(secrets.token_urlsafe())"
    ```

    > [!WARNING]
    > Do NOT use Django's `SECRET_KEY` setting. Django also uses this setting
    > to sign other data.

3. Add the token to your URL configuration:

    ```python
    # urls.py
    import os

    from django.urls import path
    from health_check.views import HealthCheckView

    urlpatterns = [
        # …
        path(
            "health/",
            HealthCheckView.as_view(auth_token=os.getenv("HEALTH_CHECK_AUTH_TOKEN")),
            name="health_check",
        ),
    ]
    ```

4. Send the token in the request:

    ```shell
    $ curl -H "Authorization: Bearer $HEALTH_CHECK_AUTH_TOKEN" http://www.example.com/health/
    ```

    Requests without the token receive HTTP 403.

To keep the endpoint public, set `allow_anonymous=True`. This admits only
requests with no `Authorization` header. A request with a wrong or malformed
token still receives HTTP 403. A request with a valid token still skips the
cache.
