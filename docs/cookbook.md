# Cookbook

This cookbook provides step-by-step examples for setting up multiple health check
endpoints tailored to different audiences and use cases.

A well-designed health check strategy exposes **three tiers** of endpoints:

| Tier                                      | Purpose                 | Consumers                              |
| ----------------------------------------- | ----------------------- | -------------------------------------- |
| [Node](#node-health-checks)               | Hardware & OS resources | Kubernetes, Docker, reverse proxies    |
| [Application](#application-health-checks) | App-level services      | Uptime monitors, on-call alerts        |
| [Pipeline](#pipeline-health-checks)       | Upstream dependencies   | CI/CD, developer Slack/Matrix channels |

______________________________________________________________________

## Node health checks

Node checks verify that the underlying server has sufficient resources to run the
application. These are suitable for **liveness and readiness probes** in container
orchestrators such as Kubernetes, Docker, and Podman, or for reverse-proxy health
checks in HAProxy, nginx, Caddy, and Traefik.

The `psutil` extra provides OS resource checks such as CPU, memory, and disk usage.

```shell
pip install "django-health-check[psutil]"
```

Add the node endpoint to your URL configuration

```python
# urls.py
import os

from django.urls import include, path
from health_check.views import HealthCheckView

node_checks = [
    "health_check.contrib.psutil.CPU",
    "health_check.contrib.psutil.Memory",
    "health_check.contrib.psutil.Disk",
]

urlpatterns = [
    # …
    path(
        f"health/{os.getenv('HEALTH_CHECK_SECRET', 'dev')}",
        include(
            [
                path(
                    "node/",
                    HealthCheckView.as_view(checks=node_checks),
                    name="health_check-node",
                ),
            ]
        ),
    )
]
```

> [!TIP]
> Protect this endpoint with a secret token so that it is not publicly accessible.
> See the [Security](install.md#security) section of the installation guide.

### Kubernetes probes

Kubernetes uses liveness and readiness probes to determine whether a pod should be
restarted. We use an HTTP probe to ensure the operation of our entire HTTP stack.

> [!NOTE]
> When using `httpGet` probes, ensure your WSGI/ASGI server binds to `0.0.0.0`
> (not just `127.0.0.1`) so the kubelet can reach it.

For our health check endpoint, the setup would look like this:

```yaml
# deployment.yaml
livenessProbe:
  httpGet:
    path: /health/${HEALTH_CHECK_SECRET:-dev}/node/
    port: 8000
  initialDelaySeconds: 10
  periodSeconds: 30
readinessProbe:
  httpGet:
    path: /health/${HEALTH_CHECK_SECRET:-dev}/node/
    port: 8000
  initialDelaySeconds: 5
  periodSeconds: 10
```

See the [Kubernetes documentation](https://kubernetes.io/docs/tasks/configure-pod-container/configure-liveness-readiness-startup-probes/#define-a-liveness-http-request)
for more details.

### Docker / Podman

Compose doesn't have native HTTP probes. Therefore, we use a
[`health_check` command](usage.md#django-command). This command doesn't require
CURL to be present in the container image, and can emulate proxy requests to satisfy
HTTPS requirements.

```yaml
# compose.yml
services:
  web:
    # … your service definition …
    healthcheck:
      test: ["CMD", "python", "manage.py", "health_check", "health_check-node", "web:8000"]
      interval: 30s
      timeout: 10s
```

### Caddy or Traefik

Caddy's and Traefik's reverse-proxies provide sophisticated load balancing.
If configured, it can ensure that traffic is only routed to healthy instances.

In Caddy, the configuration would look like this:

```caddy
# Caddyfile
example.com {
    reverse_proxy localhost:8000 {
        health_uri      /health/${HEALTH_CHECK_SECRET:-dev}/node/
        health_interval 30s
        health_timeout  5s
    }
}
```

... and in Traefik, the configuration would look like this:

```yaml
# compose.yml
services:
  app:
    image: myapp
    labels:
      - "traefik.http.services.myapp.loadbalancer.healthcheck.path=/health/${HEALTH_CHECK_SECRET:-dev}/node/"
      - "traefik.http.services.myapp.loadbalancer.healthcheck.interval=30s"
      - "traefik.http.services.myapp.loadbalancer.healthcheck.timeout=5s"
```

## Application health checks

Application checks verify that all production services the application depends on are
reachable and operational. These are consumed by **uptime monitors** such as Pingdom,
Better Uptime, or StatusCake to alert on-call engineers when an outage occurs.

You want to monitor your entire application stack, including databases, caches,
message brokers, email providers, and storage backends. This might require some extra
dependencies:

```shell
pip install "django-health-check[redis,rabbitmq,celery]"
```

```python
# urls.py
import os

from django.urls import include, path
from health_check.views import HealthCheckView
from redis.asyncio import Redis as RedisClient

application_checks = [
    # Django built-ins
    "health_check.Cache",
    "health_check.Database",
    "health_check.Mail",
    "health_check.Storage",
    # Message brokers & caches
    (
        "health_check.contrib.redis.Redis",
        {"client_factory": lambda: RedisClient.from_url("redis://localhost:6379")},
    ),
    (
        "health_check.contrib.rabbitmq.RabbitMQ",
        {"amqp_url": "amqp://guest:guest@localhost:5672//"},
    ),
    "health_check.contrib.celery.Ping",
]

urlpatterns = [
    # …
    path(
        f"health/{os.getenv('HEALTH_CHECK_SECRET', 'dev')}",
        include(
            [
                # other endpoints …
                path(
                    "application/",
                    HealthCheckView.as_view(checks=application_checks),
                    name="health_check-application",
                ),
            ]
        ),
    )
]
```

Point your uptime monitor at `https://example.com/health/<HEALTH_CHECK_SECRET>/application/`.
The endpoint returns HTTP 200 when all checks pass and HTTP 500 when any check fails,
which is exactly what uptime monitors expect.

## Pipeline health checks

Pipeline checks combine all application checks with **upstream provider status** for
cloud platforms, PaaS providers, and third-party services. These are consumed by your
development team via RSS/Atom feeds integrated into Slack or Matrix, so that upstream
outages are surfaced in developer channels before they become support tickets.

First, let's install more extra dependencies to ingest the feeds from cloud providers:

```shell
pip install "django-health-check[rss,atlassian]"
```

Add the pipeline endpoint to your URL configuration

```python
# urls.py
import os

from django.urls import include, path
from health_check.views import HealthCheckView

application_checks = [
    # configured previously …
]

pipeline_checks = [
    # You may want to include application health alerts here too
    *application_checks,
    # Cloud provider status (pick the ones relevant to your stack)
    # GitHub status; to filter by a specific component, use a
    # tuple like ("health_check.contrib.atlassian.GitHub", {"component": "<exact name from githubstatus.com>"})
    "health_check.contrib.atlassian.GitHub",
    "health_check.contrib.atlassian.Cloudflare",
    (
        "health_check.contrib.rss.AWS",
        {"region": "eu-west-1", "service": "s3"},
    ),
]

urlpatterns = [
    # …
    path(
        f"health/{os.getenv('HEALTH_CHECK_SECRET', 'dev')}",
        include(
            [
                # other endpoints …
                path(
                    "pipeline/",
                    HealthCheckView.as_view(checks=pipeline_checks),
                    name="health_check-pipeline",
                ),
            ]
        ),
    )
]
```

### Slack or Matrix

You can now alert engineers about upstream outages in Slack or Matrix.

Subscribe to the RSS feed in Slack:

1. Install the [Slack RSS App](https://slack.com/help/articles/218688467-Add-RSS-feeds-to-Slack).
1. In your `#ops` or `#incidents` channel, run:
   ```
   /feed subscribe https://www.example.com/health/pipeline/?format=rss
   ```

... or subscribe in Matrix:

```toml
# config.toml
[[bridge]]
    name = "Pipeline Health Monitor"
    feed_url = "https://example.com/health/pipeline/?format=rss"
    room_id = "!YourRoomId:matrix.org"
```

______________________________________________________________________

## Complete example

```python
# urls.py
import os

from django.urls import include, path
from health_check.views import HealthCheckView
from redis.asyncio import Redis as RedisClient

node_checks = [
    "health_check.contrib.psutil.CPU",
    "health_check.contrib.psutil.Memory",
    "health_check.contrib.psutil.Disk",
]

application_checks = [
    "health_check.Cache",
    "health_check.Database",
    "health_check.Mail",
    "health_check.Storage",
    (
        "health_check.contrib.redis.Redis",
        {"client_factory": lambda: RedisClient.from_url("redis://localhost:6379")},
    ),
    (
        "health_check.contrib.rabbitmq.RabbitMQ",
        {"amqp_url": "amqp://guest:guest@localhost:5672//"},
    ),
    "health_check.contrib.celery.Ping",
]

pipeline_checks = [
    *application_checks,
    (
        "health_check.contrib.atlassian.GitHub",
        {"component": "Actions"},
    ),
    "health_check.contrib.atlassian.Cloudflare",
    (
        "health_check.contrib.rss.AWS",
        {"region": "eu-west-1", "service": "s3"},
    ),
]

urlpatterns = [
    path(
        "health/{os.getenv('HEALTH_CHECK_SECRET', 'dev')}/",
        include(
            [
                # Tier 1 – node: liveness & readiness probes
                path(
                    "node/",
                    HealthCheckView.as_view(checks=node_checks),
                    name="health_check-node",
                ),
                # Tier 2 – application: uptime monitors & on-call alerts
                path(
                    "application/",
                    HealthCheckView.as_view(checks=application_checks),
                    name="health_check-application",
                ),
                # Tier 3 – pipeline: developer RSS/Atom feeds (Slack, Matrix)
                path(
                    "pipeline/",
                    HealthCheckView.as_view(checks=pipeline_checks),
                    name="health_check-pipeline",
                ),
            ]
        ),
    ),
]
```
