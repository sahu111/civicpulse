from django.conf import settings
from django.contrib import admin
from django.urls import include, path

from core.views import LandingView, ui_preview

urlpatterns = [
    path("", LandingView.as_view(), name="landing"),
    path("", include("accounts.urls")),
    path("", include("issues.urls")),
    path("", include("notifications.urls")),
    path("", include("analytics.urls")),
    path("django-admin/", admin.site.urls),
]

if settings.DEBUG:
    urlpatterns.append(path("ui/", ui_preview, name="ui-preview"))
