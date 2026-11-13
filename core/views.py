from django.conf import settings
from django.contrib import messages
from django.http import Http404
from django.shortcuts import render
from django.views.generic import TemplateView

from .context_processors import COMMON, NAV


class LandingView(TemplateView):
    template_name = "core/landing.html"
    extra_context = {
        "steps": [
            ("Reported by a citizen", True),
            ("Reviewed by the city", True),
            ("Assigned to field staff", True),
            ("Work in progress", True),
            ("Verified and resolved", False),
        ],
        "features": [
            {"icon": "map-pin", "title": "Pin the problem", "text": "Describe the issue, add a photo and drop a pin on the map."},
            {"icon": "shield-check", "title": "City review", "text": "Admins check the report, set priority and assign staff."},
            {"icon": "clipboard-list", "title": "Field work", "text": "Staff update progress and upload completion evidence."},
            {"icon": "bell", "title": "Stay informed", "text": "Every status change is logged and you get notified."},
        ],
    }


def ui_preview(request):
    """Shows the app shell with sample nav. Only available when DEBUG is on."""
    if not settings.DEBUG:
        raise Http404
    messages.info(request, "This is a sample toast message.")
    nav = [{"label": l, "url": u, "icon": i, "active": u == "/dashboard/"} for l, u, i in NAV["CITIZEN"] + COMMON]
    return render(request, "core/ui_preview.html", {"nav_items": nav})


def ratelimited(request, exception=None):
    """Shown when django-ratelimit blocks a request (HTTP 429)."""
    return render(request, "core/error.html", {
        "code": "429", "heading": "Too many attempts",
        "text": "Please wait a minute and try again.", "icon_name": "alert-triangle",
    }, status=429)
