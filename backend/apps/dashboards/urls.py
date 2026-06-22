from django.urls import path

from .views import BetaDashboardView, DailyBriefingView, EpiScoreView, WatchlistView

urlpatterns = [
    path("beta/", BetaDashboardView.as_view(), name="dashboard-beta"),
    path("epi-score/", EpiScoreView.as_view(), name="dashboard-epi-score"),
    path("watchlist/", WatchlistView.as_view(), name="dashboard-watchlist"),
    path("briefing/today/", DailyBriefingView.as_view(), name="dashboard-briefing"),
]
