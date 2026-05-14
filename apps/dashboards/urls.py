from django.urls import path

from .views import BetaDashboardView

urlpatterns = [
    path("beta/", BetaDashboardView.as_view(), name="dashboard-beta"),
]
