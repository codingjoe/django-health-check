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

Monitor AWS service health using their public RSS status feeds.

To enable AWS health checks, install the `rss` extra:

```shell
pip install django-health-check[rss]
```

::: health_check.contrib.rss.AWS
