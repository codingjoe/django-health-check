from unittest.mock import patch

from celery.exceptions import TaskRevokedError
from celery.exceptions import TimeoutError as CeleryTimeout

from health_check.contrib.celery.backends import CeleryHealthCheck
from health_check.exceptions import ServiceReturnedUnexpectedResult, ServiceUnavailable


class FakeResult:
    def __init__(self, result=None, get_side_effect=None):
        self.result = result
        self._get_side_effect = get_side_effect

    def get(self, timeout=None):
        if isinstance(self._get_side_effect, Exception):
            raise self._get_side_effect
        return self.result


def test_celery_returns_unexpected_result():
    chk = CeleryHealthCheck()
    chk.queue = None
    fake = FakeResult(result=9)  # wrong result
    with patch("health_check.contrib.celery.backends.add") as mock_add:
        mock_add.apply_async.return_value = fake
        chk.run_check()
        assert any(isinstance(e, ServiceReturnedUnexpectedResult) for e in chk.errors)


def test_celery_apply_async_raises_oserror():
    chk = CeleryHealthCheck()
    chk.queue = None
    with patch("health_check.contrib.celery.backends.add") as mock_add:
        mock_add.apply_async.side_effect = OSError("io error")
        chk.run_check()
        assert chk.errors
        assert any(isinstance(e, ServiceUnavailable) for e in chk.errors)


def test_celery_apply_async_raises_not_implemented():
    chk = CeleryHealthCheck()
    chk.queue = None
    with patch("health_check.contrib.celery.backends.add") as mock_add:
        mock_add.apply_async.side_effect = NotImplementedError()
        chk.run_check()
        assert chk.errors
        assert any(isinstance(e, ServiceUnavailable) for e in chk.errors)


def test_celery_result_get_raises_task_revoked():
    chk = CeleryHealthCheck()
    chk.queue = None
    fake = FakeResult(get_side_effect=TaskRevokedError())
    with patch("health_check.contrib.celery.backends.add") as mock_add:
        mock_add.apply_async.return_value = fake
        chk.run_check()
        assert chk.errors
        assert any(isinstance(e, ServiceUnavailable) for e in chk.errors)


def test_celery_result_get_raises_timeout():
    chk = CeleryHealthCheck()
    chk.queue = None
    fake = FakeResult(get_side_effect=CeleryTimeout())
    with patch("health_check.contrib.celery.backends.add") as mock_add:
        mock_add.apply_async.return_value = fake
        chk.run_check()
        assert chk.errors
        assert any(isinstance(e, ServiceUnavailable) for e in chk.errors)


def test_celery_result_get_raises_unknown():
    chk = CeleryHealthCheck()
    chk.queue = None
    fake = FakeResult(get_side_effect=RuntimeError("boom"))
    with patch("health_check.contrib.celery.backends.add") as mock_add:
        mock_add.apply_async.return_value = fake
        chk.run_check()
        assert chk.errors
        assert any(isinstance(e, ServiceUnavailable) for e in chk.errors)
