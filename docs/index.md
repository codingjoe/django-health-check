<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="https://github.com/codingjoe/django-health-check/raw/main/docs/images/logo-dark.svg">
    <source media="(prefers-color-scheme: light)" srcset="https://github.com/codingjoe/django-health-check/raw/main/docs/images/logo-light.svg">
    <img alt="Django HealthCheck: Pluggable health checks for Django applications" src="https://github.com/codingjoe/django-health-check/raw/main/docs/images/logo-light.svg">
  </picture>
<br>
  <a href="https://codingjoe.dev/django-health-check/">Documentation</a> |
  <a href="https://github.com/codingjoe/django-health-check/issues/new/choose">Issues</a> |
  <a href="https://github.com/codingjoe/django-health-check/releases">Changelog</a> |
  <a href="https://github.com/sponsors/codingjoe">Funding</a> 💚
</p>

# Django HealthCheck

[![version](https://img.shields.io/pypi/v/django-health-check.svg)](https://pypi.python.org/pypi/django-health-check/)
[![pyversion](https://img.shields.io/pypi/pyversions/django-health-check.svg)](https://pypi.python.org/pypi/django-health-check/)
[![djversion](https://img.shields.io/pypi/djversions/django-health-check.svg)](https://pypi.python.org/pypi/django-health-check/)
[![license](https://img.shields.io/badge/license-MIT-blue.svg)](https://pypi.python.org/pypi/django-health-check/)

This project checks for various conditions and provides reports when
anomalous behavior is detected.

[Documentation](https://codingjoe.dev/django-health-check/) | [Issues](https://github.com/codingjoe/django-health-check/issues/new/choose) | [Changelog](https://github.com/codingjoe/django-health-check/releases) | [Funding](https://github.com/sponsors/codingjoe) 💚

The following health checks are bundled with this project:

- [caches][health_check.Cache] & [databases][health_check.Database]
- [disk][health_check.Disk] & [memory][health_check.Disk] utilization
- [DNS][health_check.DNS] & [email][health_check.Mail]
- [storages][health_check.Storage]
- [Celery][health_check.contrib.celery.Ping], [Kafka][health_check.contrib.kafka.Kafka],
  [RabbitMQ][health_check.contrib.rabbitmq.RabbitMQ] & [Redis][health_check.contrib.redis.Redis]

Writing your own custom health checks is also very quick and easy.

We also like contributions, so don’t be afraid to make a pull request.

## Integrations

The main entry point is an HTML view for your web application. However,
there are multiple machine-readable formats available for integration:

- [HTTP Status Codes] for load balancers and uptime monitors
- [OpenMetrics] for [Prometheus] and [Grafana]
- [CLI](container.md) for [Docker], [Podman] or [Kubernetes] health checks
- [RSS]/[Atom] feed
- [JSON] API for custom integrations

[atom]: https://en.wikipedia.org/wiki/Atom_(standard)
[docker]: https://www.docker.com/
[grafana]: https://grafana.com/
[http status codes]: https://en.wikipedia.org/wiki/List_of_HTTP_status_codes
[json]: https://www.json.org/
[kubernetes]: https://kubernetes.io/
[openmetrics]: https://openmetrics.io/
[podman]: https://podman.io/
[prometheus]: https://prometheus.io/
[rss]: https://en.wikipedia.org/wiki/RSS
