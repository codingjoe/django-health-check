import json
import sys
import urllib.error
import urllib.request
import warnings

from django.core.management.base import BaseCommand
from django.http import Http404
from django.urls import reverse

from health_check.mixins import CheckMixin


class Command(CheckMixin, BaseCommand):
    help = "Run health checks and exit 0 if everything went well."

    def add_arguments(self, parser):
        parser.add_argument(
            "endpoint",
            nargs="?",
            type=str,
            help="Either URL or URL-pattern name of health check endpoint to test",
        )
        parser.add_argument(
            "addrport",
            nargs="?",
            type=str,
            help="Optional port number, or ipaddr:port (default: localhost:8000)",
            default="localhost:8000",
        )
        parser.add_argument("-s", "--subset", type=str, nargs=1, help="deprecated")

    def handle(self, *args, **options):
        if endpoint := options.get("endpoint"):
            path = reverse(endpoint)
            host, sep, port = options.get("addrport").partition(":")
            url = f"http://{host}:{port}{path}" if sep else f"http://{host}{path}"
            request = urllib.request.Request(  # noqa: S310
                url, headers={"Accept": "application/json"}
            )
            try:
                response = urllib.request.urlopen(request)  # noqa: S310
            except urllib.error.HTTPError as e:
                content = e.read()
            except urllib.error.URLError as e:
                self.stderr.write(f'"{url}" is not reachable: {e.reason}\nPlease check your ALLOWED_HOSTS setting.')
                sys.exit(1)
            else:
                content = response.read()

            try:
                json_data = json.loads(content.decode("utf-8"))
            except json.JSONDecodeError as e:
                self.stderr.write(f"Health check endpoint '{endpoint}' did not return valid JSON: {e.msg}\n")
                sys.exit(1)
            else:
                errors = False
                for label, msg in json_data.items():
                    if msg == "OK":
                        style_func = self.style.SUCCESS
                    else:
                        style_func = self.style.ERROR
                        errors = True
                    self.stdout.write(f"{label:<50} {style_func(msg)}\n")
                if errors:
                    sys.exit(1)

        else:
            warnings.warn(
                "Explicit endpoint argument will be required in the next major version: pass the endpoint name to the command. Action: call `django-admin health_check <endpoint>` or update scripts to pass the endpoint. See migration guide: https://codingjoe.dev/django-health-check/migrate-to-v4/ (docs/migrate-to-v4.md).",
                UserWarning,
            )

            if subset := options.get("subset", []):
                warnings.warn(
                    "`--subset` option is deprecated: use the endpoint argument instead. Action: call `django-admin health_check <endpoint>` or use `HealthCheckView` with subset-configured checks. See migration guide: https://codingjoe.dev/django-health-check/migrate-to-v4/ (docs/migrate-to-v4.md).",
                    DeprecationWarning,
                )
            # perform all checks
            subset = subset[0] if subset else None
            try:
                errors = self.check(subset=subset)
            except Http404 as e:
                self.stdout.write(str(e))
                sys.exit(1)

            for label, plugin in self.filter_plugins(subset=subset).items():
                style_func = self.style.SUCCESS if not plugin.errors else self.style.ERROR
                self.stdout.write(f"{label:<24} ... {style_func(plugin.pretty_status())}\n")

            if errors:
                sys.exit(1)
