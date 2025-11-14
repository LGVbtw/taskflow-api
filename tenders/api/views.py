from django.db.models import Min, Max
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters, permissions, viewsets
from rest_framework.response import Response
from rest_framework.views import APIView

from tenders.models import Tender
from tenders.serializers import TenderSerializer


class TenderViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Tender.objects.all().order_by("-deadline_at", "-id")
    serializer_class = TenderSerializer
    permission_classes = [permissions.AllowAny]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter, DjangoFilterBackend]
    search_fields = ["title", "buyer_name", "buyer_location", "procedure", "category"]
    ordering_fields = ["deadline_at", "scraped_at", "title"]
    filterset_fields = {
        "category": ["exact"],
        "procedure": ["exact"],
        "region": ["exact"],
        "department": ["exact"],
        "deadline_at": ["gte", "lte"],
    }


class TenderFilterMetadataView(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        qs = Tender.objects.all()
        agg = qs.aggregate(min_deadline=Min("deadline_at"), max_deadline=Max("deadline_at"))
        payload = {
            "categories": sorted(filter(None, qs.values_list("category", flat=True).distinct())),
            "procedures": sorted(filter(None, qs.values_list("procedure", flat=True).distinct())),
            "regions": [
                {"label": region, "count": qs.filter(region=region).count()}
                for region in sorted(filter(None, qs.values_list("region", flat=True).distinct()))
            ],
            "departments": [
                {"label": department, "count": qs.filter(department=department).count()}
                for department in sorted(filter(None, qs.values_list("department", flat=True).distinct()))
            ],
            "deadline_range": {
                "min": agg["min_deadline"],
                "max": agg["max_deadline"],
            },
            "count": qs.count(),
        }
        return Response(payload)
