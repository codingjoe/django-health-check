import json
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
            url, headers={"Accept": "application/json"}
        )
        try:
            response = urllib.request.urlopen(request)  # noqa: S310
        except urllib.error.HTTPError as e:
            content = e.read()
        except urllib.error.URLError as e:
            self.stderr.write(
                f'"{url}" is not reachable: {e.reason}\nPlease check your ALLOWED_HOSTS setting.'
            )
            sys.exit(2)
        else:
            content = response.read()

        try:
            json_data = json.loads(content.decode("utf-8"))
        except json.JSONDecodeError as e:
            self.stderr.write(
                f"Health check endpoint '{endpoint}' did not return valid JSON: {e.msg}\n"
            )
            sys.exit(2)
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
