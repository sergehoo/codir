from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import ActionPlanViewSet, ActionTaskViewSet

plans_router = DefaultRouter()
plans_router.register(r"", ActionPlanViewSet, basename="action-plan")

tasks_router = DefaultRouter()
tasks_router.register(r"", ActionTaskViewSet, basename="action-task")

# ⚠ ORDRE IMPORTANT : le router `plans_router` expose un pattern `<pk>/` qui
# matche aussi `tasks/` (avec pk="tasks") → 404 sur le détail d'un plan
# inexistant. On doit donc résoudre `tasks/` AVANT le router racine.
urlpatterns = [
    path("tasks/", include(tasks_router.urls)),
    path("", include(plans_router.urls)),
]
