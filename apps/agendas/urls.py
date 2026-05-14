from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import AgendaItemViewSet, AgendaViewSet

router = DefaultRouter()
router.register(r"", AgendaViewSet, basename="agenda")

# Items routés à part pour /api/v1/agenda-items/{id}/discuss etc.
items_router = DefaultRouter()
items_router.register(r"", AgendaItemViewSet, basename="agenda-item")

urlpatterns = [
    path("", include(router.urls)),
    path("items/", include(items_router.urls)),
]
