from rest_framework.routers import DefaultRouter

from .views import DocumentAttachmentViewSet, DocumentViewSet

router = DefaultRouter()
router.register(r"attachments", DocumentAttachmentViewSet, basename="attachment")
router.register(r"", DocumentViewSet, basename="document")

urlpatterns = router.urls
