"""Pytest configuration for health_check tests."""

import pytest
from django.test import AsyncRequestFactory

from health_check.views import HealthCheckView


@pytest.fixture
def health_check_view():
    """Create a function that can render a HealthCheckView with custom checks and request parameters."""
    factory = AsyncRequestFactory()

    async def render_view(checks, accept_header=None, format_param=None, method="get"):
        """Render a HealthCheckView with custom checks and optional parameters."""
        path = "/"
        if format_param:
            path += f"?format={format_param}"

        headers = {}
        if accept_header:
            headers["Accept"] = accept_header

        request = factory.generic(method.upper(), path, headers=headers)
        view = HealthCheckView.as_view(checks=checks)
        response = await view(request)
        if hasattr(response, "render"):
            response.render()
        return response

    return render_view
