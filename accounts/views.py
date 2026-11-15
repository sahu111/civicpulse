from django.conf import settings
from django.contrib import messages
from django.utils.decorators import method_decorator
from django_ratelimit.decorators import ratelimit
from django.core.exceptions import ValidationError
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404
from django.views import View
from django.views.generic import TemplateView
from django.contrib.auth import login
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.views import LoginView, PasswordChangeView
from django.shortcuts import redirect
from django.views.generic import FormView, UpdateView

from . import services
from .forms import LoginForm, ProfileForm, RegisterForm, StaffCreateForm, StyledPasswordChangeForm
from .models import User
from .permissions import ADMIN, RoleRequiredMixin, home_url


@method_decorator(ratelimit(key="ip", rate=settings.RATE_REGISTER, method="POST", block=True), name="post")
class RegisterView(FormView):
    template_name = "accounts/auth_form.html"
    form_class = RegisterForm
    extra_context = {"heading": "Create your account", "submit": "Create account",
                     "alt_text": "Already registered?", "alt_url": "/login/", "alt_label": "Sign in"}

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            return redirect(home_url(request.user))
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        user = form.save()
        login(self.request, user, backend="django.contrib.auth.backends.ModelBackend")
        messages.success(self.request, "Welcome to CivicPulse. Your account is ready.")
        return redirect(home_url(user))


@method_decorator(ratelimit(key="ip", rate=settings.RATE_LOGIN_IP, method="POST", block=True), name="post")
@method_decorator(ratelimit(key="post:username", rate=settings.RATE_LOGIN_EMAIL, method="POST", block=True), name="post")
class SignInView(LoginView):
    template_name = "accounts/auth_form.html"
    form_class = LoginForm
    redirect_authenticated_user = True
    extra_context = {"heading": "Sign in", "submit": "Sign in",
                     "alt_text": "New here?", "alt_url": "/register/", "alt_label": "Create an account"}

    def get_default_redirect_url(self):
        return home_url(self.request.user)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        # One-click demo sign-in cards: development only, never in production.
        if settings.DEBUG and settings.DEMO_PASSWORD:
            labels = {"ADMIN": "Administrator", "STAFF": "Field staff", "CITIZEN": "Citizen"}
            emails = ["admin@civicpulse.test", "staff1@civicpulse.test",
                      "citizen1@civicpulse.test", "citizen2@civicpulse.test"]
            users = {u.email: u for u in User.objects.filter(email__in=emails, is_active=True)}
            ctx["demo_password"] = settings.DEMO_PASSWORD
            ctx["demo_accounts"] = [
                {"email": e, "label": labels[users[e].role], "name": users[e].get_full_name() or users[e].username}
                for e in emails if e in users
            ]
        return ctx


class ProfileView(LoginRequiredMixin, UpdateView):
    template_name = "accounts/profile.html"
    form_class = ProfileForm
    success_url = "/profile/"

    def get_object(self, queryset=None):
        return self.request.user

    def form_valid(self, form):
        messages.success(self.request, "Profile updated.")
        return super().form_valid(form)


class PasswordView(PasswordChangeView):
    template_name = "core/form_page.html"
    form_class = StyledPasswordChangeForm
    success_url = "/profile/"
    extra_context = {"heading": "Change password", "submit": "Update password"}

    def form_valid(self, form):
        messages.success(self.request, "Password changed.")
        return super().form_valid(form)


class StaffListView(RoleRequiredMixin, TemplateView):
    allowed_roles = (ADMIN,)
    template_name = "accounts/staff.html"

    def get_context_data(self, form=None, **kwargs):
        people = User.objects.exclude(role=User.Role.CITIZEN).annotate(
            open_tasks=Count("tasks", filter=Q(tasks__status__in=services.OPEN_TASK_STATUSES))
        ).order_by("role", "first_name", "username")
        return super().get_context_data(
            form=form or StaffCreateForm(), people=people, roles=User.Role.choices, **kwargs
        )

    def post(self, request):
        form = StaffCreateForm(request.POST)
        if not form.is_valid():
            return self.render_to_response(self.get_context_data(form=form))
        user, password = services.create_staff(request.user, form)
        messages.success(request, f"Staff account created for {user.email}. One-time password: {password}")
        return redirect("staff")


class StaffActionView(RoleRequiredMixin, View):
    allowed_roles = (ADMIN,)

    def post(self, request, pk):
        user = get_object_or_404(User, pk=pk)
        try:
            if request.POST.get("action") == "role":
                services.set_role(request.user, user, request.POST.get("role"))
            elif request.POST.get("action") == "active":
                services.set_active(request.user, user, request.POST.get("active") == "1")
            messages.success(request, "Saved.")
        except ValidationError as e:
            messages.error(request, " ".join(e.messages))
        return redirect("staff")
