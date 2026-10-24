import datetime
import typing

from django.apps import AppConfig
from django.core import checks
from django.urls import URLPattern, URLResolver, get_resolver

from health_check.views import HealthCheckView

CHECK_ID = "health_check.W001"


def walk_url_patterns(
    url_patterns: typing.Iterable[URLPattern | URLResolver],
) -> typing.Iterator[URLPattern]:
    """Yield URL patterns, descending into included resolvers."""
    for pattern in url_patterns:
        match pattern:
            case URLResolver():
                yield from walk_url_patterns(pattern.url_patterns)
            case URLPattern():
                yield pattern


def needs_cache(allow_anonymous: bool, max_age: datetime.timedelta) -> bool:
    """Return whether a view admits anonymous requests without caching."""
    return allow_anonymous and max_age <= datetime.timedelta(0)


def get_pattern_warning(pattern: URLPattern) -> checks.Warning | None:
    """Return a warning for an anonymous view that disables caching."""
    callback = pattern.callback
    view_class = getattr(callback, "view_class", None)
    match view_class:
        case type() if issubclass(view_class, HealthCheckView):
            view_initkwargs = getattr(callback, "view_initkwargs", {})
            if needs_cache(
                view_initkwargs.get("allow_anonymous", view_class.allow_anonymous),
                view_initkwargs.get("max_age", view_class.max_age),
            ):
                return checks.Warning(
                    "Anonymous health check view disables caching.",
                    hint="Set max_age to a positive duration to cache successful responses.",
                    obj=callback,
                    id=CHECK_ID,
                )
    return None


@checks.register
def check_anonymous_view_cache(
    app_configs: typing.Iterable[AppConfig] | None = None,
    **kwargs: typing.Any,
) -> list[checks.Warning]:
    """Warn about anonymous health check views that disable caching."""
    return [
        warning
        for pattern in walk_url_patterns(get_resolver().url_patterns)
        if (warning := get_pattern_warning(pattern))
    ]
