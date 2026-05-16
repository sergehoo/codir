from django.urls import path

from .views import BetaDashboardView, EpiScoreView

urlpatterns = [
    path("beta/", BetaDashboardView.as_view(), name="dashboard-beta"),
    path("epi-score/", EpiScoreView.as_view(), name="dashboard-epi-score"),
]
