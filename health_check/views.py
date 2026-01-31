import re
import typing
from collections import OrderedDict
from concurrent.futures import ThreadPoolExecutor
from functools import cached_property

from django.db import connections, transaction
from django.http import HttpResponse, JsonResponse
from django.utils import timezone
from django.utils.cache import patch_vary_headers
from django.utils.decorators import method_decorator
from django.utils.feedgenerator import Atom1Feed, Rss201rev2Feed
from django.utils.module_loading import import_string
from django.views.decorators.cache import never_cache
from django.views.generic import TemplateView

from health_check.base import HealthCheck
from health_check.exceptions import ServiceWarning


class MediaType:
    """
    Sortable object representing HTTP's accept header.

    See also: https://developer.mozilla.org/en-US/docs/Web/HTTP/Headers/Accept
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
        """Return single instance parsed from the given Accept-header string."""
        match = cls.pattern.search(value)
        if match is None:
            raise ValueError(f'"{value}" is not a valid media type')
        return cls(match.group("mime_type"), float(match.group("weight") or 1))

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


class HealthCheckView(TemplateView):
    """Perform health checks and return results in various formats."""

    template_name = "health_check/index.html"
    feed_author = "Django Health Check"

    use_threading: bool = True
    warnings_as_errors: bool = True
    checks: typing.Iterable[
        type[HealthCheck] | str | tuple[type[HealthCheck] | str, dict[str, typing.Any]]
    ] = (
        "health_check.checks.Cache",
        "health_check.checks.Database",
        "health_check.checks.Disk",
        "health_check.checks.DNS",
        "health_check.checks.Mail",
        "health_check.checks.Memory",
        "health_check.checks.Storage",
    )

    def run_check(self):
        errors = []

        def _run(check_instance):
            check_instance.run_check()
            try:
                return check_instance
            finally:
                if self.use_threading:
                    # DB connections are thread-local so we need to close them here
                    connections.close_all()

        def _collect_errors(check_instance):
            if check_instance.critical_service:
                if not self.warnings_as_errors:
                    errors.extend(
                        e
                        for e in check_instance.errors
                        if not isinstance(e, ServiceWarning)
                    )
                else:
                    errors.extend(check_instance.errors)

        if self.use_threading:
            with ThreadPoolExecutor(
                max_workers=len(self.results.values()) or 1
            ) as executor:
                for result in executor.map(_run, self.results.values()):
                    _collect_errors(result)
        else:
            for result in self.results.values():
                _run(result)
                _collect_errors(result)
        return errors

    @method_decorator(transaction.non_atomic_requests)
    def dispatch(self, request, *args, **kwargs):
        response = super().dispatch(request, *args, **kwargs)
        patch_vary_headers(response, ["Accept"])
        return response

    @method_decorator(never_cache)
    def get(self, request, *args, **kwargs):
        health_check_has_error = self.run_check()
        status_code = 500 if health_check_has_error else 200
        format_override = request.GET.get("format")

        if format_override == "json":
            return self.render_to_response_json(status_code)
        elif format_override == "atom":
            return self.render_to_response_atom(status_code)
        elif format_override == "rss":
            return self.render_to_response_rss(status_code)

        accept_header = request.headers.get("accept", "*/*")
        for media in MediaType.parse_header(accept_header):
            match media.mime_type:
                case "text/html" | "application/xhtml+xml" | "text/*" | "*/*":
                    context = self.get_context_data(**kwargs)
                    return self.render_to_response(context, status=status_code)
                case "application/json" | "application/*":
                    return self.render_to_response_json(status_code)
                case "application/atom+xml":
                    return self.render_to_response_atom(status_code)
                case "application/rss+xml":
                    return self.render_to_response_rss(status_code)
        return HttpResponse(
            "Not Acceptable: Supported content types: text/html, application/json, application/atom+xml, application/rss+xml",
            status=406,
            content_type="text/plain",
        )

    def get_context_data(self, **kwargs):
        return {
            **super().get_context_data(**kwargs),
            "plugins": self.results.values(),
            "errors": any(p.errors for p in self.results.values()),
        }

    def render_to_response_json(self, status):
        """Return JSON response with health check results."""
        return JsonResponse(
            {label: str(p.pretty_status()) for label, p in self.results.items()},
            status=status,
        )

    def render_to_response_atom(self, status):
        """Return Atom feed response with health check results."""
        return self._render_feed(Atom1Feed, status)

    def render_to_response_rss(self, status):
        """Return RSS 2.0 feed response with health check results."""
        return self._render_feed(Rss201rev2Feed, status)

    def _render_feed(self, feed_class, status):
        """Generate RSS or Atom feed with health check results."""
        feed = feed_class(
            title="Health Check Status",
            link=self.request.build_absolute_uri(),
            description="Current status of system health checks",
            feed_url=self.request.build_absolute_uri(),
        )

        for result in self.results.values():
            feed.add_item(
                title=str(result),
                link=self.request.build_absolute_uri(),
                description=f"{result.pretty_status()}\nResponse time: {result.time_taken:.3f}s",
                pubdate=timezone.now(),
                updateddate=timezone.now(),
                author_name=self.feed_author,
                categories=["error", "unhealthy"] if result.errors else ["healthy"],
            )

        response = HttpResponse(
            feed.writeString("utf-8"),
            content_type=feed.content_type,
            status=status,
        )
        return response

    def get_results(self):
        for check in self.checks:
            try:
                check, options = check
            except (ValueError, TypeError):
                options = {}
            if isinstance(check, str):
                check = import_string(check)
            check_instance = check(**options)
            yield repr(check_instance), check_instance

    @cached_property
    def results(self):
        return OrderedDict(self.get_results())
