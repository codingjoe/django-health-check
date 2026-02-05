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

Monitor cloud provider service health using their public RSS/Atom status feeds or APIs.

To enable cloud provider health checks, install the `rss` extra:

```shell
pip install django-health-check[rss]
```

### RSS Feeds

::: health_check.contrib.rss.AWS

::: health_check.contrib.rss.Heroku

::: health_check.contrib.rss.Azure

### Atom Feeds

::: health_check.contrib.rss.GoogleCloud

### Atlassian Status Pages

The following providers use Atlassian Status Page API v2:

::: health_check.contrib.rss.FlyIO

::: health_check.contrib.rss.PlatformSh

::: health_check.contrib.rss.DigitalOcean

::: health_check.contrib.rss.Render

::: health_check.contrib.rss.Vercel

## Custom RSS/Atom Feeds

These classes can be used to write custom RSS/Atom proxy checks.
Subclasses need to implement the `feed_url`, `timeout` and `max_age` attributes.

::: health_check.contrib.rss.RSSFeed

::: health_check.contrib.rss.AtomFeed

::: health_check.contrib.rss.AtlassianStatusPage
