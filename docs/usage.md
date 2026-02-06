# Usage

## Setting up monitoring

You can use tools like Pingdom, StatusCake or other uptime robots to
monitor service status. The `/health/` endpoint will respond with an HTTP
200 if all checks passed and with an HTTP 500 if any of the tests
failed.

## Getting machine-readable reports

### Plain text

For simple monitoring and scripting, you can request plain text output with the `Accept` HTTP header set to `text/plain` or pass `format=text` as a query parameter.

The endpoint will return a plain text response with HTTP 200 if all checks passed and HTTP 500 if any check failed:

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

This format is particularly useful for command-line tools and simple monitoring scripts that don't need the overhead of JSON parsing.

### JSON

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

### OpenMetrics for Prometheus

For Prometheus monitoring, you can request OpenMetrics format:

```shell
$ curl http://www.example.com/health/?format=openmetrics
```

This will return metrics in the OpenMetrics exposition format, which can be scraped by Prometheus.

### RSS and Atom feeds

For RSS feed readers and monitoring tools, you can request RSS or Atom format:

```shell
$ curl http://www.example.com/health/?format=rss
$ curl http://www.example.com/health/?format=atom
```

You can also use the `Accept` header:

```shell
$ curl -H "Accept: application/rss+xml" http://www.example.com/health/
$ curl -H "Accept: application/atom+xml" http://www.example.com/health/
```

These endpoints always return a 200 status code with health check results in the feed content. Failed checks are indicated by categories and item descriptions.

## Writing a custom health check

You can write your own health checks by inheriting from
[HealthCheck][health_check.HealthCheck] and implementing the `run` method.

::: health_check.HealthCheck

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

### Running checks without HTTP server

In rare cases where no HTTP server is running (e.g., when using Django without HTTP),
you can skip the HTTP stack and run checks directly using the `--no-html` flag:

```shell
django-admin health_check health_check_test --no-html
```

This will run the health checks directly without making HTTP requests to the server.
The output format and exit codes remain the same as the HTTP version.

> [!WARNING]
> The `--no-html` option should only be used as a last resort.
> Checking the HTTP stack is the most crucial part of an application health check,
> and it should be running in most cases. Use this option only when you are certain
> that no HTTP server is needed for your application.
