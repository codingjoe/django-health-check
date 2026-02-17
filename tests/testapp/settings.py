import contextlib
import os.path
import uuid

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DEBUG = True

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
    },
    "other": {  # 2nd database connection to ensure proper connection handling
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
    },
}

INSTALLED_APPS = [
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.staticfiles",
    "health_check",
    "tests",
]


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

CELERY_TASK_QUEUES = []
CELERY_TASK_DEFAULT_QUEUE = "default"

with contextlib.suppress(ImportError):
    import kombu

    CELERY_TASK_QUEUES += [
        kombu.Queue("default"),
        kombu.Queue("queue2"),
    ]

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost/1")
BROKER_URL = os.getenv("BROKER_URL", "amqp://guest:guest@localhost:5672/")
