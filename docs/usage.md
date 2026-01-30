# Usage

## Setting up monitoring

You can use tools like Pingdom, StatusCake or other uptime robots to
monitor service status. The `/health/` endpoint will respond with an HTTP
200 if all checks passed and with an HTTP 500 if any of the tests
failed. Getting machine-readable JSON reports

If you want machine-readable status reports you can request the `/health/`
endpoint with the `Accept` HTTP header set to `application/json` or pass
`format=json` as a query parameter.

The backend will return a JSON response:

```shell
$ curl -v -X GET -H "Accept: application/json" http://www.example.com/health/

> GET /health/ HTTP/1.1
> Host: www.example.com
> Accept: application/json
>
< HTTP/1.1 200 OK
< Content-Type: application/json

{
    "CacheBackend": "working",
    "DatabaseBackend": "working",
    "S3BotoStorageHealthCheck": "working"
}

$ curl -v -X GET http://www.example.com/health/?format=json

> GET /health/?format=json HTTP/1.1
> Host: www.example.com
>
< HTTP/1.1 200 OK
< Content-Type: application/json

{
    "CacheBackend": "working",
    "DatabaseBackend": "working",
    "S3BotoStorageHealthCheck": "working"
}
```

## Writing a custom health check

You can write your own health checks by inheriting from [HealthCheck][health_check.HealthCheck]
and implementing the `check_status` method. For example:

```python
import dataclasses
from health_check import HealthCheck


@dataclasses.dataclass
class MyHealthCheckBackend(HealthCheck):
    #: The status endpoints will respond with a 200 status code
    #: even if the check errors.
    critical_service = False

    def check_status(self):
        # The test code goes here.
        # Raise a `HealthCheckException` if the check fails,
        # similar to Django's form validation.
        pass
```

::: health_check.HealthCheck

## Customizing output

You can customize HTML or JSON rendering by inheriting from [HealthCheckView][health_check.views.HealthCheckView]
and customizing the [template_name][django.views.generic.base.TemplateView], [render_to_response_json][health_check.views.HealthCheckView] properties:

```python
# views.py
from django.http import HttpResponse, JsonResponse

from health_check.views import HealthCheckView


class HealthCheckCustomView(HealthCheckView):
    template_name = "myapp/health_check_dashboard.html"  # customize the used templates

    def render_to_response_json(self, status):  # customize JSON output
        return JsonResponse(
            {
                label: "COOL" if status == 200 else "SWEATY"
                for label, check in self.results.items()
            },
            status=status,
        )


# urls.py
from django.urls import path

from . import views

urlpatterns = [
    # …
    path(
        "ht/",
        views.HealthCheckCustomView.as_view(
            checks=["myapp.health_checks.MyHealthCheckBackend"]
        ),
        name="health_check_custom",
    ),
]
```

::: health_check.views.HealthCheckView

## Django command

You can run the Django command `health_check` to perform your health
checks via the command line, or periodically with a cron, as follows:

```shell
django-admin health_check --help
```

This should yield the following output:

```
Database                 ... OK
CustomHealthCheck        ... Unavailable: Something went wrong!
```

Similar to the http version, a critical error will cause the command to
quit with the exit code `1`.
