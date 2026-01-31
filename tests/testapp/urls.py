from django.conf import settings
from django.urls import path

from health_check.feeds import HealthCheckFeed, HealthCheckRSSFeed
from health_check.views import HealthCheckView

urlpatterns = [
    path("health/", HealthCheckView.as_view(), name="health_check"),
    path("health/feed/", HealthCheckFeed(), name="health_check_feed"),
    path("health/feed.atom", HealthCheckFeed(), name="health_check_feed_atom"),
    path("health/feed.rss", HealthCheckRSSFeed(), name="health_check_feed_rss"),
]

try:
    import celery  # noqa: F401
except ImportError:
    pass
else:
    urlpatterns.append(
        path(
            "health/celery/",
            HealthCheckView.as_view(
                checks=[
                    "health_check.contrib.celery.Ping",
                    "health_check.contrib.celery.Ping",
                ],
                use_threading=False,
            ),
            name="health_check_celery",
        )
    )

try:
    import redis  # noqa: F401
except ImportError:
    pass
else:
    urlpatterns.append(
        path(
            "health/redis/",
            HealthCheckView.as_view(
                checks=[
                    (
                        "health_check.contrib.redis.Redis",
                        {"redis_url": settings.REDIS_URL},
                    )
                ]
            ),
            name="health_check_redis",
        )
    )

try:
    import kombu  # noqa: F401
except ImportError:
    pass
else:
    urlpatterns.append(
        path(
            "health/rabbitmq/",
            HealthCheckView.as_view(
                checks=[
                    (
                        "health_check.contrib.rabbitmq.RabbitMQ",
                        {
                            "amqp_url": settings.BROKER_URL,
                        },
                    )
                ]
            ),
            name="health_check_rabbitmq",
        )
    )
