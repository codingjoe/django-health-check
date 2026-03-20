# Cookbook

This cookbook provides step-by-step examples for setting up multiple health check
endpoints tailored to different audiences and use cases.

A well-designed health check strategy exposes **three tiers** of endpoints:

| Tier | Purpose | Consumers |
|------|---------|-----------|
| [Node](#node-health-checks) | Hardware & OS resources | Kubernetes, Docker, reverse proxies |
| [Application](#application-health-checks) | App-level services | Uptime monitors, on-call alerts |
| [Pipeline](#pipeline-health-checks) | Upstream dependencies | CI/CD, developer Slack/Matrix channels |

---

## Node health checks

Node checks verify that the underlying server has sufficient resources to run the
application. These are suitable for **liveness and readiness probes** in container
orchestrators such as Kubernetes, Docker, and Podman, or for reverse-proxy health
checks in HAProxy or nginx.

### 1. Install the `psutil` extra

```shell
pip install "django-health-check[psutil]"
```

### 2. Add the node endpoint to your URL configuration

```python
# urls.py
from django.urls import path
from health_check.views import HealthCheckView

urlpatterns = [
    # …
    path(
        "health/node/",
        HealthCheckView.as_view(
            checks=[
                "health_check.contrib.psutil.CPU",
                "health_check.contrib.psutil.Memory",
                "health_check.contrib.psutil.Disk",
            ]
        ),
    ),
]
```

### 3. Configure Kubernetes probes

```yaml
# deployment.yaml
livenessProbe:
  httpGet:
    path: /health/node/
    port: 8000
  initialDelaySeconds: 10
  periodSeconds: 30
readinessProbe:
  httpGet:
    path: /health/node/
    port: 8000
  initialDelaySeconds: 5
  periodSeconds: 10
```

### 4. Configure a Docker health check

```dockerfile
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8000/health/node/ || exit 1
```

### 5. Configure Caddy as a reverse proxy

```caddy
# Caddyfile
example.com {
    reverse_proxy localhost:8000 {
        health_uri      /health/node/
        health_interval 30s
        health_timeout  5s
    }
}
```

### 6. Configure Traefik as a reverse proxy

```yaml
# docker-compose.yml
services:
  app:
    image: myapp
    labels:
      - "traefik.http.services.myapp.loadbalancer.healthcheck.path=/health/node/"
      - "traefik.http.services.myapp.loadbalancer.healthcheck.interval=30s"
      - "traefik.http.services.myapp.loadbalancer.healthcheck.timeout=5s"
```

---

## Application health checks

Application checks verify that all production services the application depends on are
reachable and operational. These are consumed by **uptime monitors** such as Pingdom,
Better Uptime, or StatusCake to alert on-call engineers when an outage occurs.

### 1. Install the required extras

```shell
pip install "django-health-check[redis,rabbitmq,celery]"
```

### 2. Add the application endpoint to your URL configuration

```python
# urls.py
from django.urls import path
from health_check.views import HealthCheckView
from redis.asyncio import Redis as RedisClient

urlpatterns = [
    # …
    path(
        "health/application/",
        HealthCheckView.as_view(
            checks=[
                # Django built-ins
                "health_check.Cache",
                "health_check.Database",
                "health_check.Mail",
                "health_check.Storage",
                # Message brokers & caches
                (
                    "health_check.contrib.redis.Redis",
                    {
                        "client_factory": lambda: RedisClient.from_url(
                            "redis://localhost:6379"
                        )
                    },
                ),
                (
                    "health_check.contrib.rabbitmq.RabbitMQ",
                    {"amqp_url": "amqp://guest:guest@localhost:5672//"},
                ),
                "health_check.contrib.celery.Ping",
            ]
        ),
    ),
]
```

### 3. Configure Pingdom

Point your Pingdom HTTP check at `https://www.example.com/health/application/`.
The endpoint returns HTTP 200 when all checks pass and HTTP 500 when any check fails,
which is exactly what Pingdom's uptime monitor expects.

> [!TIP]
> Protect this endpoint with a secret token so that it is not publicly accessible.
> See the [Security](install.md#security) section of the installation guide.

---

## Pipeline health checks

Pipeline checks combine all application checks with **upstream provider status** for
cloud platforms, PaaS providers, and third-party services. These are consumed by your
development team via RSS/Atom feeds integrated into Slack or Matrix, so that upstream
outages are surfaced in developer channels before they become support tickets.

### 1. Install the required extras

```shell
pip install "django-health-check[redis,rabbitmq,celery,rss,atlassian]"
```

### 2. Add the pipeline endpoint to your URL configuration

```python
# urls.py
from django.urls import path
from health_check.views import HealthCheckView
from redis.asyncio import Redis as RedisClient

urlpatterns = [
    # …
    path(
        "health/pipeline/",
        HealthCheckView.as_view(
            checks=[
                # Django built-ins
                "health_check.Cache",
                "health_check.Database",
                "health_check.Mail",
                "health_check.Storage",
                # Infrastructure
                (
                    "health_check.contrib.redis.Redis",
                    {
                        "client_factory": lambda: RedisClient.from_url(
                            "redis://localhost:6379"
                        )
                    },
                ),
                (
                    "health_check.contrib.rabbitmq.RabbitMQ",
                    {"amqp_url": "amqp://guest:guest@localhost:5672//"},
                ),
                "health_check.contrib.celery.Ping",
                # Cloud provider status (pick the ones relevant to your stack)
                (
                    "health_check.contrib.atlassian.GitHub",
                    {"component": "GitHub Actions"},
                ),
                "health_check.contrib.atlassian.Cloudflare",
                (
                    "health_check.contrib.rss.AWS",
                    {"region": "eu-west-1", "service": "s3"},
                ),
            ]
        ),
    ),
]
```

### 3. Subscribe to the RSS feed in Slack

1. Install the [Slack RSS App](https://slack.com/help/articles/218688467-Add-RSS-feeds-to-Slack).
1. In your `#ops` or `#incidents` channel, run:
   ```
   /feed subscribe https://www.example.com/health/pipeline/?format=rss
   ```

### 4. Subscribe in Matrix

```toml
# config.toml
[[bridge]]
    name = "Pipeline Health Monitor"
    feed_url = "https://example.com/health/pipeline/?format=rss"
    room_id = "!YourRoomId:matrix.org"
```

---

## Complete example

Below is a complete `urls.py` that wires all three tiers together.

```python
# urls.py
from django.urls import path
from health_check.views import HealthCheckView
from redis.asyncio import Redis as RedisClient

_application_checks = [
    "health_check.Cache",
    "health_check.Database",
    "health_check.Mail",
    "health_check.Storage",
    (
        "health_check.contrib.redis.Redis",
        {
            "client_factory": lambda: RedisClient.from_url(
                "redis://localhost:6379"
            )
        },
    ),
    (
        "health_check.contrib.rabbitmq.RabbitMQ",
        {"amqp_url": "amqp://guest:guest@localhost:5672//"},
    ),
    "health_check.contrib.celery.Ping",
]

urlpatterns = [
    # Tier 1 – node: for Kubernetes/Docker liveness & readiness probes
    path(
        "health/node/",
        HealthCheckView.as_view(
            checks=[
                "health_check.contrib.psutil.CPU",
                "health_check.contrib.psutil.Memory",
                "health_check.contrib.psutil.Disk",
            ]
        ),
    ),
    # Tier 2 – application: for uptime monitors & on-call alerts
    path(
        "health/application/",
        HealthCheckView.as_view(checks=_application_checks),
    ),
    # Tier 3 – pipeline: for developer RSS/Atom feeds (Slack, Matrix)
    path(
        "health/pipeline/",
        HealthCheckView.as_view(
            checks=[
                *_application_checks,
                (
                    "health_check.contrib.atlassian.GitHub",
                    {"component": "GitHub Actions"},
                ),
                "health_check.contrib.atlassian.Cloudflare",
                (
                    "health_check.contrib.rss.AWS",
                    {"region": "eu-west-1", "service": "s3"},
                ),
            ]
        ),
    ),
]
```
