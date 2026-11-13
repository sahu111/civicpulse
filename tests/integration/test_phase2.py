import re

import pytest
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile

from accounts.models import User
from issues import services
from issues.models import Issue, IssueAssignment, IssueEvent, IssueVote
from notifications.models import Notification
from tests.conftest import ISSUE_DATA, PASSWORD, add_evidence, png_upload

S = Issue.Status
pytestmark = pytest.mark.django_db


# ---------- authentication ----------

def test_register_always_creates_citizen(client):
    r = client.post("/register/", {
        "first_name": "Test", "last_name": "User", "username": "newbie", "email": "New@Example.test",
        "password1": PASSWORD, "password2": PASSWORD, "role": "ADMIN",
    })
    assert r.status_code == 302
    user = User.objects.get(username="newbie")
    assert user.role == "CITIZEN" and user.email == "new@example.test"
    assert user.password.startswith(("pbkdf2_", "argon2", "bcrypt"))


def test_wrong_password_fails_and_logout_ends_session(client, make_user):
    user = make_user()
    r = client.post("/login/", {"username": user.email, "password": "wrong"})
    assert r.status_code == 200 and "_auth_user_id" not in client.session
    client.post("/login/", {"username": user.email, "password": PASSWORD})
    assert "_auth_user_id" in client.session
    client.post("/logout/")
    assert "_auth_user_id" not in client.session


# ---------- permissions ----------

def test_citizen_cannot_open_another_citizens_report(client, make_user, make_issue):
    issue = make_issue()
    client.force_login(make_user())
    assert client.get(f"/issues/{issue.tracking_code}/").status_code == 404
    client.force_login(issue.reporter)
    assert client.get(f"/issues/{issue.tracking_code}/").status_code == 200


def test_staff_sees_only_assigned_issues(client, make_user, make_issue):
    admin, staff, other = make_user("ADMIN"), make_user("STAFF"), make_user("STAFF")
    issue = make_issue()
    services.change_status(issue, S.UNDER_REVIEW, admin)
    services.assign(issue, staff, admin)
    client.force_login(other)
    assert client.get(f"/issues/{issue.tracking_code}/").status_code == 404
    client.force_login(staff)
    assert client.get(f"/issues/{issue.tracking_code}/").status_code == 200


def test_citizen_cannot_use_admin_or_staff_urls(client, make_issue):
    issue = make_issue()
    client.force_login(issue.reporter)
    r = client.post(f"/issues/{issue.tracking_code}/action/", {"action": "review"})
    assert r.status_code == 403
    assert client.get("/tasks/").status_code == 403
    assert Issue.objects.get(pk=issue.pk).status == S.REPORTED


def test_anonymous_redirected_to_login(client):
    r = client.get("/issues/")
    assert r.status_code == 302 and r.url.startswith("/login/")


def test_staff_cannot_submit_issue(client, make_user):
    client.force_login(make_user("STAFF"))
    assert client.get("/issues/new/").status_code == 403


# ---------- issue creation ----------

def test_tracking_codes_are_unique_and_formatted(make_issue):
    codes = [make_issue().tracking_code for _ in range(3)]
    assert len(set(codes)) == 3
    assert all(re.fullmatch(r"CP-\d{4}-\d{4}", c) for c in codes)


def test_submit_with_photo_and_reject_fake_image(client, make_user):
    client.force_login(make_user())
    data = {**ISSUE_DATA, "photo": png_upload()}
    r = client.post("/issues/new/", data)
    assert r.status_code == 302
    issue = Issue.objects.get()
    media = issue.media.get()
    assert re.fullmatch(r"issues/\d{4}/\d{2}/[0-9a-f]{32}\.png", media.file.name)

    fake = SimpleUploadedFile("evil.jpg", b"MZ\x90\x00 not an image", content_type="image/jpeg")
    r = client.post("/issues/new/", {**ISSUE_DATA, "photo": fake})
    assert r.status_code == 200 and b"valid JPEG, PNG or WebP" in r.content
    assert Issue.objects.count() == 1


def test_missing_coordinates_and_long_title_rejected(client, make_user):
    client.force_login(make_user())
    data = {**ISSUE_DATA, "title": "x" * 101}
    data.pop("latitude")
    r = client.post("/issues/new/", data)
    assert r.status_code == 200 and Issue.objects.count() == 0
    assert set(r.context["form"].errors) >= {"title", "latitude"}


# ---------- status transitions ----------

def test_invalid_transition_refused_and_nothing_written(make_user, make_issue):
    admin, issue = make_user("ADMIN"), make_issue()
    before = IssueEvent.objects.count()
    with pytest.raises(ValidationError):
        services.change_status(issue, S.RESOLVED, admin)
    assert IssueEvent.objects.count() == before
    assert Issue.objects.get(pk=issue.pk).status == S.REPORTED


def test_reject_requires_reason(make_user, make_issue):
    admin, issue = make_user("ADMIN"), make_issue()
    with pytest.raises(ValidationError):
        services.change_status(issue, S.REJECTED, admin, "  ")
    issue = services.change_status(issue, S.REJECTED, admin, "Duplicate of an older report")
    assert issue.status == S.REJECTED


def test_full_workflow_writes_history_and_notifications(make_user, make_issue):
    admin, staff = make_user("ADMIN"), make_user("STAFF")
    issue = make_issue()
    citizen = issue.reporter
    issue = services.change_status(issue, S.UNDER_REVIEW, admin)
    with pytest.raises(ValidationError):
        services.change_status(issue, S.IN_PROGRESS, staff)  # skips ASSIGNED: not in the table
    issue = services.assign(issue, staff, admin)
    assert issue.status == S.ASSIGNED
    issue = services.change_status(issue, S.IN_PROGRESS, staff)
    with pytest.raises(ValidationError):
        services.submit_for_verification(issue, staff)  # no evidence
    with pytest.raises(ValidationError):
        services.change_status(issue, S.RESOLVED, admin)  # not submitted
    add_evidence(issue, staff)
    issue = services.submit_for_verification(issue, staff)
    issue = services.change_status(issue, S.RESOLVED, admin)
    assert issue.resolved_at and not issue.verification_pending
    issue = services.confirm_resolution(issue, citizen)
    assert issue.reporter_confirmed is True
    statuses = list(issue.events.filter(kind="status").values_list("new_status", flat=True))
    assert statuses == [S.REPORTED, S.UNDER_REVIEW, S.ASSIGNED, S.IN_PROGRESS, S.RESOLVED]
    assert Notification.objects.filter(user=citizen).count() >= 4
    assert Notification.objects.filter(user=staff).exists()


def test_reporter_can_reopen_resolved_issue(make_user, make_issue):
    admin, staff = make_user("ADMIN"), make_user("STAFF")
    issue = make_issue()
    services.change_status(issue, S.UNDER_REVIEW, admin)
    services.assign(issue, staff, admin)
    services.change_status(issue, S.IN_PROGRESS, staff)
    add_evidence(issue, staff)
    services.submit_for_verification(issue, staff)
    issue = services.change_status(issue, S.RESOLVED, admin)
    with pytest.raises(PermissionDenied):
        services.change_status(issue, S.UNDER_REVIEW, make_user())  # someone else
    issue = services.change_status(issue, S.UNDER_REVIEW, issue.reporter, "Still leaking")
    assert issue.status == S.UNDER_REVIEW and issue.resolved_at is None and issue.reporter_confirmed is False


def test_reassign_closes_old_assignment(make_user, make_issue):
    admin, s1, s2 = make_user("ADMIN"), make_user("STAFF"), make_user("STAFF")
    issue = services.change_status(make_issue(), S.UNDER_REVIEW, admin)
    services.assign(issue, s1, admin)
    issue = services.assign(issue, s2, admin)
    old, new = IssueAssignment.objects.get(staff=s1), IssueAssignment.objects.get(staff=s2)
    assert old.ended_at is not None and new.ended_at is None
    assert issue.assigned_to == s2
    assert Notification.objects.filter(user=s2).exists()


def test_events_are_append_only(make_issue):
    event = make_issue().events.first()
    with pytest.raises(ValueError):
        event.save()
    with pytest.raises(ValueError):
        event.delete()


# ---------- votes ----------

def test_vote_only_once(client, make_user, make_issue):
    issue, voter = make_issue(), make_user()
    assert services.vote(issue, voter) is True
    assert services.vote(issue, voter) is False
    client.force_login(voter)
    client.post(f"/issues/{issue.tracking_code}/vote/")
    assert IssueVote.objects.filter(issue=issue).count() == 1


def test_staff_cannot_vote(make_user, make_issue):
    with pytest.raises(PermissionDenied):
        services.vote(make_issue(), make_user("STAFF"))
