import secrets

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction

from .models import User
from .permissions import is_admin

OPEN_TASK_STATUSES = ["ASSIGNED", "IN_PROGRESS"]


def _guard(admin, user):
    if not is_admin(admin):
        raise PermissionDenied
    if user.pk == admin.pk:
        raise ValidationError("You cannot change your own account here.")


def _has_open_tasks(user):
    return user.tasks.filter(status__in=OPEN_TASK_STATUSES).exists()


@transaction.atomic
def create_staff(admin, form):
    """Create a STAFF account with a one-time random password, shown to the admin once."""
    if not is_admin(admin):
        raise PermissionDenied
    password = secrets.token_urlsafe(10)
    user = form.save(commit=False)
    user.role = User.Role.STAFF
    user.set_password(password)
    user.save()
    return user, password


@transaction.atomic
def set_role(admin, user, role):
    _guard(admin, user)
    if role not in User.Role.values:
        raise ValidationError("Choose a valid role.")
    if user.role == User.Role.STAFF and role != User.Role.STAFF and _has_open_tasks(user):
        raise ValidationError("Reassign this person's open tasks first.")
    user.role = role
    user.is_staff = role == User.Role.ADMIN  # Django admin site access
    user.save(update_fields=["role", "is_staff"])
    return user


@transaction.atomic
def set_active(admin, user, active):
    _guard(admin, user)
    if not active and _has_open_tasks(user):
        raise ValidationError("Reassign this person's open tasks before deactivating them.")
    user.is_active = active
    user.save(update_fields=["is_active"])
    return user
