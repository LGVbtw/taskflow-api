from django.db import models


class Tender(models.Model):
    """Represents a scraped tender notice from e-marchespublics."""

    source_id = models.CharField(max_length=100, unique=True)
    title = models.CharField(max_length=300)
    buyer_name = models.CharField(max_length=255, blank=True)
    buyer_location = models.CharField(max_length=255, blank=True)
    category = models.CharField(max_length=100, blank=True)
    procedure = models.CharField(max_length=120, blank=True)
    region = models.CharField(max_length=120, blank=True)
    department = models.CharField(max_length=120, blank=True)
    deadline_label = models.CharField(max_length=150, blank=True)
    deadline_at = models.DateTimeField(null=True, blank=True)
    buyer_site_url = models.URLField(blank=True)
    notice_links = models.JSONField(default=dict, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    raw_html = models.TextField(blank=True)
    published_at = models.DateTimeField(null=True, blank=True)
    scraped_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-deadline_at", "-id"]

    def __str__(self) -> str:
        return self.title
