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

To enable AWS health checks, install the correct extra:

```shell
pip install django-health-check[redis,rabbitmq,celery,kafka]
```

::: health_check.contrib.celery.Ping

::: health_check.contrib.kafka.Kafka

::: health_check.contrib.rabbitmq.RabbitMQ

::: health_check.contrib.redis.Redis

## Cloud Provider Status

Monitor cloud provider service health using their public RSS/Atom status feeds.

To enable cloud provider health checks, install the `rss` extra:

```shell
pip install django-health-check[rss]
```

### Base Classes

::: health_check.contrib.rss.StatusFeedBase

::: health_check.contrib.rss.RSSFeed

::: health_check.contrib.rss.AtomFeed

### RSS Feed Providers

::: health_check.contrib.rss.AWS

::: health_check.contrib.rss.Heroku

::: health_check.contrib.rss.Azure

### Atom Feed Providers

::: health_check.contrib.rss.GoogleCloud

::: health_check.contrib.rss.FlyIO

::: health_check.contrib.rss.PlatformSh

::: health_check.contrib.rss.DigitalOcean

::: health_check.contrib.rss.Render

::: health_check.contrib.rss.Vercel

::: health_check.contrib.rss.Railway

::: health_check.contrib.rss.Heroku

::: health_check.contrib.rss.Azure

::: health_check.contrib.rss.GoogleCloud

::: health_check.contrib.rss.FlyIO

::: health_check.contrib.rss.PlatformSh

::: health_check.contrib.rss.DigitalOcean

::: health_check.contrib.rss.Render

::: health_check.contrib.rss.Vercel

::: health_check.contrib.rss.Railway
