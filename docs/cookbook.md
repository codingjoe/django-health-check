# Cookbook

This cookbook walks through setting up multiple health check endpoints,
each aimed at a different audience and use case.

A solid setup exposes **three tiers** of endpoints:

| Tier                                      | Purpose                 | Consumers                              |
| ----------------------------------------- | ----------------------- | -------------------------------------- |
| [Node](#node-health-checks)               | Hardware & OS resources | Kubernetes, Docker, reverse proxies    |
| [Application](#application-health-checks) | App-level services      | Uptime monitors, on-call alerts        |
| [Pipeline](#pipeline-health-checks)       | Upstream dependencies   | CI/CD, developer Slack/Matrix channels |

______________________________________________________________________

## Node health checks

Node checks confirm the server has enough resources to run the app.
Use them for **liveness and readiness probes** in container
orchestrators such as Kubernetes, Docker, and Podman, or for reverse-proxy
checks in HAProxy, nginx, Caddy, and Traefik.

The `psutil` extra provides OS resource checks such as CPU, memory, and disk usage.

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
> Protect this endpoint with a secret token. Do not make it publicly accessible.
> See the [Security](install.md#security) section of the installation guide.

### Kubernetes probes

Kubernetes uses liveness and readiness probes to decide when to restart a pod.
We hit the endpoint over HTTP, which also proves the whole HTTP stack works.

> [!NOTE]
> Bind your WSGI/ASGI server to `0.0.0.0`, not just `127.0.0.1`, so the kubelet
> can reach the `httpGet` probes.

For our health check endpoint, the configuration looks like this:

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

Compose has no native HTTP probes, so we use the
[`health_check` command](usage.md#django-command) instead. It doesn't need
CURL in the image, and it can emulate proxy requests to satisfy HTTPS
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

Most reverse-proxies can load balance.
Once configured, they only route traffic to healthy instances.

In [Caddy][caddy-active-health-checks], the configuration looks like this:

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

… in [Traefik][traefik-health-checks], the configuration looks like this:

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

… in [Nginx][nginx-health-checks], the configuration looks like this:

```nginx
# nginx.conf
upstream myapp {
    server localhost:8000;
    health_check interval=30s timeout=5s uri=/health/${HEALTH_CHECK_SECRET:-dev}/node/;
}
```

… and in [HAProxy][haproxy-health-checks], the configuration looks like this:

```haproxy
# haproxy.cfg
backend myapp
    server app1 localhost:8000 check inter 30s fall 3 rise 2
    http-check expect status 200
    http-check send meth GET uri /health/${HEALTH_CHECK_SECRET:-dev}/node/
```

## Application health checks

Application checks make sure every production service your app depends on is
reachable and operational. **Uptime monitors** such as Pingdom,
Better Uptime, or StatusCake watch these endpoints and page on-call engineers when
something goes down.

To cover the whole stack — databases, caches, message brokers, email, storage —
you'll need some extra dependencies:

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
It returns HTTP 200 when all checks pass and HTTP 500 when any fail — exactly the
codes monitors watch for.

## Pipeline health checks

Pipeline checks add **upstream provider status** on top of your application checks —
cloud platforms, PaaS providers, third-party services. The dev team watches these
via RSS/Atom feeds in Slack or Matrix, so upstream outages surface before they become
support tickets.

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

You can now alert engineers about upstream outages in Slack or Matrix.

Subscribe to the RSS feed in Slack:

1. Install the [Slack RSS App](https://slack.com/help/articles/218688467-Add-RSS-feeds-to-Slack).
1. In your `#ops` or `#incidents` channel, run:
   ```
   /feed subscribe https://www.example.com/health/<HEALTH_CHECK_SECRET>/pipeline/?format=rss
   ```

... or subscribe in Matrix:

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
