"""Every dashboard number comes from these ORM queries. Nothing is hard-coded."""
from datetime import timedelta

from django.db.models import Avg, Count, DurationField, ExpressionWrapper, F, Q
from django.db.models.functions import TruncWeek
from django.utils import timezone

from accounts.models import User
from issues.models import Category, Issue
from issues.smart import hotspots, overdue_q

S = Issue.Status


def summary():
    data = Issue.objects.aggregate(
        total=Count("id"),
        open=Count("id", filter=Q(status__in=Issue.OPEN_STATUSES)),
        high_open=Count("id", filter=Q(status__in=Issue.OPEN_STATUSES, priority="HIGH")),
        resolved=Count("id", filter=Q(status=S.RESOLVED)),
        rejected=Count("id", filter=Q(status=S.REJECTED)),
        awaiting=Count("id", filter=Q(verification_pending=True)),
    )
    avg = Issue.objects.filter(resolved_at__isnull=False).aggregate(
        v=Avg(ExpressionWrapper(F("resolved_at") - F("created_at"), output_field=DurationField()))
    )["v"]
    data["avg_resolution_hours"] = round(avg.total_seconds() / 3600, 1) if avg is not None else None
    data["overdue"] = Issue.objects.filter(overdue_q()).count()
    return data


def by_status():
    counts = dict(Issue.objects.values_list("status").annotate(n=Count("id")))
    return [{"key": v, "label": l, "count": counts.get(v, 0)} for v, l in S.choices]


def by_category():
    counts = dict(Issue.objects.values_list("category").annotate(n=Count("id")))
    rows = [{"key": v, "label": l, "count": counts.get(v, 0)} for v, l in Category.choices]
    return sorted(rows, key=lambda r: r["count"], reverse=True)


def weekly_trend(weeks=8):
    """Reports created and resolved per week (Monday start), oldest first, zero-filled."""
    today = timezone.localdate()
    start = today - timedelta(days=today.weekday(), weeks=weeks - 1)

    def counts(field):
        rows = (Issue.objects.filter(**{f"{field}__date__gte": start})
                .annotate(week=TruncWeek(field)).values("week").annotate(n=Count("id")))
        return {timezone.localtime(r["week"]).date() if hasattr(r["week"], "hour") else r["week"]: r["n"] for r in rows}

    created, resolved = counts("created_at"), counts("resolved_at")
    labels = [start + timedelta(weeks=i) for i in range(weeks)]
    return {
        "labels": [d.strftime("%d %b") for d in labels],
        "reported": [created.get(d, 0) for d in labels],
        "resolved": [resolved.get(d, 0) for d in labels],
    }


def overdue_issues(limit=10):
    return Issue.objects.filter(overdue_q()).select_related("assigned_to").order_by("created_at")[:limit]


def open_hotspots():
    return hotspots(Issue.objects.filter(status__in=Issue.OPEN_STATUSES, merged_into__isnull=True))


def staff_workload():
    return User.objects.filter(role="STAFF", is_active=True).annotate(
        open_tasks=Count("tasks", filter=Q(tasks__status__in=[S.ASSIGNED, S.IN_PROGRESS])),
        done=Count("tasks", filter=Q(tasks__status=S.RESOLVED)),
    ).order_by("-open_tasks", "first_name")
