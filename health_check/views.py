import re
import warnings
from functools import cached_property

from django.db import transaction
from django.http import HttpResponse, JsonResponse
from django.utils.decorators import method_decorator
from django.utils.module_loading import import_string
from django.views.decorators.cache import never_cache
from django.views.generic import TemplateView

from health_check.deprecation import deprecated
from health_check.mixins import CheckMixin


class MediaType:
    """
    Sortable object representing HTTP's accept header.

    .. seealso:: https://developer.mozilla.org/en-US/docs/Web/HTTP/Headers/Accept
    """

    pattern = re.compile(
        r"""
          ^
          (?P<mime_type>
            (\w+|\*)                      # Media type, or wildcard
            /
            ([\w\d\-+.]+|\*)              # subtype, or wildcard
          )
          (
            \s*;\s*                       # parameter separator with optional whitespace
            q=                            # q is expected to be the first parameter, by RFC2616
            (?P<weight>
              1([.]0{1,3})?               # 1 with up to three digits of precision
              |
              0([.]\d{1,3})?              # 0.000 to 0.999 with optional precision
            )
          )?
          (
            \s*;\s*                       # parameter separator with optional whitespace
            [-!#$%&'*+.^_`|~0-9a-zA-Z]+   # any token from legal characters
            =
            [-!#$%&'*+.^_`|~0-9a-zA-Z]+   # any value from legal characters
          )*
          $
        """,
        re.VERBOSE,
    )

    def __init__(self, mime_type, weight=1.0):
        self.mime_type = mime_type
        self.weight = float(weight)

    @classmethod
    def from_string(cls, value):
        """Return single instance parsed from given accept header string."""
        match = cls.pattern.search(value)
        if match is None:
            raise ValueError(f'"{value}" is not a valid media type')
        try:
            return cls(match.group("mime_type"), float(match.group("weight") or 1))
        except ValueError:
            return cls(value)

    @classmethod
    def parse_header(cls, value="*/*"):
        """Parse HTTP accept header and return instances sorted by weight."""
        yield from sorted(
            (cls.from_string(token.strip()) for token in value.split(",") if token.strip()),
            reverse=True,
        )

    def __str__(self):
        return f"{self.mime_type}; q={self.weight}"

    def __repr__(self):
        return f"{type(self).__name__}: {self.__str__()}"

    def __eq__(self, other):
        return self.weight == other.weight and self.mime_type == other.mime_type

    def __lt__(self, other):
        return self.weight.__lt__(other.weight)


@method_decorator(transaction.non_atomic_requests, name="dispatch")
class _MainView(CheckMixin, TemplateView):
    """Deprecated: Use HealthCheckView instead."""

    template_name = "health_check/index.html"

    @method_decorator(never_cache)
    def get(self, request, *args, **kwargs):
        subset = kwargs.get("subset")
        health_check_has_error = self.check(subset)
        status_code = 500 if health_check_has_error else 200
        format_override = request.GET.get("format")

        if format_override == "json":
            return self.render_to_response_json(self.filter_plugins(subset=subset), status_code)

        accept_header = request.headers.get("accept", "*/*")
        for media in MediaType.parse_header(accept_header):
            if media.mime_type in (
                "text/html",
                "application/xhtml+xml",
                "text/*",
                "*/*",
            ):
                context = self.get_context_data(**kwargs)
                return self.render_to_response(context, status=status_code)
            elif media.mime_type in ("application/json", "application/*"):
                return self.render_to_response_json(self.filter_plugins(subset=subset), status_code)
        return HttpResponse(
            "Not Acceptable: Supported content types: text/html, application/json",
            status=406,
            content_type="text/plain",
        )

    def get_context_data(self, **kwargs):
        subset = kwargs.get("subset")
        return {
            **super().get_context_data(**kwargs),
            "plugins": self.filter_plugins(subset=subset).values(),
            "errors": any(p.errors for p in self.filter_plugins(subset=subset).values()),
        }

    def render_to_response_json(self, plugins, status):
        return JsonResponse(
            {label: str(p.pretty_status()) for label, p in plugins.items()},
            status=status,
        )


@deprecated(
    "MainView is deprecated: use `HealthCheckView` instead (view-based API). Action: replace `MainView` usage with `HealthCheckView.as_view(checks=...)`. See migration guide: https://codingjoe.dev/django-health-check/migrate-to-v4/ (docs/migrate-to-v4.md)."
)
class MainView(_MainView):
    """Deprecated: Use HealthCheckView instead."""

    pass


class HealthCheckView(_MainView):
    """Perform health checks and return results in various formats."""

    checks: list[str | tuple[str, dict]] | None = None

    @classmethod
    def as_view(cls, **initkwargs):
        if "warnings_as_errors" in initkwargs:
            warnings.warn(
                "`warnings_as_errors` argument is deprecated and will be removed the next major version.",
                DeprecationWarning,
                stacklevel=2,
            )
        if "use_threading" in initkwargs:
            warnings.warn(
                "`use_threading` argument is deprecated and will be removed the next major version.",
                DeprecationWarning,
                stacklevel=2,
            )
        super().as_view(**initkwargs)

    def get_plugins(self):
        for check in self.checks or [
            "health_check.Cache",
            "health_check.Database",
            "health_check.Disk",
            "health_check.Mail",
            "health_check.Memory",
            "health_check.Storage",
        ]:
            try:
                check, options = check
            except ValueError:
                options = {}
            if isinstance(check, str):
                check = import_string(check)
            plugin_instance = check(**options)
            yield repr(plugin_instance), plugin_instance

    @cached_property
    def plugins(self):
        return dict(self.get_plugins())
