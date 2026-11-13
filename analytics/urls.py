from django.urls import path

from . import views

app_name = "analytics"

urlpatterns = [
    path("admin-panel/", views.DashboardView.as_view(), name="dashboard"),
    path("api/analytics/charts/", views.ChartDataView.as_view(), name="charts"),
]
