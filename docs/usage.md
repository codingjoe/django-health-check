# Usage

## Setting up monitoring

You can point an uptime monitor such as Pingdom, StatusCake, or other
uptime robots at your service. The `/health/` endpoint returns an HTTP
200 when every check passes, and an HTTP 500 when any of them fails.

For step-by-step examples of multi-tier endpoint setups, including uptime
monitoring, container probes, reverse-proxy configuration, and RSS/Atom
integration into Slack or Matrix, see the [Cookbook](cookbook.md).

## Caching and authentication

### Caching for availability

A short cache protects the endpoint from request floods. Set `cache_timeout`
to let a CDN or reverse proxy reuse the response:

```python
import datetime

from django.urls import path
from health_check.views import HealthCheckView

urlpatterns = [
    path(
        "health/",
        HealthCheckView.as_view(
            cache_timeout=datetime.timedelta(seconds=30),
        ),
    ),
]
```

The view sends `Cache-Control: public, max-age=30` and a weak `ETag`.
The ETag changes only when a check result changes. A cache that revalidates
an unchanged result receives HTTP 304.

> [!WARNING]
> Only enable caching on endpoints without a secret in the URL. The view
> cannot detect URL secrets.

### Authentication

Set `authentication_token` to require a bearer token:

```python
import os

HealthCheckView.as_view(
    authentication_token=os.environ["HEALTH_CHECK_AUTHENTICATION_TOKEN"],
)
```

Send the token in the `Authorization` header:

```shell
curl -H "Authorization: Bearer $HEALTH_CHECK_AUTHENTICATION_TOKEN" https://example.com/health/
```

Requests without a valid token receive HTTP 403 before any check runs.
Authenticated responses bypass the cache and send `Cache-Control: no-store`.
This is the default because `allow_anonymous` is `False`.

### Cache busting with anonymous access

For a public endpoint, set `allow_anonymous=True`. Anonymous visitors get
the cached result. The uptime monitor sends the token and always gets a
fresh result:

```python
HealthCheckView.as_view(
    cache_timeout=datetime.timedelta(seconds=30),
    authentication_token=os.environ["HEALTH_CHECK_AUTHENTICATION_TOKEN"],
    allow_anonymous=True,
)
```

Any `Authorization` header with a wrong token receives HTTP 403 before
checks run. Random tokens cannot create cache variants or trigger checks.

> [!NOTE]
> When `authentication_token` is set, the `Authorization` header is
> reserved for it. Ensure your CDN honors `Vary: Authorization` and forwards
> the header to the origin.

> [!NOTE]
> A client can still ask a shared cache to revalidate with
> `Cache-Control: no-cache`. Configure your CDN to ignore client cache
> directives if anonymous clients must never trigger checks.

### Custom policies

Override `is_authorized` to implement another permission model. Override
`should_bypass_cache` to change when a request skips the cache.

```python
import os

from health_check.views import HealthCheckView


class TeamHealthCheckView(HealthCheckView):
    def is_authorized(self, request):
        return request.headers.get("X-Team-Token") == os.environ["TEAM_TOKEN"]

    def should_bypass_cache(self, request):
        return self.is_authorized(request)
```

> [!WARNING]
> When caching is enabled and you use another credential, return `True` from
> `should_bypass_cache` for authenticated requests. Otherwise a shared cache
> can serve the response to another client.

## Getting machine-readable reports

### Plain text

For simple monitoring and scripting, ask for plain text. Set the `Accept` HTTP header to `text/plain`, or pass `format=text` as a query parameter.

When everything passes, you get a plain text response with HTTP 200. When a check fails, you get HTTP 500:

```shell
$ curl -v -X GET -H "Accept: text/plain" http://www.example.com/health/

> GET /health/ HTTP/1.1
> Host: www.example.com
> Accept: text/plain
>
< HTTP/1.1 200 OK
< Content-Type: text/plain; charset=utf-8

CacheBackend: OK
DatabaseBackend: OK
S3BotoStorageHealthCheck: OK

$ curl -v -X GET http://www.example.com/health/?format=text

> GET /health/?format=text HTTP/1.1
> Host: www.example.com
>
< HTTP/1.1 200 OK
< Content-Type: text/plain; charset=utf-8

CacheBackend: OK
DatabaseBackend: OK
S3BotoStorageHealthCheck: OK
```

This format is handy for command-line tools and simple scripts that don't want to parse JSON.

### JSON

Want machine-readable results? Set the `Accept` HTTP header to
`application/json`, or pass `format=json` as a query parameter.

The endpoint returns a JSON response:

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

### OpenMetrics for Prometheus

If you monitor with Prometheus, request the OpenMetrics format:

```shell
$ curl http://www.example.com/health/?format=openmetrics
```

Prometheus can scrape these metrics directly.

### RSS and Atom feeds

For feed readers and monitoring tools, request the RSS or Atom format:

```shell
$ curl http://www.example.com/health/?format=rss
$ curl http://www.example.com/health/?format=atom
```

You can also use the `Accept` header:

```shell
$ curl -H "Accept: application/rss+xml" http://www.example.com/health/
$ curl -H "Accept: application/atom+xml" http://www.example.com/health/
```

These endpoints always answer with HTTP 200. The feed lists each check, and failed checks show up as categories and item descriptions.

## Writing a custom health check

You can write your own checks too. Inherit from
[HealthCheck][health_check.HealthCheck] and implement the `run` method.

::: health_check.HealthCheck

## Django command

Run the Django command `health_check` from the shell, or schedule it
with cron:

```shell
django-admin health_check health_check
```

The `endpoint` argument is the `name` of the health check URL pattern defined in your
`urls.py` (see the [installation guide](install.md)). The command looks it up with
`reverse()` and runs the checks over HTTP against the running server:

```
Database                 ... OK
CustomHealthCheck        ... Unavailable: Something went wrong!
```

Pass `--no-http` to skip the HTTP server entirely. Handy for container
health checks that don't run a web server:

```shell
django-admin health_check health_check --no-http
```

A critical error exits the command with the code `1`.

## Performance tweaks

Every check runs asynchronously, via `asyncio` or a thread pool, depending
on how each check is implemented.
IO-bound checks run in parallel, so responses come back faster.

Synchronous checks (for example [Database][health_check.checks.Database], [Mail][health_check.checks.Mail],
or [Storage][health_check.checks.Storage]) run in the event loop's default thread pool.
That pool usually persists between requests. It keeps things fast, but it can
grow memory usage. That's a problem for some applications, especially `S3Storage`,
which uses thread-local connections.

To avoid that, use a custom executor that spins up a fresh thread pool per
request and tears it down when the checks finish. Subclass `HealthCheckView`
and override the `get_executor` method to return a context manager with a
new `ThreadPoolExecutor` each time.

```python
from concurrent.futures import ThreadPoolExecutor
from health_check.views import HealthCheckView


class CustomHealthCheckView(HealthCheckView):
    def get_executor(self):
        return ThreadPoolExecutor(max_workers=len(self.checks))
```

This gives every request its own thread pool. You keep the speed of
concurrent execution for synchronous checks, but the memory stays under
control.
