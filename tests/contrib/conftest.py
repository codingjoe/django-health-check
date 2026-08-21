"""Pytest fixtures that run integration test dependencies in containers."""

import pytest


def _require_docker() -> None:
    """Skip the test when a Docker daemon is not reachable."""
    from docker import from_env
    from docker.errors import DockerException

    try:
        from_env().ping()
    except DockerException as exc:
        pytest.skip(f"Docker daemon is not available: {exc}")


@pytest.fixture(scope="module")
def redis_url():
    """Start a Redis container and return its URL."""
    from testcontainers.community.redis import RedisContainer

    _require_docker()
    with RedisContainer("redis:7") as redis:
        yield f"redis://localhost:{redis.get_exposed_port(6379)}/0"


@pytest.fixture(scope="module")
def redis_sentinel():
    """Start a Redis master and a Sentinel, return their nodes and service name."""
    from testcontainers.community.redis import RedisContainer
    from testcontainers.core.container import DockerContainer

    _require_docker()
    with RedisContainer("redis:7") as master:
        master_port = master.get_exposed_port(6379)
        conf = (
            "port 26379\n"
            f"sentinel monitor mymaster 127.0.0.1 {master_port} 1\n"
            "sentinel down-after-milliseconds mymaster 5000\n"
            "sentinel failover-timeout mymaster 60000\n"
            "sentinel parallel-syncs mymaster 1\n"
        )
        sentinel = (
            DockerContainer("redis:7")
            .with_command(
                "sh -c 'chmod 666 /tmp/sentinel.conf "
                "&& redis-server /tmp/sentinel.conf --sentinel'"
            )
            .with_copy_into_container(
                conf.encode(),
                "/tmp/sentinel.conf",  # noqa: S108 - path is inside the container
            )
            .with_exposed_ports(26379)
        )
        with sentinel:
            nodes = [("localhost", sentinel.get_exposed_port(26379))]
            yield nodes, "mymaster"


@pytest.fixture(scope="module")
def kafka_bootstrap_servers():
    """Fixture that returns a running Kafka bootstrap server address."""
    from testcontainers.community.kafka import KafkaContainer

    _require_docker()
    with KafkaContainer() as kafka:
        yield kafka.get_bootstrap_server()


@pytest.fixture(scope="module")
def rabbitmq_url():
    """Return a connection URL for a running RabbitMQ broker."""
    from testcontainers.core.container import DockerContainer
    from testcontainers.core.wait_strategies import LogMessageWaitStrategy

    _require_docker()
    container = DockerContainer("rabbitmq:3-management")
    container.with_exposed_ports(5672)
    container.waiting_for(LogMessageWaitStrategy("Server startup complete"))
    with container:
        yield f"amqp://guest:guest@localhost:{container.get_exposed_port(5672)}//"
