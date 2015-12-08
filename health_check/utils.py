# -*- coding: utf-8 -*-
from django.db.models.options import get_verbose_name

from health_check.backends.base import BaseHealthCheckBackend
from health_check.plugins import plugin_dir


class BaseHealthCheck(BaseHealthCheckBackend):
    def check_status(self):
        self._wrapped()


def healthcheck(func_or_name):
    """
    Usage:

        @healthcheck("My Check")
        def my_check():
            if something_is_not_okay():
                raise ServiceReturnedUnexpectedResult()

        @healthcheck
        def other_check():
            if something_is_not_available():
                raise ServiceUnavailable()
    """

    def inner(func):
        cls = type(func.__name__, (BaseHealthCheck,), {'_wrapped': staticmethod(func)})
        cls.identifier = name
        plugin_dir.register(cls)
        return func

    if callable(func_or_name):
        name = get_verbose_name(func_or_name.__name__).replace('_', ' ')
        return inner(func_or_name)
    else:
        name = func_or_name
        return inner
