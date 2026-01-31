"""Tests for DNS health check."""

from unittest import mock

import pytest

pytest.importorskip("dns")

import dns.exception
import dns.resolver

from health_check.contrib.dns import DNS as DNSHealthCheck
from health_check.exceptions import ServiceUnavailable


class TestDNS:
    """Test DNS health check."""

    def test_check_status__success(self):
        """Resolve hostname successfully when DNS is working."""
        with mock.patch("health_check.contrib.dns.dns.resolver.Resolver") as mock_resolver_class:
            mock_resolver = mock.MagicMock()
            mock_resolver_class.return_value = mock_resolver
            mock_answers = mock.MagicMock()
            mock_answers.__bool__.return_value = True
            mock_resolver.resolve.return_value = mock_answers

            check = DNSHealthCheck(hostname="example.com")
            check.check_status()
            assert check.errors == []

            # Verify resolver was configured correctly
            mock_resolver.resolve.assert_called_once_with("example.com", "A")

    def test_check_status__success_with_custom_nameservers(self):
        """Resolve hostname successfully with custom nameservers."""
        with mock.patch("health_check.contrib.dns.dns.resolver.Resolver") as mock_resolver_class:
            mock_resolver = mock.MagicMock()
            mock_resolver_class.return_value = mock_resolver
            mock_answers = mock.MagicMock()
            mock_answers.__bool__.return_value = True
            mock_resolver.resolve.return_value = mock_answers

            check = DNSHealthCheck(
                hostname="example.com",
                nameservers=["8.8.8.8", "8.8.4.4"]
            )
            check.check_status()
            assert check.errors == []

            # Verify custom nameservers were set
            assert mock_resolver.nameservers == ["8.8.8.8", "8.8.4.4"]

    def test_check_status__success_with_custom_timeout(self):
        """Resolve hostname successfully with custom timeout."""
        with mock.patch("health_check.contrib.dns.dns.resolver.Resolver") as mock_resolver_class:
            mock_resolver = mock.MagicMock()
            mock_resolver_class.return_value = mock_resolver
            mock_answers = mock.MagicMock()
            mock_answers.__bool__.return_value = True
            mock_resolver.resolve.return_value = mock_answers

            check = DNSHealthCheck(hostname="example.com", timeout=10.0)
            check.check_status()
            assert check.errors == []

            # Verify timeout was set
            assert mock_resolver.lifetime == 10.0

    def test_check_status__nxdomain(self):
        """Raise ServiceUnavailable when hostname does not exist."""
        with mock.patch("health_check.contrib.dns.dns.resolver.Resolver") as mock_resolver_class:
            mock_resolver = mock.MagicMock()
            mock_resolver_class.return_value = mock_resolver
            mock_resolver.resolve.side_effect = dns.resolver.NXDOMAIN("not found")

            check = DNSHealthCheck(hostname="nonexistent.example.com")
            with pytest.raises(ServiceUnavailable) as exc_info:
                check.check_status()
            assert "does not exist" in str(exc_info.value)

    def test_check_status__no_answer(self):
        """Raise ServiceUnavailable when DNS returns no answer."""
        with mock.patch("health_check.contrib.dns.dns.resolver.Resolver") as mock_resolver_class:
            mock_resolver = mock.MagicMock()
            mock_resolver_class.return_value = mock_resolver
            mock_resolver.resolve.side_effect = dns.resolver.NoAnswer("no answer")

            check = DNSHealthCheck(hostname="example.com")
            with pytest.raises(ServiceUnavailable) as exc_info:
                check.check_status()
            assert "no answer" in str(exc_info.value)

    def test_check_status__timeout(self):
        """Raise ServiceUnavailable when DNS query times out."""
        with mock.patch("health_check.contrib.dns.dns.resolver.Resolver") as mock_resolver_class:
            mock_resolver = mock.MagicMock()
            mock_resolver_class.return_value = mock_resolver
            mock_resolver.resolve.side_effect = dns.resolver.Timeout("timeout")

            check = DNSHealthCheck(hostname="example.com")
            with pytest.raises(ServiceUnavailable) as exc_info:
                check.check_status()
            assert "timeout" in str(exc_info.value)

    def test_check_status__no_nameservers(self):
        """Raise ServiceUnavailable when no nameservers are available."""
        with mock.patch("health_check.contrib.dns.dns.resolver.Resolver") as mock_resolver_class:
            mock_resolver = mock.MagicMock()
            mock_resolver_class.return_value = mock_resolver
            mock_resolver.resolve.side_effect = dns.resolver.NoNameservers(
                "no nameservers"
            )

            check = DNSHealthCheck(hostname="example.com")
            with pytest.raises(ServiceUnavailable) as exc_info:
                check.check_status()
            assert "no nameservers available" in str(exc_info.value)

    def test_check_status__dns_exception(self):
        """Raise ServiceUnavailable for general DNS exceptions."""
        with mock.patch("health_check.contrib.dns.dns.resolver.Resolver") as mock_resolver_class:
            mock_resolver = mock.MagicMock()
            mock_resolver_class.return_value = mock_resolver
            mock_resolver.resolve.side_effect = dns.exception.DNSException(
                "general DNS error"
            )

            check = DNSHealthCheck(hostname="example.com")
            with pytest.raises(ServiceUnavailable) as exc_info:
                check.check_status()
            assert "DNS resolution failed" in str(exc_info.value)

    def test_check_status__unknown_error(self):
        """Raise ServiceUnavailable for unexpected exceptions."""
        with mock.patch("health_check.contrib.dns.dns.resolver.Resolver") as mock_resolver_class:
            mock_resolver = mock.MagicMock()
            mock_resolver_class.return_value = mock_resolver
            mock_resolver.resolve.side_effect = RuntimeError("unexpected")

            check = DNSHealthCheck(hostname="example.com")
            with pytest.raises(ServiceUnavailable) as exc_info:
                check.check_status()
            assert "Unknown DNS error" in str(exc_info.value)

    def test_check_status__empty_answer(self):
        """Raise ServiceUnavailable when DNS returns empty answer list."""
        with mock.patch("health_check.contrib.dns.dns.resolver.Resolver") as mock_resolver_class:
            mock_resolver = mock.MagicMock()
            mock_resolver_class.return_value = mock_resolver
            # Create a mock that evaluates to False in boolean context
            mock_answers = mock.MagicMock()
            mock_answers.__bool__.return_value = False
            mock_resolver.resolve.return_value = mock_answers

            check = DNSHealthCheck(hostname="example.com")
            with pytest.raises(ServiceUnavailable) as exc_info:
                check.check_status()
            assert "no results" in str(exc_info.value)

    @pytest.mark.integration
    def test_check_status__real_dns(self):
        """Resolve real hostname using actual DNS."""
        # Use a well-known, stable hostname
        check = DNSHealthCheck(hostname="example.com")
        check.check_status()
        assert check.errors == []

    @pytest.mark.integration
    def test_check_status__real_dns_with_google_nameservers(self):
        """Resolve hostname using Google's public DNS servers."""
        try:
            check = DNSHealthCheck(
                hostname="example.com",
                nameservers=["8.8.8.8", "8.8.4.4"]
            )
            check.check_status()
            assert check.errors == []
        except ServiceUnavailable as e:
            # Skip if network access to external DNS servers is restricted
            if "Operation not permitted" in str(e.__cause__):
                pytest.skip("External DNS server access restricted in test environment")
            raise
