from django.http import JsonResponse
from django.views import View
from django.views.generic import TemplateView

from accounts.permissions import ADMIN, RoleRequiredMixin
from issues import smart_config

from . import queries


class DashboardView(RoleRequiredMixin, TemplateView):
    allowed_roles = (ADMIN,)
    template_name = "analytics/dashboard.html"

    def get_context_data(self, **kwargs):
        return super().get_context_data(
            s=queries.summary(),
            overdue=queries.overdue_issues(),
            hotspots=queries.open_hotspots()[:8],
            workload=queries.staff_workload(),
            targets=smart_config.RESOLUTION_TARGET_HOURS,
            hotspot_min=smart_config.HOTSPOT_MIN_COUNT,
            **kwargs,
        )


class ChartDataView(RoleRequiredMixin, View):
    allowed_roles = (ADMIN,)

    def get(self, request):
        return JsonResponse({
            "by_status": queries.by_status(),
            "by_category": queries.by_category(),
            "weekly": queries.weekly_trend(),
        })
