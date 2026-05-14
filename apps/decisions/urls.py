from rest_framework.routers import DefaultRouter

from .views import DecisionCategoryViewSet, DecisionViewSet

router = DefaultRouter()
router.register(r"categories", DecisionCategoryViewSet, basename="decision-category")
router.register(r"", DecisionViewSet, basename="decision")

urlpatterns = router.urls
