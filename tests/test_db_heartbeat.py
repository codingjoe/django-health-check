from unittest.mock import MagicMock, patch

import pytest

from health_check.contrib.db_heartbeat.backends import DatabaseHeartBeatCheck, SelectOne
from health_check.exceptions import ServiceUnavailable


class TestSelectOne:
    def test_as_sql(self):
        select_one = SelectOne()
        sql, params = select_one.as_sql(None, None)
        assert sql == "SELECT 1"
        assert not params

    def test_as_oracle(self):
        select_one = SelectOne()
        sql, params = select_one.as_oracle(None, None)
        assert sql == "SELECT 1 FROM DUAL"
        assert not params


class TestDatabaseHeartBeatCheck:
    @pytest.mark.django_db
    def test_check_status__success(self):
        health_check = DatabaseHeartBeatCheck()
        health_check.check_status()

    @patch("health_check.contrib.db_heartbeat.backends.connections")
    def test_check_status__failure(self, mock_connection):
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = (1,)
        mock_connection["default"].cursor.return_value.__enter__.return_value = mock_cursor

        health_check = DatabaseHeartBeatCheck()
        try:
            health_check.check_status()
        except Exception as e:
            pytest.fail(f"check_status() raised an exception unexpectedly: {e}")

    @patch("health_check.contrib.db_heartbeat.backends.connections")
    def test_check_status_service_unavailable(self, mock_connection):
        mock_connection["default"].cursor.side_effect = Exception("Database error")

        health_check = DatabaseHeartBeatCheck()
        with pytest.raises(ServiceUnavailable):
            health_check.check_status()
