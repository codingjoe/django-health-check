import sys
import urllib.error
import urllib.request

from django.core.management.base import BaseCommand
from django.urls import reverse


class Command(BaseCommand):
    help = "Run health checks and exit 0 if everything went well."

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
            help="Optional port number, or ipaddr:port (default: localhost:8000)",
            default="localhost:8000",
        )

    def handle(self, *args, **options):
        endpoint = options.get("endpoint")
        path = reverse(endpoint)
        host, sep, port = options.get("addrport").partition(":")
        url = f"http://{host}:{port}{path}" if sep else f"http://{host}{path}"
        request = urllib.request.Request(  # noqa: S310
            url, headers={"Accept": "text/plain"}
        )
        try:
            response = urllib.request.urlopen(request)  # noqa: S310
        except urllib.error.HTTPError as e:
            # 500 status codes will raise HTTPError
            self.stdout.write(e.read().decode("utf-8"))
            sys.exit(1)
        except urllib.error.URLError as e:
            self.stderr.write(
                f'"{url}" is not reachable: {e.reason}\nPlease check your ALLOWED_HOSTS setting.'
            )
            sys.exit(2)
        else:
            self.stdout.write(response.read().decode("utf-8"))
