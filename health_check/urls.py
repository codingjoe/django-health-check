import warnings

from django.urls import path

from health_check.views import MainView

warnings.warn(
    "The `health_check.urls` module is deprecated: it has been replaced by view-based checks. Action: use `health_check.views.MainView` or `HealthCheckView.as_view(checks=...)` in your URLconf. See migration guide: https://codingjoe.dev/django-health-check/migrate-to-v4/ (docs/migrate-to-v4.md).",
    DeprecationWarning,
)

app_name = "health_check"

urlpatterns = [
    path("", MainView.as_view(), name="health_check_home"),
    path("<str:subset>/", MainView.as_view(), name="health_check_subset"),
]
