from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import ActionPlanViewSet, ActionTaskViewSet

plans_router = DefaultRouter()
plans_router.register(r"", ActionPlanViewSet, basename="action-plan")

tasks_router = DefaultRouter()
tasks_router.register(r"", ActionTaskViewSet, basename="action-task")

urlpatterns = [
    path("", include(plans_router.urls)),
    path("tasks/", include(tasks_router.urls)),
]
