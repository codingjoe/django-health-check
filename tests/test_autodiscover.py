import pytest

pytest.importorskip("celery")
from celery import current_app
from django.conf import settings

from health_check.contrib.celery.backends import CeleryHealthCheck
from health_check.contrib.celery_ping.backends import CeleryPingHealthCheck
from health_check.plugins import plugin_dir


class TestAutoDiscover:
    def test_autodiscover(self):
        health_check_plugins = list(
            filter(
                lambda x: x.startswith("health_check.") and "celery" not in x,
                settings.INSTALLED_APPS,
            )
        )

        non_celery_plugins = [
            x for x in plugin_dir._registry if not issubclass(x[0], (CeleryHealthCheck, CeleryPingHealthCheck))
        ]

        # The number of installed apps excluding celery should equal to all plugins except celery
        assert len(non_celery_plugins) == len(health_check_plugins)

    def test_discover_celery_queues(self):
        celery_plugins = [x for x in plugin_dir._registry if issubclass(x[0], CeleryHealthCheck)]
        assert len(celery_plugins) == len(current_app.amqp.queues)
