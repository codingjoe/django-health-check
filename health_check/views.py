import asyncio
import contextlib
import datetime
import hashlib
import hmac
import logging
import re
import timeit
import typing
import uuid
from concurrent.futures import Executor

from django.db import transaction
from django.http import HttpRequest, HttpResponse, HttpResponseBase, JsonResponse
from django.utils.cache import (
    add_never_cache_headers,
    get_conditional_response,
    patch_vary_headers,
)
from django.utils.decorators import method_decorator
from django.utils.feedgenerator import Atom1Feed, Rss201rev2Feed
from django.utils.http import quote_etag
from django.utils.module_loading import import_string
from django.views.generic import TemplateView

from health_check.base import HealthCheck, HealthCheckResult
from health_check.exceptions import HealthCheckError

logger = logging.getLogger("health_check")


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
            msg = f'"{value}" is not a valid media type'
            raise ValueError(msg)
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
    """
    Perform health checks and return results in various formats.

    Set `cache_timeout` to allow shared caches to reuse responses.
    Set `authentication_token` to authenticate requests and bypass the cache.
    """

    template_name = "health_check/index.html"
    feed_author = "Django Health Check"

    cache_timeout: datetime.timedelta | None = None
    """Time a shared cache may reuse a response. Caching is disabled by default."""

    authentication_token: str | None = None
    """Secret bearer token that authenticates a request and bypasses the cache."""

    allow_anonymous: bool = True
    """Allow requests without an authentication token when one is configured."""

    checks: typing.Iterable[
        type[HealthCheck] | str | tuple[type[HealthCheck] | str, dict[str, typing.Any]]
    ] = (
        "health_check.checks.Cache",
        "health_check.checks.Database",
        "health_check.checks.DNS",
        "health_check.checks.Mail",
        "health_check.checks.Storage",
    )

    @method_decorator(transaction.non_atomic_requests)
    async def dispatch(self, request, *args, **kwargs):
        if not self.is_authorized(request):
            return self.render_forbidden_response(request)
        response = await super().dispatch(request, *args, **kwargs)
        patch_vary_headers(response, ["Accept"])
        if self.authentication_token:
            patch_vary_headers(response, ["Authorization"])
        if not self.cache_timeout or request.method not in ("GET", "HEAD"):
            add_never_cache_headers(response)
            return response
        return self.patch_cache_headers(request, response)

    def render_forbidden_response(self, request: HttpRequest) -> HttpResponse:
        """Return 403 without running health checks."""
        response = HttpResponse(
            "" if request.method == "HEAD" else "Authentication failed",
            status=403,
            content_type="text/plain; charset=utf-8",
        )
        patch_vary_headers(response, ["Accept", "Authorization"])
        add_never_cache_headers(response)
        return response

    def patch_cache_headers(
        self, request: HttpRequest, response: HttpResponseBase
    ) -> HttpResponseBase:
        """Set shared cache headers and answer matching entity tags with 304."""
        is_refresh = self.should_bypass_cache(request)
        etag = self.calculate_etag(response, uuid.uuid4().bytes if is_refresh else b"")
        response["ETag"] = quote_etag(f'W/"{etag}"')
        if is_refresh:
            response["Cache-Control"] = "no-store"
            return response
        max_age_secs = int(self.cache_timeout.total_seconds())
        response["Cache-Control"] = f"public, max-age={max_age_secs}"
        return get_conditional_response(
            request, etag=response["ETag"], response=response
        )

    def calculate_etag(self, response: HttpResponseBase, salt: bytes = b"") -> str:
        """Return an entity tag for the current check results."""
        digest = hashlib.sha256(salt)
        digest.update(str(response.status_code).encode())
        digest.update(response.get("Content-Type", "").encode())
        digest.update(
            b"".join(
                repr(result.check).encode() + b"\0" + str(result.error).encode() + b"\0"
                for result in self.results
            )
        )
        return digest.hexdigest()

    def is_authorized(self, request: HttpRequest) -> bool:
        """Return whether the request may access the view."""
        if self.authentication_token is None or self.has_valid_authentication_token(
            request
        ):
            return True
        return self.allow_anonymous and "Authorization" not in request.headers

    def should_bypass_cache(self, request: HttpRequest) -> bool:
        """Return whether the request must run fresh checks and skip shared caches."""
        return self.has_valid_authentication_token(request)

    def has_valid_authentication_token(self, request: HttpRequest) -> bool:
        """Return whether the request carries the configured bearer token."""
        if not self.authentication_token:
            return False
        scheme, _, token = request.headers.get("Authorization", "").partition(" ")
        return scheme.lower() == "bearer" and hmac.compare_digest(
            token.encode(), self.authentication_token.encode()
        )

    async def get(self, request, *args, **kwargs):
        with self.get_executor() as executor:
            self.results = await asyncio.gather(
                *(self.get_check_result(check, executor) for check in self.get_checks())
            )
        has_errors = any(result.error for result in self.results)
        status_code = 500 if has_errors else 200

        response = self.render_for_format(request.GET.get("format"), status_code)
        if response is None:
            response = self.render_for_accept_header(
                request.headers.get("accept", "*/*"), status_code, **kwargs
            )
        return response

    def render_for_format(self, format_override, status_code):
        """Return the response for an explicit format override, if supported."""
        match format_override:
            case "json":
                return self.render_to_response_json(status_code)
            case "text":
                return self.render_to_response_text(status_code)
            case "atom":
                return self.render_to_response_atom()
            case "rss":
                return self.render_to_response_rss()
            case "openmetrics":
                return self.render_to_response_openmetrics()
        return None

    def render_for_accept_header(self, accept_header, status_code, **kwargs):
        """Return the response matching the Accept header, defaulting to 406."""
        for media in MediaType.parse_header(accept_header):
            match media.mime_type:
                case "text/plain":
                    return self.render_to_response_text(status_code)
                case "text/html" | "application/xhtml+xml" | "text/*" | "*/*":
                    context = self.get_context_data(**kwargs)
                    return self.render_to_response(context, status=status_code)
                case "application/json" | "application/*":
                    return self.render_to_response_json(status_code)
                case "application/atom+xml":
                    return self.render_to_response_atom()
                case "application/rss+xml":
                    return self.render_to_response_rss()
                case "application/openmetrics-text":
                    return self.render_to_response_openmetrics()
        return HttpResponse(
            "Not Acceptable: Supported content types: text/plain, text/html, application/json, application/atom+xml, application/rss+xml, application/openmetrics-text",
            status=406,
            content_type="text/plain",
        )

    @staticmethod
    async def get_check_result(
        check: HealthCheck, executor: Executor | None
    ) -> HealthCheckResult:
        """Return one check's outcome, reporting an escaping exception as a failure."""
        start = timeit.default_timer()
        try:
            return await check.get_result(executor)
        except HealthCheckError as exception:
            logger.warning("Health check %r failed", check, exc_info=exception)
            error = exception
        except Exception:
            logger.exception("Unexpected exception during health check")
            error = HealthCheckError("unknown error")
        return HealthCheckResult(
            check=check,
            error=error,
            time_taken=timeit.default_timer() - start,
        )

    def get_context_data(self, **kwargs):
        return {
            **super().get_context_data(**kwargs),
            "results": self.results,
            "errors": any(result.error for result in self.results),
        }

    def get_executor(self) -> contextlib.AbstractContextManager[Executor | None]:
        """
        Return a context manager providing an executor for synchronous checks.

        Return a context manager that yields ``None`` to use the event loop's
        default executor.

        Example:
            def get_executor(self):
                return ThreadPoolExecutor(max_workers=5)

        """
        return contextlib.nullcontext(None)

    def render_to_response_json(self, status):
        """Return JSON response with health check results."""
        return JsonResponse(
            {
                repr(result.check): "OK" if not result.error else str(result.error)
                for result in self.results
            },
            status=status,
        )

    def render_to_response_text(self, status):
        """Return a plain text response with health check results."""
        lines = (
            f"{repr(result.check)}: {'OK' if not result.error else str(result.error)}"
            for result in self.results
        )
        return HttpResponse(
            "\n".join(lines) + "\n",
            content_type="text/plain; charset=utf-8",
            status=status,
        )

    def render_to_response_atom(self):
        """Return Atom feed response with health check results."""
        return self._render_feed(Atom1Feed)

    def render_to_response_rss(self):
        """Return RSS 2.0 feed response with health check results."""
        return self._render_feed(Rss201rev2Feed)

    @staticmethod
    def abnf_escape(value):
        r"""
        Escape ABNF OpenMetic labels according to RFC 5234 and RFC7405.

        Escapes backslashes, double quotes, and newlines as required by the spec:
        - Backslash (\) -> \\
        - Double quote (") -> \"
        - Line feed (\n) -> \n
        """
        return value.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")

    @staticmethod
    def abnf_dumps(o: dict[str, str]):
        """Return ABNF OpenMetic labels as a string suitable for use in a metric name."""
        return ",".join(
            f'{key}="{HealthCheckView.abnf_escape(value)}"' for key, value in o.items()
        )

    def render_to_response_openmetrics(self):
        """Return OpenMetrics response with health check results."""
        lines = [
            "# HELP django_health_check_status Health check status (1 = healthy, 0 = unhealthy)",
            "# TYPE django_health_check_status gauge",
        ]
        has_errors: bool = False

        # Add status metrics for each check
        for result in self.results:
            has_errors |= bool(result.error)
            lines.append(
                f"django_health_check_status{{{self.abnf_dumps(result.check.labels)}}} {not result.error:d}"
            )

        # Add response time metrics
        lines += [
            "# HELP django_health_check_response_time_seconds Health check response time in seconds",
            "# TYPE django_health_check_response_time_seconds gauge",
        ]

        for result in self.results:
            lines.append(
                f"django_health_check_response_time_seconds{{{self.abnf_dumps(result.check.labels)}}} {result.time_taken:.6f}"
            )

        # Add overall health status
        lines += [
            "# HELP django_health_check_overall_status Overall health check status (1 = all healthy, 0 = at least one unhealthy)",
            "# TYPE django_health_check_overall_status gauge",
            f"django_health_check_overall_status {not has_errors:d}",
            "# EOF",
        ]

        return HttpResponse(
            "\n".join(lines) + "\n",
            content_type="application/openmetrics-text; version=1.0.0; charset=utf-8",
            status=200,  # Prometheus expects 200 even if checks fail
        )

    def _render_feed(self, feed_class):
        """Generate RSS or Atom feed with health check results."""
        feed = feed_class(
            title="Health Check Status",
            link=self.request.build_absolute_uri(self.request.path),
            description="Current status of system health checks",
            feed_url=self.request.build_absolute_uri(),
        )

        for result in self.results:
            published_at = (
                result.error.timestamp
                if result.error
                else datetime.datetime(1970, 1, 1, tzinfo=datetime.UTC)
            )
            feed.add_item(
                title=repr(result.check),
                link=self.request.build_absolute_uri(self.request.path),
                description=str(result.error) if result.error else "OK",
                pubdate=published_at,
                updateddate=published_at,
                author_name=self.feed_author,
                categories=["error", "unhealthy"] if result.error else ["healthy"],
            )

        return HttpResponse(
            feed.writeString("utf-8"),
            content_type=feed.content_type,
            status=200,  # Feed readers expect 200 even if checks fail
        )

    def get_checks(
        self,
    ) -> typing.Generator[HealthCheck]:
        """Yield instantiated health check callables."""
        for check in self.checks:
            try:
                check, options = check
            except ValueError, TypeError:
                options = {}
            if isinstance(check, str):
                check = import_string(check)
            yield check(**options)
