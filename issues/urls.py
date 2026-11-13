from django.urls import path

from . import views

app_name = "issues"

urlpatterns = [
    path("dashboard/", views.DashboardView.as_view(), name="dashboard"),
    path("admin-panel/export/", views.ExportView.as_view(), name="export"),
    path("map/", views.MapView.as_view(), name="map"),
    path("api/map/", views.MapDataView.as_view(), name="map-data"),
    path("tasks/", views.TaskListView.as_view(), name="tasks"),
    path("issues/", views.IssueListView.as_view(), name="list"),
    path("issues/new/", views.IssueCreateView.as_view(), name="create"),
    path("issues/suggest/", views.SuggestView.as_view(), name="suggest"),
    path("issues/mine/", views.MyIssuesView.as_view(), name="mine"),
    path("issues/<str:code>/", views.IssueDetailView.as_view(), name="detail"),
    path("issues/<str:code>/action/", views.IssueActionView.as_view(), name="action"),
    path("issues/<str:code>/vote/", views.VoteView.as_view(), name="vote"),
    path("issues/<str:code>/media/<int:pk>/", views.MediaView.as_view(), name="media"),
]
