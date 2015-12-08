import logging

from django.utils.encoding import force_text
from django.utils.functional import cached_property
from django.utils.translation import ugettext_lazy as _

logger = logging.getLogger('health-check')


class HealthCheckStatusType(object):
    unavailable = 0
    working = 1
    unexpected_result = 2


class HealthCheckException(Exception):
    type = _("unknown error")

    def __init__(self, message):
        self.message = message

    def __str__(self):
        return "%s: %s" % (self.type, self.message)


class ServiceUnavailable(HealthCheckException):
    type = _("unavailable")


class ServiceReturnedUnexpectedResult(HealthCheckException):
    type = _("unexpected result")


class BaseHealthCheckBackend(object):
    error = _("unknown error")

    def check_status(self):
        return None

    @cached_property
    def status(self):
        try:
            self.check_status()
        except Exception as e:
            logger.exception("Health check failed!")
            self.error = e
            return 0
        else:
            return 1

    def pretty_status(self):
        if self.status:
            return _('working')
        else:
            return force_text(self.error)

    @classmethod
    def identifier(cls):
        return cls.__name__
