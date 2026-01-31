"""Tests for health check RSS/Atom feed."""

import dataclasses
from xml.etree import ElementTree

import pytest
from django.test import RequestFactory
from django.urls import reverse

from health_check.base import HealthCheck
from health_check.exceptions import HealthCheckException
from health_check.feeds import HealthCheckFeed, HealthCheckRSSFeed


class TestHealthCheckFeed:
    """Tests for the HealthCheckFeed class (Atom)."""

    def test_feed_attributes(self):
        """Verify feed has required attributes."""
        feed = HealthCheckFeed()
        assert feed.title == "Health Check Status"
        assert feed.description == "Current status of system health checks"
        assert feed.link() == reverse("health_check")

    def test_feed_items(self):
        """Feed returns health check plugins as items."""
        feed = HealthCheckFeed()
        items = feed.items()
        assert isinstance(items, list)
        # Should have default checks
        assert len(items) > 0

    def test_item_title(self):
        """Item title is the string representation of the check."""

        @dataclasses.dataclass
        class TestCheck(HealthCheck):
            def check_status(self):
                pass

        feed = HealthCheckFeed()
        check = TestCheck()
        title = feed.item_title(check)
        assert title == str(check)

    def test_item_description_success(self):
        """Item description includes status and timing."""

        @dataclasses.dataclass
        class TestCheck(HealthCheck):
            def check_status(self):
                pass

        feed = HealthCheckFeed()
        check = TestCheck()
        check.run_check()
        description = feed.item_description(check)
        assert "OK" in description
        assert "Response time:" in description
        assert "s" in description

    def test_item_description_error(self):
        """Item description includes error message."""

        @dataclasses.dataclass
        class TestCheck(HealthCheck):
            def check_status(self):
                raise HealthCheckException("Test error")

        feed = HealthCheckFeed()
        check = TestCheck()
        check.run_check()
        description = feed.item_description(check)
        assert "Test error" in description

    def test_item_categories_healthy(self):
        """Healthy items have 'healthy' category."""

        @dataclasses.dataclass
        class TestCheck(HealthCheck):
            def check_status(self):
                pass

        feed = HealthCheckFeed()
        check = TestCheck()
        check.run_check()
        categories = feed.item_categories(check)
        assert "healthy" in categories
        assert "error" not in categories

    def test_item_categories_error(self):
        """Failed items have 'error' and 'unhealthy' categories."""

        @dataclasses.dataclass
        class TestCheck(HealthCheck):
            def check_status(self):
                raise HealthCheckException("Test error")

        feed = HealthCheckFeed()
        check = TestCheck()
        check.run_check()
        categories = feed.item_categories(check)
        assert "error" in categories
        assert "unhealthy" in categories

    def test_item_link(self):
        """Item link points to health check page."""

        @dataclasses.dataclass
        class TestCheck(HealthCheck):
            def check_status(self):
                pass

        feed = HealthCheckFeed()
        check = TestCheck()
        link = feed.item_link(check)
        assert link == reverse("health_check")

    def test_item_pubdate(self):
        """Item has publication date."""

        @dataclasses.dataclass
        class TestCheck(HealthCheck):
            def check_status(self):
                pass

        feed = HealthCheckFeed()
        check = TestCheck()
        pubdate = feed.item_pubdate(check)
        assert pubdate is not None

    def test_item_updateddate(self):
        """Item has updated date."""

        @dataclasses.dataclass
        class TestCheck(HealthCheck):
            def check_status(self):
                pass

        feed = HealthCheckFeed()
        check = TestCheck()
        updated = feed.item_updateddate(check)
        assert updated is not None


class TestHealthCheckRSSFeed:
    """Tests for the HealthCheckRSSFeed class (RSS 2.0)."""

    def test_feed_attributes(self):
        """Verify RSS feed has required attributes."""
        feed = HealthCheckRSSFeed()
        assert feed.title == "Health Check Status"
        assert feed.description == "Current status of system health checks"
        assert feed.link() == reverse("health_check")


@pytest.mark.django_db
class TestHealthCheckFeedIntegration:
    """Integration tests for the health check feed endpoint."""

    def test_feed_endpoint_exists(self, client):
        """Feed endpoint is accessible."""
        response = client.get(reverse("health_check_feed"))
        assert response.status_code == 200
        assert "application/atom+xml" in response["Content-Type"]

    def test_atom_feed_endpoint(self, client):
        """Atom feed endpoint is accessible."""
        response = client.get(reverse("health_check_feed_atom"))
        assert response.status_code == 200
        assert "application/atom+xml" in response["Content-Type"]

    def test_rss_feed_endpoint(self, client):
        """RSS feed endpoint is accessible."""
        response = client.get(reverse("health_check_feed_rss"))
        assert response.status_code == 200
        assert "application/rss+xml" in response["Content-Type"]

    def test_feed_valid_xml(self, client):
        """Feed returns valid XML."""
        response = client.get(reverse("health_check_feed"))
        assert response.status_code == 200

        # Parse XML to verify it's valid
        try:
            root = ElementTree.fromstring(response.content)
            assert root is not None
        except ElementTree.ParseError:
            pytest.fail("Feed did not return valid XML")

    def test_rss_feed_valid_xml(self, client):
        """RSS feed returns valid XML."""
        response = client.get(reverse("health_check_feed_rss"))
        assert response.status_code == 200

        # Parse XML to verify it's valid
        try:
            root = ElementTree.fromstring(response.content)
            assert root is not None
        except ElementTree.ParseError:
            pytest.fail("RSS feed did not return valid XML")

    def test_feed_contains_entries(self, client):
        """Feed contains entry elements for health checks."""
        response = client.get(reverse("health_check_feed"))
        assert response.status_code == 200

        root = ElementTree.fromstring(response.content)
        # Atom feeds use namespace
        namespace = {"atom": "http://www.w3.org/2005/Atom"}
        entries = root.findall("atom:entry", namespace)
        assert len(entries) > 0

    def test_rss_feed_contains_items(self, client):
        """RSS feed contains item elements for health checks."""
        response = client.get(reverse("health_check_feed_rss"))
        assert response.status_code == 200

        root = ElementTree.fromstring(response.content)
        # RSS items are under channel
        items = root.findall(".//item")
        assert len(items) > 0

    def test_feed_entry_structure(self, client):
        """Feed entries have required Atom elements."""
        response = client.get(reverse("health_check_feed"))
        assert response.status_code == 200

        root = ElementTree.fromstring(response.content)
        namespace = {"atom": "http://www.w3.org/2005/Atom"}
        entries = root.findall("atom:entry", namespace)

        # Check first entry has required fields
        if entries:
            entry = entries[0]
            assert entry.find("atom:title", namespace) is not None
            assert entry.find("atom:link", namespace) is not None
            assert entry.find("atom:updated", namespace) is not None

    def test_rss_feed_item_structure(self, client):
        """RSS feed items have required elements."""
        response = client.get(reverse("health_check_feed_rss"))
        assert response.status_code == 200

        root = ElementTree.fromstring(response.content)
        items = root.findall(".//item")

        # Check first item has required fields
        if items:
            item = items[0]
            assert item.find("title") is not None
            assert item.find("link") is not None
            assert item.find("description") is not None
            assert item.find("pubDate") is not None
