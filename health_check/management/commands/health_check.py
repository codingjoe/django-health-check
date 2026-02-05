import os
import sys
import urllib.error
import urllib.request

from django.conf import settings
from django.core.management.base import BaseCommand
from django.urls import NoReverseMatch, reverse


class Command(BaseCommand):
    help = "Run health checks and exit 0 if everything went well."

    @property
    def default_forwarded_host(self):
        return (
            settings.ALLOWED_HOSTS[0].strip(".")
            if settings.ALLOWED_HOSTS and settings.ALLOWED_HOSTS[0] != "*"
            else None
        )

    @property
    def default_addrport(self):
        return ":".join([os.getenv("HOST", "127.0.0.1"), os.getenv("PORT", "8000")])

    def add_arguments(self, parser):
        parser.add_argument(
            "endpoint",
            type=str,
            help="URL-pattern name of health check endpoint to test",
        )
        parser.add_argument(
            "addrport",
            nargs="?",
            type=str,
            default=self.default_addrport,
            help=f"Optional port number, or ipaddr:port (default: {self.default_addrport})",
        )
        parser.add_argument(
            "--forwarded-host",
            type=str,
            default=self.default_forwarded_host,
            help=f"Value for X-Forwarded-Host header (default: {self.default_forwarded_host})",
        )
        parser.add_argument(
            "--forwarded-proto",
            type=str,
            choices=["http", "https"],
            default="https",
            help="Value for X-Forwarded-Proto header (default: https)",
        )
        parser.add_argument(
            "--timeout",
            type=int,
            default=5,
            help="Timeout in seconds for the health check request (default: 5 seconds)",
        )

    def handle(self, *args, **options):
        endpoint = options.get("endpoint")
        try:
            path = reverse(endpoint)
        except NoReverseMatch as e:
            self.stderr.write(
                f"Could not resolve endpoint {endpoint!r}: {e}\n"
                "Please provide a valid URL pattern name for the health check endpoint."
            )
            sys.exit(2)
        addrport = options.get("addrport")
        # Determine the protocol to use when connecting to the local server:
        # - Connect via HTTPS only if SSL redirect is enabled AND forwarded headers are not used
        #   (meaning the app truly requires HTTPS connections)
        # - Otherwise, connect via HTTP (typical for containerized apps where the app listens
        #   on HTTP and X-Forwarded-Proto header indicates the original protocol to Django)
        proto = (
            "https"
            if settings.SECURE_SSL_REDIRECT and not settings.USE_X_FORWARDED_HOST
            else "http"
        )
        url = f"{proto}://{addrport}{path}"

        headers = {"Accept": "text/plain"}

        # Add X-Forwarded-Host header
        if forwarded_host := options.get("forwarded_host"):
            headers["X-Forwarded-Host"] = forwarded_host

        # Add X-Forwarded-Proto header
        if forwarded_proto := options.get("forwarded_proto"):
            headers["X-Forwarded-Proto"] = forwarded_proto

        if options.get("verbosity", 1) >= 2:
            self.stdout.write(
                f"Checking health endpoint at {url!r} with headers: {headers}"
            )

        request = urllib.request.Request(url, headers=headers)  # noqa: S310
        try:
            response = urllib.request.urlopen(request, timeout=options["timeout"])  # noqa: S310
        except urllib.error.HTTPError as e:
            match e.code:
                case 500:  # Health check failed
                    self.stdout.write(e.read().decode("utf-8"))
                    sys.exit(1)
                case 400:
                    self.stderr.write(
                        f"{url!r} is not reachable: {e.reason}\nPlease check your ALLOWED_HOSTS setting or use the --forwarded-host option."
                    )
                    sys.exit(2)
                case _:
                    self.stderr.write(
                        "Unexpected HTTP error "
                        f"when trying to reach {url!r}: {e}\n"
                        f"You may have selected an invalid endpoint {endpoint!r}"
                        f" or another application is running on {addrport!r}."
                    )
                    sys.exit(2)
        except urllib.error.URLError as e:
            self.stderr.write(
                f"{url!r} is not reachable: {e.reason}\nPlease check your server is running and reachable."
            )
            sys.exit(2)
        except TimeoutError as e:
            self.stderr.write(f"Timeout when trying to reach {url!r}: {e}")
            sys.exit(2)
        else:
            self.stdout.write(response.read().decode("utf-8"))
