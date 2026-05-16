from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import ActionPlanViewSet, ActionTaskViewSet

plans_router = DefaultRouter()
plans_router.register(r"", ActionPlanViewSet, basename="action-plan")

tasks_router = DefaultRouter()
tasks_router.register(r"", ActionTaskViewSet, basename="action-task")

# ⚠ Le router `plans_router` expose un pattern `<pk>/` qui matche aussi
# `tasks/` (avec pk="tasks") → 404 sur le détail d'un plan inexistant.
# Solution :
#   1) On définit explicitement `tasks/` AVANT tout include() — gagne TOUJOURS,
#      même si l'ordre des includes Django change.
#   2) On garde le router `tasks/` pour les sous-URLs (`tasks/<pk>/`, etc.).
#   3) Le router racine vient en dernier.
urlpatterns = [
    # 1️⃣ Route explicite pour le LIST/CREATE des tâches (gagne en priorité)
    path(
        "tasks/",
        ActionTaskViewSet.as_view({"get": "list", "post": "create"}),
        name="action-task-list",
    ),
    # 2️⃣ Toutes les autres URLs de tâches (<pk>/, actions custom, etc.)
    path("tasks/", include(tasks_router.urls)),
    # 3️⃣ Router racine des plans en dernier
    path("", include(plans_router.urls)),
]
