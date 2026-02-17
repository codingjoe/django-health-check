try:
    from celery import Celery
except ImportError:
    from unittest.mock import Mock

    app = Mock()
else:
    app = Celery("testapp", broker="memory://")
    app.config_from_object("django.conf:settings", namespace="CELERY")
