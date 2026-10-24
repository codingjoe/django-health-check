# Cookbook

This cookbook shows how to set up multiple health check endpoints. Each
endpoint has a different audience and use case.

A good setup has **three tiers** of endpoints:

| Tier                                      | Purpose                 | Consumers                              |
| ----------------------------------------- | ----------------------- | -------------------------------------- |
| [Node](#node-health-checks)               | Hardware & OS resources | Kubernetes, Docker, reverse proxies    |
| [Application](#application-health-checks) | App-level services      | Uptime monitors, on-call alerts        |
| [Pipeline](#pipeline-health-checks)       | Upstream dependencies   | CI/CD, developer Slack/Matrix channels |

______________________________________________________________________

## Node health checks

Node checks make sure that the server has enough resources to run the application.
Use them for **liveness and readiness probes** in container orchestrators,
for example Kubernetes, Docker, and Podman. You can also use them for
reverse-proxy checks in HAProxy, nginx, Caddy, and Traefik.

The `psutil` extra provides OS resource checks for CPU, memory, and disk usage.

```shell
pip install "django-health-check[psutil]"
```

Add the node endpoint to your URL configuration.

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
        f"health/{os.getenv('HEALTH_CHECK_SECRET', 'dev')}/",
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
> A secret token protects this endpoint from public access.
> See the [Security](install.md#security) section of the installation guide.

### Kubernetes probes

Kubernetes uses liveness and readiness probes to decide when to restart a pod.
The probes use HTTP. Thus they also prove that the full HTTP stack operates
correctly.

> [!NOTE]
> If the WSGI/ASGI server binds to `0.0.0.0`, the kubelet can reach the
> `httpGet` probes. A bind to `127.0.0.1` is not sufficient.

The configuration for this health check endpoint is:

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
for more information.

### Docker / Podman

Compose has no native HTTP probes. Thus this setup uses the
[`health_check` command](usage.md#django-command). The command does not need
CURL in the image. It can emulate proxy requests to satisfy HTTPS
requirements.

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

### Load balancers

Most reverse proxies can load balance. After configuration, they send traffic
only to healthy instances.

The configuration for [Caddy][caddy-active-health-checks] is:

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

The configuration for [Traefik][traefik-health-checks] is:

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

The configuration for [Nginx][nginx-health-checks] is:

```nginx
# nginx.conf
upstream myapp {
    server localhost:8000;
    health_check interval=30s timeout=5s uri=/health/${HEALTH_CHECK_SECRET:-dev}/node/;
}
```

The configuration for [HAProxy][haproxy-health-checks] is:

```haproxy
# haproxy.cfg
backend myapp
    server app1 localhost:8000 check inter 30s fall 3 rise 2
    http-check expect status 200
    http-check send meth GET uri /health/${HEALTH_CHECK_SECRET:-dev}/node/
```

## Application health checks

Application checks make sure that each production service of your application
is reachable and operates correctly. **Uptime monitors**, for example Pingdom,
Better Uptime, or StatusCake, watch these endpoints. They notify on-call
engineers when a service fails.

The full stack includes databases, caches, message brokers, email, and storage.
To cover the full stack, install these extra dependencies:

```shell
pip install "django-health-check[redis,rabbitmq,celery,crontask]"
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
    "health_check.contrib.crontask.Scheduler",
]

urlpatterns = [
    # …
    path(
        f"health/{os.getenv('HEALTH_CHECK_SECRET', 'dev')}/",
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

Point the uptime monitor at `https://example.com/health/<HEALTH_CHECK_SECRET>/application/`.
The endpoint returns HTTP 200 when all checks pass. It returns HTTP 500 when a
check fails. Uptime monitors expect these codes.

## Pipeline health checks

Pipeline checks add **upstream provider status** to your application checks.
This status includes cloud platforms, PaaS providers, and third-party services.
The development team watches these checks with RSS/Atom feeds in Slack or
Matrix. Then upstream outages become known before they become support tickets.

Install the extras that read the feeds from cloud providers:

```shell
pip install "django-health-check[rss,atlassian]"
```

Add the pipeline endpoint to your URL configuration.

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
        f"health/{os.getenv('HEALTH_CHECK_SECRET', 'dev')}/",
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

You can now tell engineers about upstream outages in Slack or Matrix.

Subscribe to the RSS feed in Slack:

1. Install the [Slack RSS App](https://slack.com/help/articles/218688467-Add-RSS-feeds-to-Slack).
2. In your `#ops` or `#incidents` channel, run:
   ```
   /feed subscribe https://www.example.com/health/<HEALTH_CHECK_SECRET>/pipeline/?format=rss
   ```

Or subscribe in Matrix:

```toml
# config.toml
[[bridge]]
    name = "Pipeline Health Monitor"
    feed_url = "https://example.com/health/<HEALTH_CHECK_SECRET>/pipeline/?format=rss"
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
    "health_check.contrib.crontask.Scheduler",
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

[caddy-active-health-checks]: https://www.haproxy.com/documentation/haproxy-configuration-tutorials/reliability/health-checks/#http-health-checks
[haproxy-health-checks]: https://www.haproxy.com/documentation/hapee/2-5r1/traffic-management/load-balancing/health-checks/
[nginx-health-checks]: https://nginx.org/en/docs/http/ngx_http_upstream_hc_module.html#health_check
[traefik-health-checks]: https://doc.traefik.io/traefik/routing/services/#health-check
