from django.contrib.auth import get_user_model

from .models import Notification


def notify(user, issue, message, exclude=None):
    if user is None or (exclude is not None and user.pk == exclude.pk):
        return
    Notification.objects.create(user=user, issue=issue, message=message[:300])


def notify_admins(issue, message, exclude=None):
    admins = get_user_model().objects.filter(role="ADMIN", is_active=True)
    if exclude is not None:
        admins = admins.exclude(pk=exclude.pk)
    Notification.objects.bulk_create(
        [Notification(user=a, issue=issue, message=message[:300]) for a in admins]
    )
