"""All role and object-level access rules live here. Views and services both call these."""
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied

ADMIN, STAFF, CITIZEN = "ADMIN", "STAFF", "CITIZEN"


def has_role(user, *roles):
    return bool(user and user.is_authenticated and user.is_active and user.role in roles)


def is_admin(user):
    return has_role(user, ADMIN)


class RoleRequiredMixin(LoginRequiredMixin):
    """Class-based view guard. The role is read from the database user, never from the request."""

    allowed_roles: tuple = ()

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return self.handle_no_permission()
        if self.allowed_roles and not has_role(request.user, *self.allowed_roles):
            raise PermissionDenied
        return super().dispatch(request, *args, **kwargs)


def home_url(user):
    if has_role(user, ADMIN):
        return "/admin-panel/"
    if has_role(user, STAFF):
        return "/tasks/"
    return "/dashboard/"


def issues_visible_to(user):
    """Private scope: admin sees all, staff only assigned issues, citizens only their own."""
    from issues.models import Issue

    if has_role(user, ADMIN):
        return Issue.objects.all()
    if has_role(user, STAFF):
        return Issue.objects.filter(assigned_to=user)
    if has_role(user, CITIZEN):
        return Issue.objects.filter(reporter=user)
    return Issue.objects.none()


def community_issues():
    """Public community list for citizens: open and resolved reports, no rejected or merged ones."""
    from issues.models import Issue

    return Issue.objects.filter(merged_into__isnull=True).exclude(status=Issue.Status.REJECTED)


def can_view_issue(user, issue):
    if has_role(user, ADMIN):
        return True
    if has_role(user, STAFF):
        return issue.assigned_to_id == user.id
    if has_role(user, CITIZEN):
        return issue.reporter_id == user.id
    return False


def can_update_issue(user, issue):
    """Field work (start, notes, evidence, submit): only the assigned staff member."""
    return has_role(user, STAFF) and issue.assigned_to_id == user.id


def is_reporter(user, issue):
    return has_role(user, CITIZEN) and issue.reporter_id == user.id
