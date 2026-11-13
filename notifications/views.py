from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import redirect
from django.utils import timezone
from django.views import View
from django.views.generic import ListView


class NotificationListView(LoginRequiredMixin, ListView):
    template_name = "notifications/list.html"
    paginate_by = 20

    def get_queryset(self):
        return self.request.user.notifications.select_related("issue")


class MarkAllReadView(LoginRequiredMixin, View):
    def post(self, request):
        request.user.notifications.filter(read_at__isnull=True).update(read_at=timezone.now())
        return redirect("notifications:list")
