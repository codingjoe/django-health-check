import datetime

from django.http import HttpResponse
from django.urls import include, path
from django.views.generic import TemplateView

from health_check.views import HealthCheckView


class AnonymousHealthCheckView(HealthCheckView):
    """Health check view that admits anonymous requests."""

    allow_anonymous = True


class CachedAnonymousHealthCheckView(HealthCheckView):
    """Health check view that admits anonymous requests and caches results."""

    allow_anonymous = True
    max_age = datetime.timedelta(seconds=30)


class AuthenticatedHealthCheckView(HealthCheckView):
    """Health check view that requires authentication."""


def plain_view(request):
    """Return a plain response."""
    return HttpResponse("OK")


inner_urlpatterns = [
    path(
        "anonymous/",
        AnonymousHealthCheckView.as_view(),
        name="nested_anonymous",
    ),
    path(
        "cached/",
        AnonymousHealthCheckView.as_view(max_age=datetime.timedelta(seconds=30)),
        name="nested_cached",
    ),
]

nested_urlpatterns = [
    path("inner/", include(inner_urlpatterns)),
]

urlpatterns = [
    path("anonymous/", AnonymousHealthCheckView.as_view(), name="anonymous"),
    path(
        "anonymous-cached/",
        AnonymousHealthCheckView.as_view(max_age=datetime.timedelta(seconds=30)),
        name="anonymous_cached",
    ),
    path(
        "authenticated/",
        AuthenticatedHealthCheckView.as_view(),
        name="authenticated",
    ),
    path("plain/", plain_view, name="plain"),
    path("template/", TemplateView.as_view(), name="template"),
    path("nested/", include(nested_urlpatterns)),
    path(
        "initkwargs-anonymous/",
        AuthenticatedHealthCheckView.as_view(allow_anonymous=True),
        name="initkwargs_anonymous",
    ),
    path(
        "initkwargs-zero-max-age/",
        CachedAnonymousHealthCheckView.as_view(max_age=datetime.timedelta(0)),
        name="initkwargs_zero_max_age",
    ),
    path(
        "initkwargs-authentication-required/",
        CachedAnonymousHealthCheckView.as_view(allow_anonymous=False),
        name="initkwargs_authentication_required",
    ),
]
