# Usage

## Setting up monitoring

You can use tools such as Pingdom, StatusCake, or other uptime robots to
monitor service status. The `/health/` endpoint responds with an HTTP
200 when all checks pass. It responds with an HTTP 500 when any check
fails.

For step-by-step examples of multi-tier endpoint setups, including uptime
monitoring, container probes, reverse-proxy configuration, and RSS/Atom
integration into Slack or Matrix, see the [Cookbook](cookbook.md).

## Getting machine-readable reports

### Plain text

For simple monitoring and scripting, you can request plain text output. Set the `Accept` HTTP header to `text/plain`. You can also pass `format=text` as a query parameter.

The endpoint returns a plain text response with HTTP 200 when all checks pass. It returns HTTP 500 when any check fails:

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

This format is useful for command-line tools and simple monitoring scripts that do not need to parse JSON.

### JSON

For machine-readable status reports, you can request the `/health/`
endpoint. Set the `Accept` HTTP header to `application/json`. You can
also pass `format=json` as a query parameter.

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

For Prometheus monitoring, you can request the OpenMetrics format:

```shell
$ curl http://www.example.com/health/?format=openmetrics
```

This returns metrics in the OpenMetrics exposition format. Prometheus can scrape them.

### RSS and Atom feeds

For RSS feed readers and monitoring tools, you can request the RSS or Atom format:

```shell
$ curl http://www.example.com/health/?format=rss
$ curl http://www.example.com/health/?format=atom
```

You can also use the `Accept` header:

```shell
$ curl -H "Accept: application/rss+xml" http://www.example.com/health/
$ curl -H "Accept: application/atom+xml" http://www.example.com/health/
```

These endpoints always return a 200 status code. The feed content includes the health check results. Failed checks appear as categories and item descriptions.

## Writing a custom health check

Write your own health checks. Inherit from
[HealthCheck][health_check.HealthCheck] and implement the `run` method.

::: health_check.HealthCheck

## Django command

Run the Django command `health_check` to perform your health
checks from the command line. You can also run it periodically with a
cron job, as follows:

```shell
django-admin health_check --help
```

This command prints the following output:

```
Database                 ... OK
CustomHealthCheck        ... Unavailable: Something went wrong!
```

As with the HTTP version, a critical error makes the command
quit with the exit code `1`.

## Performance tweaks

All checks run asynchronously, either via `asyncio` or via a thread pool,
depending on the implementation of each check.
This lets the IO-bound checks run at the same time,
which reduces the response time.

The event loop's default executor runs synchronous checks
(for example [Database][health_check.checks.Database], [Mail][health_check.checks.Mail],
or [Storage][health_check.checks.Storage]) in a thread pool.
This pool usually persists across requests. As a result, the pool can
allocate a large amount of memory. This can be undesirable for some
applications, especially `S3Storage`, which uses thread-local connections.

Use a custom executor to avoid this. The executor creates a new thread
pool for each request and cleans it up after the checks complete. To do
this, subclass `HealthCheckView` and override the `get_executor` method.
Return a context manager that provides a new `ThreadPoolExecutor`
instance for each request.

```python
from concurrent.futures import ThreadPoolExecutor
from health_check.views import HealthCheckView


class CustomHealthCheckView(HealthCheckView):
    def get_executor(self):
        return ThreadPoolExecutor(max_workers=len(self.checks))
```

This approach gives each request a fresh thread pool.
It helps manage memory usage
while it keeps the benefits of concurrent execution for synchronous checks.
