# Container (Docker/Podman)

Django HealthCheck can be integrated into various container orchestration systems by defining health checks that utilize the `manage.py health_check` command.
Below are examples for Containerfile/Dockerfile, Docker Compose, and Kubernetes.

> [!TIP]
> The health check command does not require curl or any HTTP client in your container image.

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
python manage.py health_check health_check-container localhost:8000
```

Your host name and port may vary depending on your container setup.

## Configuration Examples

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
            exec:
              command:
                - python
                - manage.py
                - health_check
                - health_check-container
                - web:8000
            periodSeconds: 60
            timeoutSeconds: 10
```
