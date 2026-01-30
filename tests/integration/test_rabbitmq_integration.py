import os

import pytest

pytest.importorskip("kombu")

from health_check.contrib.rabbitmq.backends import RabbitMQHealthCheck


@pytest.mark.integration
def test_rabbitmq_integration_connect():
    broker_url = os.getenv("BROKER_URL") or os.getenv("RABBITMQ_URL")
    if not broker_url:
        pytest.skip("BROKER_URL/RABBITMQ_URL not set; skipping integration test")

    checker = RabbitMQHealthCheck()
    # override settings via attribute to avoid reading Django settings
    checker.namespace = None
    checker.check_status()
    assert not checker.errors
