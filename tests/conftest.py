"""Pytest configuration for health_check tests."""

import pytest
from django.test import RequestFactory

from health_check.views import HealthCheckView


@pytest.fixture
def health_check_view():
    """Create a function that can render a HealthCheckView with custom checks and request parameters."""
    factory = RequestFactory()

    def render_view(checks, accept_header=None, format_param=None):
        """Render a HealthCheckView with custom checks and optional parameters."""
        path = "/"
        if format_param:
            path += f"?format={format_param}"

        kwargs = {}
        if accept_header:
            kwargs["HTTP_ACCEPT"] = accept_header

        request = factory.get(path, **kwargs)
        view = HealthCheckView.as_view(checks=checks)
        response = view(request)
        if hasattr(response, "render"):
            response.render()
        return response

    return render_view
