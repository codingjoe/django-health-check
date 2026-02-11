# Checks

## Django Built-in Services

::: health_check.Cache

::: health_check.DNS

::: health_check.Database

::: health_check.Mail

::: health_check.Storage

## System Services

To use the psutil-based checks, you will need to install `psutil` extra:

```shell
pip install django-health-check[psutil]
```

::: health_check.contrib.psutil.Battery

::: health_check.contrib.psutil.CPU

::: health_check.contrib.psutil.Memory

::: health_check.contrib.psutil.Disk

::: health_check.contrib.psutil.Temperature

## 3rd Party Services

To use the checks, you will need to install and set up their corresponding dependencies.

To enable AWS health checks, install the extra for the `contrib` checks:

```shell
pip install django-health-check[redis,rabbitmq,celery,kafka]
```

::: health_check.contrib.celery.Ping

::: health_check.contrib.kafka.Kafka

::: health_check.contrib.rabbitmq.RabbitMQ

::: health_check.contrib.redis.Redis

## Cloud Provider Status

Monitor cloud provider service health using their public RSS/Atom status feeds or APIs.

Cloud provider health checks require different extras depending on the provider:

```shell
pip install django-health-check[rss,atlassian]
```

::: health_check.contrib.rss.AWS

::: health_check.contrib.rss.Azure

::: health_check.contrib.atlassian.Cloudflare

::: health_check.contrib.atlassian.DigitalOcean

::: health_check.contrib.atlassian.FlyIo

::: health_check.contrib.atlassian.GitHub

::: health_check.contrib.rss.GoogleCloud

::: health_check.contrib.rss.Heroku

::: health_check.contrib.atlassian.PlatformSh

::: health_check.contrib.atlassian.Render

::: health_check.contrib.atlassian.Sentry

::: health_check.contrib.atlassian.Vercel

## Custom Status Page Feeds

These classes can be used to write custom status page proxy checks.
Subclasses need to implement the required attributes as documented.

::: health_check.contrib.rss.Feed

::: health_check.contrib.atlassian.AtlassianStatusPage
