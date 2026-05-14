from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import CurrentOrgView, SubsidiaryViewSet

router = DefaultRouter()
router.register(r"subsidiaries", SubsidiaryViewSet, basename="subsidiary")

urlpatterns = [
    path("me/", CurrentOrgView.as_view(), name="org-me"),
    path("", include(router.urls)),
]
