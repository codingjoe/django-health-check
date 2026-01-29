import pytest

pytest.importorskip("amqp")
pytest.importorskip("kombu")

from unittest import mock

from amqp.exceptions import AccessRefused

from health_check.contrib.rabbitmq.backends import RabbitMQHealthCheck


class TestRabbitMQHealthCheck:
    """Test RabbitMQ health check."""

    @mock.patch("health_check.contrib.rabbitmq.backends.getattr")
    @mock.patch("health_check.contrib.rabbitmq.backends.Connection")
    def test_broker_refused_connection(self, mocked_connection, mocked_getattr):
        """Test when the connection to RabbitMQ is refused."""
        mocked_getattr.return_value = "broker_url"

        conn_exception = ConnectionRefusedError("Refused connection")

        # mock returns
        mocked_conn = mock.MagicMock()
        mocked_connection.return_value.__enter__.return_value = mocked_conn
        mocked_conn.connect.side_effect = conn_exception

        # instantiates the class
        rabbitmq_healthchecker = RabbitMQHealthCheck()

        # invokes the method check_status()
        rabbitmq_healthchecker.check_status()
        assert len(rabbitmq_healthchecker.errors), 1

        # mock assertions
        mocked_connection.assert_called_once_with("broker_url")

    @mock.patch("health_check.contrib.rabbitmq.backends.getattr")
    @mock.patch("health_check.contrib.rabbitmq.backends.Connection")
    def test_broker_auth_error(self, mocked_connection, mocked_getattr):
        """Test that the connection to RabbitMQ has an authentication error."""
        mocked_getattr.return_value = "broker_url"

        conn_exception = AccessRefused("Refused connection")

        # mock returns
        mocked_conn = mock.MagicMock()
        mocked_connection.return_value.__enter__.return_value = mocked_conn
        mocked_conn.connect.side_effect = conn_exception

        # instantiates the class
        rabbitmq_healthchecker = RabbitMQHealthCheck()

        # invokes the method check_status()
        rabbitmq_healthchecker.check_status()
        assert len(rabbitmq_healthchecker.errors), 1

        # mock assertions
        mocked_connection.assert_called_once_with("broker_url")

    @mock.patch("health_check.contrib.rabbitmq.backends.getattr")
    @mock.patch("health_check.contrib.rabbitmq.backends.Connection")
    def test_broker_connection_upon_none_url(self, mocked_connection, mocked_getattr):
        """Thest when the connection to RabbitMQ has no ``broker_url``."""
        mocked_getattr.return_value = None
        # if the variable BROKER_URL is not set, AccessRefused exception is raised
        conn_exception = AccessRefused("Refused connection")

        # mock returns
        mocked_conn = mock.MagicMock()
        mocked_connection.return_value.__enter__.return_value = mocked_conn
        mocked_conn.connect.side_effect = conn_exception

        # instantiates the class
        rabbitmq_healthchecker = RabbitMQHealthCheck()

        # invokes the method check_status()
        rabbitmq_healthchecker.check_status()
        assert len(rabbitmq_healthchecker.errors), 1

        # mock assertions
        mocked_connection.assert_called_once_with(None)
