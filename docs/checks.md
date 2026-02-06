# Checks

## Django Built-in Services

::: health_check.Cache

::: health_check.DNS

::: health_check.Database

::: health_check.Disk

::: health_check.Mail

::: health_check.Memory

::: health_check.Storage

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

- For RSS/Atom feed-based providers (AWS, Heroku, Azure, Google Cloud):

```shell
pip install django-health-check[rss]
```

- For Atlassian Status Page API providers (Cloudflare, DigitalOcean, Fly.io, Platform.sh, Render, Vercel):

```shell
pip install django-health-check[atlassian]
```

::: health_check.contrib.rss.AWS

::: health_check.contrib.rss.Azure

::: health_check.contrib.rss.GoogleCloud

::: health_check.contrib.atlassian.Cloudflare

::: health_check.contrib.atlassian.DigitalOcean

::: health_check.contrib.atlassian.FlyIo

::: health_check.contrib.rss.Heroku

::: health_check.contrib.atlassian.PlatformSh

::: health_check.contrib.atlassian.Render

::: health_check.contrib.atlassian.Vercel

## Custom Status Page Feeds

These classes can be used to write custom status page proxy checks.
Subclasses need to implement the required attributes as documented.

::: health_check.contrib.rss.Feed

::: health_check.contrib.atlassian.AtlassianStatusPage
