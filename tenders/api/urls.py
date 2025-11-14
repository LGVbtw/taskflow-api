from django.urls import path, include
from rest_framework.routers import DefaultRouter

from tenders.api.views import TenderFilterMetadataView, TenderViewSet

router = DefaultRouter()
router.register(r"", TenderViewSet, basename="tender")

urlpatterns = [
    path("", include(router.urls)),
    path("filters/", TenderFilterMetadataView.as_view(), name="tender-filters"),
]
