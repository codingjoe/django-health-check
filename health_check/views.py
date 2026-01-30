import re
import typing
from collections import OrderedDict
from concurrent.futures import ThreadPoolExecutor
from functools import cached_property

from django.db import connections, transaction
from django.http import HttpResponse, JsonResponse
from django.utils.decorators import method_decorator
from django.utils.module_loading import import_string
from django.views.decorators.cache import never_cache
from django.views.generic import TemplateView

from health_check import HealthCheck
from health_check.exceptions import HealthCheckException, ServiceWarning


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
            (
                cls.from_string(token.strip())
                for token in value.split(",")
                if token.strip()
            ),
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
class HealthCheckView(TemplateView):
    """Perform health checks and return results in various formats."""

    template_name = "health_check/index.html"

    _errors: list[HealthCheckException] | None = None
    _plugins = None

    use_threading: bool = True
    warnings_as_errors: bool = False
    checks: typing.Iterable[
        HealthCheck | str | tuple[HealthCheck | str, dict[str, typing.Any]]
    ] = (
        "health_check.checks.Cache",
        "health_check.checks.Database",
        "health_check.checks.Disk",
        "health_check.checks.Mail",
        "health_check.checks.Memory",
        "health_check.checks.Storage",
    )

    @property
    def errors(self):
        if not self._errors:
            self._errors = self.run_check()
        return self._errors

    def check(self):
        return self.run_check()

    def run_check(self):
        errors = []

        def _run(plugin):
            plugin.run_check()
            try:
                return plugin
            finally:
                if self.use_threading:
                    # DB connections are thread-local so we need to close them here
                    connections.close_all()

        def _collect_errors(plugin):
            if plugin.critical_service:
                if not self.warnings_as_errors:
                    errors.extend(
                        e for e in plugin.errors if not isinstance(e, ServiceWarning)
                    )
                else:
                    errors.extend(plugin.errors)

        plugins = dict(self.plugins)
        plugin_instances = plugins.values()

        if not self.use_threading:
            for plugin in plugin_instances:
                _run(plugin)
                _collect_errors(plugin)
        else:
            with ThreadPoolExecutor(max_workers=len(plugin_instances) or 1) as executor:
                for plugin in executor.map(_run, plugin_instances):
                    _collect_errors(plugin)
        return errors

    @method_decorator(never_cache)
    def get(self, request, *args, **kwargs):
        health_check_has_error = self.check()
        status_code = 500 if health_check_has_error else 200
        format_override = request.GET.get("format")

        if format_override == "json":
            return self.render_to_response_json(self.plugins, status_code)

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
                return self.render_to_response_json(self.plugins, status_code)
        return HttpResponse(
            "Not Acceptable: Supported content types: text/html, application/json",
            status=406,
            content_type="text/plain",
        )

    def get_context_data(self, **kwargs):
        return {
            **super().get_context_data(**kwargs),
            "plugins": self.plugins.values(),
            "errors": any(p.errors for p in self.plugins.values()),
        }

    def render_to_response_json(self, plugins, status):
        return JsonResponse(
            {label: str(p.pretty_status()) for label, p in plugins.items()},
            status=status,
        )

    def get_plugins(self):
        # If checks are explicitly set, use them
        if self.checks is not None:
            for check in self.checks:
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
        return OrderedDict(self.get_plugins())
