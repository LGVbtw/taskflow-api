from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="Tender",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("source_id", models.CharField(max_length=100, unique=True)),
                ("title", models.CharField(max_length=300)),
                ("buyer_name", models.CharField(blank=True, max_length=255)),
                ("buyer_location", models.CharField(blank=True, max_length=255)),
                ("category", models.CharField(blank=True, max_length=100)),
                ("procedure", models.CharField(blank=True, max_length=120)),
                ("region", models.CharField(blank=True, max_length=120)),
                ("department", models.CharField(blank=True, max_length=120)),
                ("deadline_label", models.CharField(blank=True, max_length=150)),
                ("deadline_at", models.DateTimeField(blank=True, null=True)),
                ("buyer_site_url", models.URLField(blank=True)),
                ("notice_links", models.JSONField(blank=True, default=dict)),
                ("metadata", models.JSONField(blank=True, default=dict)),
                ("raw_html", models.TextField(blank=True)),
                ("published_at", models.DateTimeField(blank=True, null=True)),
                ("scraped_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "ordering": ["-deadline_at", "-id"],
            },
        ),
    ]
