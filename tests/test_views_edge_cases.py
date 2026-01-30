"""Additional tests for edge cases in views to improve coverage."""

from django.test import RequestFactory

from health_check.backends import HealthCheck
from health_check.views import HealthCheckView


class TestHealthCheckViewEdgeCases:
    """Test edge cases in the HealthCheckView."""

    def test_view_with_kwargs_options(self):
        """Test view with check that has kwargs/options."""
        factory = RequestFactory()
        request = factory.get("/")

        class ConfigurableBackend(HealthCheck):
            def __init__(self, timeout=5, **kwargs):
                super().__init__(**kwargs)
                self.timeout = timeout

            def run_check(self):
                pass

        # Pass check as tuple with options
        view = HealthCheckView.as_view(checks=[(ConfigurableBackend, {"timeout": 10})])
        response = view(request)
        if hasattr(response, "render"):
            response.render()
        assert response.status_code == 200

    def test_view_with_string_check(self):
        """Test view with check specified as import string."""
        factory = RequestFactory()
        request = factory.get("/")

        view = HealthCheckView.as_view(checks=["health_check.checks.Cache"])
        response = view(request)
        if hasattr(response, "render"):
            response.render()
        assert response.status_code == 200

    def test_view_without_threading(self):
        """Test view with threading disabled."""
        factory = RequestFactory()
        request = factory.get("/")

        class SimpleBackend(HealthCheck):
            def run_check(self):
                pass

        view = HealthCheckView.as_view(checks=[SimpleBackend], use_threading=False)
        response = view(request)
        if hasattr(response, "render"):
            response.render()
        assert response.status_code == 200

    def test_check_method_returns_errors(self):
        """Test that check() method returns errors correctly."""

        class FailingBackend(HealthCheck):
            def check_status(self):
                self.add_error("Test failure")

        view_instance = HealthCheckView()
        view_instance.checks = [FailingBackend]
        errors = view_instance.check()
        assert len(errors) > 0

    def test_view_get_plugins_with_no_checks(self):
        """Test get_plugins when checks is empty."""
        view = HealthCheckView()
        view.checks = []
        plugins = list(view.get_plugins())
        assert plugins == []

    def test_response_with_non_template_response(self):
        """Test that JsonResponse is returned for JSON accept."""
        factory = RequestFactory()
        request = factory.get("/", HTTP_ACCEPT="application/json")

        class SimpleBackend(HealthCheck):
            def run_check(self):
                pass

        view = HealthCheckView.as_view(checks=[SimpleBackend])
        response = view(request)
        # JsonResponse is not a TemplateResponse, so no render needed
        assert response.status_code == 200
        assert response["content-type"] == "application/json"

    def test_multiple_critical_and_non_critical(self):
        """Test view with mix of critical and non-critical services."""
        factory = RequestFactory()
        request = factory.get("/")

        class CriticalBackend(HealthCheck):
            critical_service = True

            def check_status(self):
                self.add_error("Critical failure")

        class NonCriticalBackend(HealthCheck):
            critical_service = False

            def check_status(self):
                self.add_error("Non-critical failure")

        view = HealthCheckView.as_view(checks=[CriticalBackend, NonCriticalBackend])
        response = view(request)
        if hasattr(response, "render"):
            response.render()
        # Should fail because critical service failed
        assert response.status_code == 500

    def test_context_data_with_errors(self):
        """Test get_context_data includes errors info."""
        view = HealthCheckView()

        class FailingBackend(HealthCheck):
            def check_status(self):
                self.add_error("Test error")

        view.checks = [FailingBackend]
        # Run the check first to populate errors
        view.check()
        context = view.get_context_data()
        assert "errors" in context
        assert "plugins" in context
        assert context["errors"] is True  # has errors

    def test_context_data_without_errors(self):
        """Test get_context_data without errors."""
        view = HealthCheckView()

        class HealthyBackend(HealthCheck):
            def run_check(self):
                pass

        view.checks = [HealthyBackend]
        context = view.get_context_data()
        assert context["errors"] is False  # no errors
