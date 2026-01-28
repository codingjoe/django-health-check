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

- caches
- databases
- disk and memory utilization
- email servers
- storages
- Celery
- RabbitMQ
- Redis

Writing your own custom health checks is also very quick and easy.

We also like contributions, so don’t be afraid to make a pull request.

## Use Cases

The primary intended use case is to monitor conditions via HTTP(S), with
responses available in HTML and JSON formats. When you get back a
response that includes one or more problems, you can then decide the
appropriate course of action, which could include generating
notifications and/or automating the replacement of a failing node with a
new one. If you are monitoring health in a high-availability environment
with a load balancer that returns responses from multiple nodes, please
note that certain checks (e.g., disk and memory usage) will return
responses specific to the node selected by the load balancer.
