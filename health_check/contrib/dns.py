"""DNS health check."""

import dataclasses
import logging

import dns.resolver

from health_check.base import HealthCheck
from health_check.exceptions import ServiceUnavailable

logger = logging.getLogger(__name__)


@dataclasses.dataclass
class DNS(HealthCheck):
    """
    Check DNS service by resolving a hostname.

    This health check verifies that DNS resolution is working properly,
    which is critical for outgoing API calls, database connections,
    and other network services that rely on DNS.

    Args:
        hostname: The hostname to resolve (default: 'example.com').
        nameservers: Optional list of nameserver IPs to use instead of system defaults.
        timeout: DNS query timeout in seconds (default: 5.0).

    """

    hostname: str = dataclasses.field(default="example.com", repr=False)
    nameservers: list[str] | None = dataclasses.field(
        default=None, repr=False
    )
    timeout: float = dataclasses.field(default=5.0, repr=False)

    def check_status(self):
        logger.debug("Attempting to resolve hostname: %s", self.hostname)

        try:
            resolver = dns.resolver.Resolver()

            # Configure custom nameservers if provided
            if self.nameservers:
                resolver.nameservers = self.nameservers
                logger.debug("Using custom nameservers: %s", self.nameservers)

            # Set timeout
            resolver.lifetime = self.timeout

            # Perform DNS resolution (A record by default)
            answers = resolver.resolve(self.hostname, "A")

            # Verify we got at least one answer
            if not answers:
                raise ServiceUnavailable(
                    f"DNS resolution returned no results for {self.hostname}"
                )

            logger.debug(
                "Successfully resolved %s to %s",
                self.hostname,
                [str(rdata) for rdata in answers],
            )

        except ServiceUnavailable:
            # Re-raise ServiceUnavailable exceptions as-is
            raise
        except dns.resolver.NXDOMAIN as e:
            raise ServiceUnavailable(
                f"DNS resolution failed: hostname {self.hostname} does not exist"
            ) from e
        except dns.resolver.NoAnswer as e:
            raise ServiceUnavailable(
                f"DNS resolution failed: no answer for {self.hostname}"
            ) from e
        except dns.resolver.Timeout as e:
            raise ServiceUnavailable(
                f"DNS resolution failed: timeout resolving {self.hostname}"
            ) from e
        except dns.resolver.NoNameservers as e:
            raise ServiceUnavailable(
                "DNS resolution failed: no nameservers available"
            ) from e
        except dns.exception.DNSException as e:
            raise ServiceUnavailable(f"DNS resolution failed: {e}") from e
        except BaseException as e:
            raise ServiceUnavailable("Unknown DNS error") from e
