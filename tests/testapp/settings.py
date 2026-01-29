import os.path
import uuid

try:
    from kombu import Queue
except Exception:  # pragma: no cover - optional dependency
    Queue = None

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DEBUG = True

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
    },
    "other": {  # 2nd database conneciton to ensure proper connection handling
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":backup",
    },
}

INSTALLED_APPS = (
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.staticfiles",
    "health_check",
    "health_check.cache",
    "health_check.db",
    "health_check.storage",
    "health_check.contrib.celery",
    "health_check.contrib.migrations",
    "health_check.contrib.celery_ping",
    "health_check.contrib.s3boto_storage",
    "health_check.contrib.db_heartbeat",
    "health_check.contrib.mail",
    "tests",
)

MIDDLEWARE_CLASSES = (
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
)

STATIC_URL = "/static/"

MEDIA_ROOT = os.path.join(BASE_DIR, "media")

SITE_ID = 1
ROOT_URLCONF = "tests.testapp.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "APP_DIRS": True,
        "OPTIONS": {
            "debug": True,
        },
    },
]

SECRET_KEY = uuid.uuid4().hex

USE_TZ = True

CELERY_QUEUES = []
if Queue is not None:
    CELERY_QUEUES += [
        Queue("default"),
        Queue("queue2"),
    ]


REDIS_URL = os.getenv("REDIS_URL", "redis://localhost/1")
BROKER_URL = os.getenv("BROKER_URL", "amqp://guest:guest@localhost:5672/")
