import http
import sys
import urllib.error
import urllib.request

from django import test, urls
from django.core import management


class Command(management.BaseCommand):
    help = "Run health checks and exit 0 if everything went well."

    def add_arguments(self, parser: management.base.CommandParser):
        parser.add_argument(
            "endpoint",
            type=str,
            help="URL-pattern name of health check endpoint to test",
        )
        parser.add_argument(
            "--make-http-request-directly",
            action="store_true",
            help="Make a direct http request to server",
        )
        parser.add_argument(
            "addrport",
            nargs="?",
            type=str,
            help="Optional port number, or ipaddr:port (default: localhost:8000)",
            default="localhost:8000",
        )

    def handle(
        self,
        *args,
        **options,
    ) -> None:
        endpoint = options.get("endpoint")
        if options.get("make_http_request_directly"):
            self.call_endpoint_via_http(endpoint, options.get("addrport"))
        else:
            self.call_endpoint_directly(endpoint)

    def call_endpoint_via_http(
        self,
        endpoint: str,
        addrport: str,
    ) -> None:
        path = urls.reverse(endpoint)
        host, sep, port = addrport.partition(":")
        url = f"http://{host}:{port}{path}" if sep else f"http://{host}{path}"
        request = urllib.request.Request(  # noqa: S310
            url,
            headers={
                "Accept": "text/plain",
            },
        )
        try:
            response = urllib.request.urlopen(request)  # noqa: S310
        except urllib.error.HTTPError as error:
            self.stdout.write(
                self.style.ERROR(
                    error.read().decode("utf-8"),
                ),
            )
            sys.exit(1)
        except urllib.error.URLError as error:
            self.stderr.write(
                self.style.ERROR(
                    f'"{url}" is not reachable: {error.reason}'
                    "\nPlease check your ALLOWED_HOSTS setting.",
                ),
            )
            sys.exit(2)
        else:
            self.stdout.write(
                self.style.SUCCESS(
                    response.read().decode("utf-8"),
                ),
            )

    def call_endpoint_directly(
        self,
        endpoint: str,
    ) -> None:
        path = urls.reverse(endpoint)
        resolved = urls.resolve(path)
        response = resolved.func(
            test.RequestFactory().get(
                path,
                headers={
                    "Accept": "text/plain",
                },
            ),
            *resolved.args,
            **resolved.kwargs,
        )
        if response.status_code == http.HTTPStatus.OK:
            self.stdout.write(
                self.style.SUCCESS(
                    response.content.decode("utf-8"),
                ),
            )
        else:
            for check_result in response.content.decode("utf-8").splitlines():
                if check_result.endswith("OK"):
                    self.stdout.write(self.style.SUCCESS(check_result))
                else:
                    self.stdout.write(self.style.ERROR(check_result))
            sys.exit(1)
