from django.urls import include, path

from health_check.views import HealthCheckView

health_check_patterns = (
    [
        path("", HealthCheckView.as_view(), name="health_check_home"),
        path("<str:subset>/", HealthCheckView.as_view(), name="health_check_subset"),
    ],
    "health_check",
)

urlpatterns = [
    path("ht/", include(health_check_patterns)),
]
