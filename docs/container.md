# Container (Docker/Podman)

Django HealthCheck can be integrated into various container orchestration systems by defining health checks that utilize the `manage.py health_check` command.
Below are examples for Containerfile/Dockerfile, Docker Compose, and Kubernetes.

> [!TIP]
> The health check command does not require curl/wget to minimize your container image.

## Container Health Check Endpoint

You may want to limit the checks performed by the health check command to a subset of all available checks.
E.g. you might want to skip checks that are monitoring external services like databases, caches, or task queues
since those containers usually provide their own health checks.

You can add a separate health check endpoint for container checks:

```python
# urls.py
from django.urls import include, path
from health_check.views import HealthCheckView

urlpatterns = [
    # …
    path(
        "container/health/",
        HealthCheckView.as_view(
            checks=["health_check.Disk", "health_check.Memory"],
        ),
        name="health_check-container",
    ),
]
```

… and then run the health check command:

```shell
python manage.py health_check health_check-container localhost:8000 --forwarded-host example.com
```

> [!IMPORTANT]
> When using the `health_check` command, ensure that the host is included in your `ALLOWED_HOSTS` setting.
> The command automatically uses the first entry from `ALLOWED_HOSTS` for the `X-Forwarded-Host` header if available.
> For SSL-enabled applications, use the `--forwarded-proto https` flag.

Your host name and port may vary depending on your container setup.

## Configuration Examples

> [!TIP]
> For Prometheus users: The health check endpoint supports OpenMetrics format via `?format=openmetrics` for metrics scraping.

### Container Image

```Dockerfile
# Containerfile / Dockerfile
HEALTHCHECK --interval=30s --timeout=10s \
  CMD python manage.py health_check health_check-container web:8000 || exit 1
```

### Compose

```yaml
# compose.yml / docker-compose.yml
services:
  web:
    # … your service definition …
    healthcheck:
      test: ["CMD", "python", "manage.py", "health_check", "health_check-container", "web:8000"]
      interval: 60s
      timeout: 10s
```

### Kubernetes

```yaml
# deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: my-django-app
spec:
  template:
    spec:
      containers:
        - name: web
          image: my-django-image:latest
          livenessProbe:
            httpGet:
              path: /container/health/
              port: 8000
              httpHeaders:
                - name: X-Forwarded-Proto
                  value: https
                - name: X-Forwarded-Host
                  value: example.com  # Use your actual domain from ALLOWED_HOSTS
            periodSeconds: 60
            timeoutSeconds: 10
```

> [!TIP]
> Configure `X-Forwarded-Host` to match your domain from `ALLOWED_HOSTS` and set `X-Forwarded-Proto` to `https` if your application enforces SSL.
> See Django's [USE_X_FORWARDED_HOST](https://docs.djangoproject.com/en/stable/ref/settings/#std-setting-USE_X_FORWARDED_HOST) and [SECURE_PROXY_SSL_HEADER](https://docs.djangoproject.com/en/stable/ref/settings/#secure-proxy-ssl-header) settings.
