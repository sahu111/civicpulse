import csv
import io
from datetime import timedelta

import pytest
from django.utils import timezone

from accounts.models import User
from analytics import queries
from issues import services
from issues.models import Issue

S = Issue.Status
pytestmark = pytest.mark.django_db


def test_summary_metrics_from_known_data(make_user, make_issue):
    admin, staff = make_user("ADMIN"), make_user("STAFF")
    now = timezone.now()
    a, b, c = make_issue(), make_issue(), make_issue()
    Issue.objects.filter(pk=a.pk).update(status=S.RESOLVED, created_at=now - timedelta(hours=10), resolved_at=now)
    Issue.objects.filter(pk=b.pk).update(priority="HIGH")
    Issue.objects.filter(pk=c.pk).update(priority="LOW", created_at=now - timedelta(hours=300))
    s = queries.summary()
    assert (s["total"], s["open"], s["resolved"], s["high_open"], s["overdue"]) == (3, 2, 1, 1, 1)
    assert s["avg_resolution_hours"] == 10.0
    status = {r["key"]: r["count"] for r in queries.by_status()}
    assert status["RESOLVED"] == 1 and status["REPORTED"] == 2
    trend = queries.weekly_trend()
    assert sum(trend["reported"]) == 3  # all three fall inside the 8-week window
    assert sum(trend["resolved"]) == 1
    assert len(trend["labels"]) == 8


def test_dashboard_number_follows_database(client, make_user, make_issue):
    client.force_login(make_user("ADMIN"))
    before = client.get("/admin-panel/").context["s"]["total"]
    make_issue()
    assert client.get("/admin-panel/").context["s"]["total"] == before + 1
    data = client.get("/api/analytics/charts/").json()
    assert sum(r["count"] for r in data["by_category"]) == before + 1


def test_dashboard_admin_only(client, make_user):
    for role in ("CITIZEN", "STAFF"):
        client.force_login(make_user(role))
        assert client.get("/admin-panel/").status_code == 403
        assert client.get("/api/analytics/charts/").status_code == 403
        assert client.get("/admin-panel/export/").status_code == 403


def test_csv_export_filters_and_neutralises_formulas(client, make_user, make_issue):
    client.force_login(make_user("ADMIN"))
    make_issue(title="=HYPERLINK(\"http://x\")", category="WATER")
    make_issue(title="+cmd stuff here", category="WATER")
    make_issue(title="Normal pothole report", category="ROADS")
    r = client.get("/admin-panel/export/?category=WATER")
    assert r["Content-Type"].startswith("text/csv")
    rows = list(csv.reader(io.StringIO(r.content.decode("utf-8-sig"))))
    assert rows[0][0] == "Tracking code" and len(rows) == 3
    titles = {row[1] for row in rows[1:]}
    assert titles == {"'=HYPERLINK(\"http://x\")", "'+cmd stuff here"}


def test_admin_detail_shows_rule_based_wording(client, make_user, make_issue):
    issue = make_issue()
    make_issue()  # a near-identical duplicate
    client.force_login(make_user("ADMIN"))
    html = client.get(f"/issues/{issue.tracking_code}/").content.decode().lower()
    assert "recommendations" in html and "rule-based" in html and "merge into it" in html
    assert "machine learning" not in html and "ai model" not in html


def test_suggest_fragment_for_citizens(client, make_user, make_issue):
    make_issue()
    client.force_login(make_user())
    r = client.get("/issues/suggest/", {"title": "Pothole by the school", "description": "deep pothole",
                                        "category": "", "latitude": "12.5", "longitude": "77.5"})
    html = r.content.decode()
    assert "Roads and potholes" in html and "Similar open reports nearby" in html
    assert "machine learning" not in html.lower()


def test_admin_can_correct_category(make_user, make_issue):
    admin, issue = make_user("ADMIN"), make_issue()
    issue = services.set_category(issue, "WATER", admin)
    assert issue.category == "WATER" and issue.events.filter(kind="info").exists()


def test_staff_management(client, make_user, make_issue):
    admin, staff = make_user("ADMIN"), make_user("STAFF")
    client.force_login(admin)
    r = client.post("/admin-panel/staff/", {"first_name": "New", "last_name": "Worker",
                                            "username": "worker", "email": "worker@example.test"})
    assert r.status_code == 302 and User.objects.get(username="worker").role == "STAFF"

    issue = services.change_status(make_issue(), S.UNDER_REVIEW, admin)
    services.assign(issue, staff, admin)
    client.post(f"/admin-panel/staff/{staff.pk}/", {"action": "active", "active": "0"})
    staff.refresh_from_db()
    assert staff.is_active  # blocked: open task

    client.post(f"/admin-panel/staff/{admin.pk}/", {"action": "role", "role": "CITIZEN"})
    admin.refresh_from_db()
    assert admin.role == "ADMIN"  # cannot change own role

    client.force_login(make_user())
    assert client.get("/admin-panel/staff/").status_code == 403
