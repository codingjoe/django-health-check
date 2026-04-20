from django.conf import settings
from django.urls import path

from health_check.base import HealthCheck
from health_check.exceptions import HealthCheckException
from health_check.views import HealthCheckView


class AlwaysFailingCheck(HealthCheck):
    """Health check that always fails for testing purposes."""

    async def run(self):
        raise HealthCheckException("Test failure")


urlpatterns = [
    path("health/", HealthCheckView.as_view(), name="health_check"),
    # Simple endpoint for testing that only checks things that will work
    path(
        "health/test/",
        HealthCheckView.as_view(
            checks=[
                "health_check.checks.Database",
                "health_check.checks.Cache",
            ]
        ),
        name="health_check_test",
    ),
    # Failing endpoint for testing error handling
    path(
        "health/fail/",
        HealthCheckView.as_view(checks=[AlwaysFailingCheck]),
        name="health_check_fail",
    ),
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
            ),
            name="health_check_celery",
        )
    )

try:
    from redis.asyncio import Redis as RedisClient
except ImportError:
    pass
else:

    def redis_client_factory():
        return RedisClient.from_url(settings.REDIS_URL)

    urlpatterns.append(
        path(
            "health/redis/",
            HealthCheckView.as_view(
                checks=[
                    (
                        "health_check.contrib.redis.Redis",
                        {"client_factory": redis_client_factory},
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
