from django.contrib.auth.views import LogoutView
from django.urls import path

from . import views

urlpatterns = [
    path("register/", views.RegisterView.as_view(), name="register"),
    path("login/", views.SignInView.as_view(), name="login"),
    path("logout/", LogoutView.as_view(next_page="/"), name="logout"),
    path("profile/", views.ProfileView.as_view(), name="profile"),
    path("admin-panel/staff/", views.StaffListView.as_view(), name="staff"),
    path("admin-panel/staff/<int:pk>/", views.StaffActionView.as_view(), name="staff-action"),
    path("profile/password/", views.PasswordView.as_view(), name="password-change"),
]
