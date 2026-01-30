import os

import pytest

pytest.importorskip("redis")

from health_check.contrib.redis.backends import RedisHealthCheck


@pytest.mark.integration
def test_redis_integration_ping():
    """Integration test: ping real Redis server when available."""
    redis_url = os.getenv("REDIS_URL")
    if not redis_url:
        pytest.skip("REDIS_URL not set; skipping integration test")

    checker = RedisHealthCheck(redis_url=redis_url)
    checker.check_status()
    assert not checker.errors
