from django.views.generic import TemplateView


class TenderDashboardView(TemplateView):
    template_name = "tenders/index.html"
