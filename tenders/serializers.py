from rest_framework import serializers

from .models import Tender


class TenderSerializer(serializers.ModelSerializer):
    links = serializers.SerializerMethodField()

    class Meta:
        model = Tender
        fields = (
            "id",
            "source_id",
            "title",
            "buyer_name",
            "buyer_location",
            "category",
            "procedure",
            "region",
            "department",
            "deadline_label",
            "deadline_at",
            "buyer_site_url",
            "notice_links",
            "links",
            "metadata",
            "scraped_at",
            "published_at",
        )
        read_only_fields = fields

    def get_links(self, obj):
        links = obj.notice_links or {}
        return [
            {"label": label.title(), "href": href}
            for label, href in links.items()
        ]
