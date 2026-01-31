"""RSS/Atom feed for health check monitoring."""

from django.contrib.syndication.views import Feed
from django.urls import reverse
from django.utils import timezone
from django.utils.feedgenerator import Atom1Feed, Rss201rev2Feed

from health_check.views import HealthCheckView


class BaseHealthCheckFeed(Feed):
    """Base class for health check feeds.

    Provides shared functionality for health check status feeds,
    similar to cloud providers like Google Cloud, AWS, and Azure.
    This allows monitoring services to subscribe to health status updates.
    """

    title = "Health Check Status"
    description = "Current status of system health checks"

    def link(self):
        """Return the link to the health check page."""
        return reverse("health_check")

    def items(self):
        """Return health check plugins as feed items."""
        view = HealthCheckView()
        view.run_check()
        return list(view.results.values())

    def item_title(self, item):
        """Return the title for a health check item."""
        return str(item)

    def item_description(self, item):
        """Return the description for a health check item."""
        status = item.pretty_status()
        timing = f"Response time: {item.time_taken:.3f}s"
        return f"{status}\n{timing}"

    def item_link(self, item):
        """Return the link to the health check page."""
        return reverse("health_check")

    def item_pubdate(self, item):
        """Return the publication date (current time)."""
        return timezone.now()

    def item_updateddate(self, item):
        """Return the updated date (current time)."""
        return timezone.now()

    def item_author_name(self, item):
        """Return the author name."""
        return "Django Health Check"

    def item_categories(self, item):
        """Return categories based on health status."""
        if item.errors:
            return ["error", "unhealthy"]
        return ["healthy"]


class HealthCheckFeed(BaseHealthCheckFeed):
    """Atom feed for health check status monitoring."""

    feed_type = Atom1Feed


class HealthCheckRSSFeed(BaseHealthCheckFeed):
    """RSS 2.0 feed for health check status monitoring."""

    feed_type = Rss201rev2Feed
