# Usage

## Set up monitoring

You can point an uptime monitor at your service. Examples are Pingdom and
StatusCake. The `/health/` endpoint returns HTTP 200 when every check passes.
It returns HTTP 500 when a check fails.

The [Cookbook](cookbook.md) gives examples of multi-tier endpoint setups.
It includes uptime monitoring, container probes, reverse-proxy configuration,
and RSS/Atom integration into Slack or Matrix.

::: health_check.views.HealthCheckView
    options:
      members:
        - max_age
        - auth_token
        - allow_anonymous

## Get machine-readable reports

### Plain text

For simple monitoring and scripting, request plain text. Set the `Accept` HTTP
header to `text/plain`. Or pass `format=text` as a query parameter.

When every check passes, the endpoint returns plain text with HTTP 200. When a
check fails, the endpoint returns HTTP 500:

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

This format is useful for command-line tools and simple scripts. These tools
do not parse JSON.

### JSON

Set the `Accept` HTTP header to `application/json`. Or pass `format=json` as a
query parameter.

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

These endpoints always return HTTP 200. The feed lists each check. Failed checks
appear as categories and item descriptions.

## Write a custom health check

You can also write your own checks. Inherit from
[HealthCheck][health_check.HealthCheck] and implement the `run` method.

::: health_check.HealthCheck

## Django command

Run the Django command `health_check` from the shell. You can also schedule it
with cron:

```shell
django-admin health_check health_check
```

The `endpoint` argument is the `name` of the health check URL pattern in your
`urls.py`. See the [installation guide](install.md). The command resolves the
name with `reverse()`. Then it runs the checks over HTTP against the running
server:

```
Database                 ... OK
CustomHealthCheck        ... Unavailable: Something went wrong!
```

If the view sets `auth_token`, pass a bearer token:

```shell
django-admin health_check health_check --auth-token "$HEALTH_CHECK_AUTH_TOKEN"
```

The command reads `HEALTH_CHECK_AUTH_TOKEN` from the environment when you omit
`--auth-token`.

Pass `--no-http` to skip the HTTP server. This option is useful for container
health checks that do not run a web server:

```shell
django-admin health_check health_check --no-http
```

A critical error exits the command with the code `1`.

## Performance tweaks

Every check runs asynchronously. It uses `asyncio` or a thread pool, based on
its implementation. IO-bound checks run in parallel. As a result, responses
return faster.

Synchronous checks (for example [Database][health_check.checks.Database],
[Mail][health_check.checks.Mail], or [Storage][health_check.checks.Storage])
run in the default thread pool of the event loop. That pool usually persists
between requests. It is fast, but it can increase memory use. This is a problem
for some applications, for example `S3Storage`. `S3Storage` uses thread-local
connections.

To prevent this problem, use a custom executor. The executor starts a new
thread pool for each request and stops it when the checks finish. Subclass
`HealthCheckView` and override the `get_executor` method. Return a context
manager with a new `ThreadPoolExecutor` for each request.

```python
from concurrent.futures import ThreadPoolExecutor
from health_check.views import HealthCheckView


class CustomHealthCheckView(HealthCheckView):
    def get_executor(self):
        return ThreadPoolExecutor(max_workers=len(self.checks))
```

Then every request has its own thread pool. You keep the speed of concurrent
execution for synchronous checks. Memory use stays under control.

To let a CDN cache successful responses, set
[`max_age`](#health_check.views.HealthCheckView.max_age) to
`timedelta(seconds=30)` on `HealthCheckView`. A failing check returns HTTP 500,
which is never cached. A request with a valid bearer token skips the
cache and runs the checks.
