from django.urls import include, path

from health_check.views import HealthCheckView

# For test compatibility - main endpoint uses plugin_dir for flexibility
urlpatterns = [
    path("ht/", HealthCheckView.as_view(), name="health_check_home"),
]

# Add Celery check if celery is available
try:
    import celery  # noqa: F401
except ImportError:
    pass
else:
    urlpatterns.append(
        path(
            "ht/celery/",
            HealthCheckView.as_view(checks=["health_check.contrib.celery.Ping"]),
            name="health_check_celery",
        )
    )

# Add Redis check if redis is available
try:
    import redis  # noqa: F401
except ImportError:
    pass
else:
    urlpatterns.append(
        path(
            "ht/redis/",
            HealthCheckView.as_view(checks=["health_check.contrib.redis.Redis"]),
            name="health_check_redis",
        )
    )

# Add RabbitMQ check if kombu is available
try:
    import kombu  # noqa: F401
except ImportError:
    pass
else:
    urlpatterns.append(
        path(
            "ht/rabbitmq/",
            HealthCheckView.as_view(checks=["health_check.contrib.rabbitmq.RabbitMQ"]),
            name="health_check_rabbitmq",
        )
    )

# For backwards compatibility with tests, wrap in a namespace
health_check_patterns = (urlpatterns, "health_check")

urlpatterns = [
    path("", include(health_check_patterns)),
]
