from django.contrib import admin

from .models import Tender


@admin.register(Tender)
class TenderAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "buyer_name",
        "region",
        "department",
        "deadline_at",
        "procedure",
    )
    search_fields = ("title", "buyer_name", "department", "region", "procedure")
    list_filter = ("region", "procedure", "category")
    readonly_fields = ("scraped_at",)
