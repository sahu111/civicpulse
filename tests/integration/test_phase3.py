import pytest
from django.core.files.uploadedfile import SimpleUploadedFile

from issues import services
from issues.models import Issue, IssueMedia, IssueVote
from notifications.models import Notification
from tests.conftest import ISSUE_DATA, png_upload

S = Issue.Status
pytestmark = pytest.mark.django_db


def act(client, issue, action, **data):
    return client.post(f"/issues/{issue.tracking_code}/action/", {"action": action, **data})


def test_full_flow_through_http(client, make_user):
    citizen, admin, staff = make_user(), make_user("ADMIN"), make_user("STAFF")

    client.force_login(citizen)
    page = client.get("/issues/new/")
    assert page.status_code == 200 and b'id="picker"' in page.content
    client.post("/issues/new/", {**ISSUE_DATA, "photo": png_upload()})
    issue = Issue.objects.get()

    client.force_login(admin)
    act(client, issue, "review")
    act(client, issue, "assign", staff=staff.pk)
    issue.refresh_from_db()
    assert issue.status == S.ASSIGNED

    client.force_login(staff)
    act(client, issue, "start")
    act(client, issue, "progress", note="Crew on site")
    act(client, issue, "submit")  # refused: no evidence yet
    issue.refresh_from_db()
    assert issue.status == S.IN_PROGRESS and not issue.verification_pending
    act(client, issue, "evidence", photo=png_upload("done.png"))
    act(client, issue, "submit")
    issue.refresh_from_db()
    assert issue.verification_pending

    client.force_login(admin)
    act(client, issue, "resolve", note="Checked")
    client.force_login(citizen)
    act(client, issue, "confirm")
    issue.refresh_from_db()
    assert issue.status == S.RESOLVED and issue.reporter_confirmed is True
    kinds = list(issue.events.values_list("kind", flat=True))
    assert {"status", "assign", "progress", "evidence", "verify"} <= set(kinds)
    assert issue.media.filter(kind="evidence").count() == 1


@pytest.fixture
def in_progress(make_user, make_issue):
    admin, staff = make_user("ADMIN"), make_user("STAFF")
    issue = services.change_status(make_issue(), S.UNDER_REVIEW, admin)
    services.assign(issue, staff, admin)
    issue = services.change_status(issue, S.IN_PROGRESS, staff)
    return issue, admin, staff


def test_fake_and_oversized_evidence_rejected(client, in_progress):
    issue, _, staff = in_progress
    client.force_login(staff)
    exe = SimpleUploadedFile("photo.jpg", b"MZ\x90\x00\x03" + b"\x00" * 200, content_type="image/jpeg")
    r = act(client, issue, "evidence", photo=exe)
    assert IssueMedia.objects.count() == 0
    big = SimpleUploadedFile("big.png", b"\x89PNG" + b"\x00" * (5 * 1024 * 1024 + 1), content_type="image/png")
    r = client.post(f"/issues/{issue.tracking_code}/action/", {"action": "evidence", "photo": big}, follow=True)
    assert IssueMedia.objects.count() == 0
    assert b"5 MB or smaller" in r.content


def test_send_back_clears_pending(in_progress):
    issue, admin, staff = in_progress
    IssueMedia.objects.create(issue=issue, file=png_upload(), media_type="image/png", kind="evidence", uploaded_by=staff)
    services.submit_for_verification(issue, staff)
    issue = services.send_back(issue, admin, "Bench still broken")
    assert issue.status == S.IN_PROGRESS and not issue.verification_pending
    assert Notification.objects.filter(user=staff, message__contains="sent back").exists()


def test_other_staff_cannot_add_progress(client, make_user, in_progress):
    issue, _, _ = in_progress
    client.force_login(make_user("STAFF"))
    assert act(client, issue, "progress", note="hi").status_code == 404


def test_request_info_notifies_reporter(make_user, make_issue):
    admin, issue = make_user("ADMIN"), make_issue()
    services.request_info(issue, admin, "Which side of the road?")
    assert Notification.objects.filter(user=issue.reporter, message__contains="more information").exists()


def test_merge_moves_votes_without_duplicates(make_user, make_issue):
    admin, a, b, c = make_user("ADMIN"), make_user(), make_user(), make_user()
    target, dup = make_issue(), make_issue()
    services.vote(target, a)
    services.vote(dup, a)  # already supports target: must not double up
    services.vote(dup, b)
    services.merge_issues(dup, target.tracking_code, admin)
    dup.refresh_from_db()
    assert dup.status == S.REJECTED and dup.merged_into == target
    voters = set(IssueVote.objects.filter(issue=target).values_list("user_id", flat=True))
    assert voters == {a.id, b.id, dup.reporter_id}
    assert not IssueVote.objects.filter(issue=dup).exists()


def test_map_shows_only_permitted_issues(client, make_user, make_issue):
    admin, staff = make_user("ADMIN"), make_user("STAFF")
    citizen = make_user()
    own = make_issue(reporter=citizen)
    other = make_issue()
    rejected = services.change_status(make_issue(), S.REJECTED, admin, "Not a city matter")
    services.assign(services.change_status(other, S.UNDER_REVIEW, admin), staff, admin)

    def codes(user):
        client.force_login(user)
        return {i["code"]: i["url"] for i in client.get("/api/map/").json()["issues"]}

    assert set(codes(admin)) == {own.tracking_code, other.tracking_code, rejected.tracking_code}
    assert set(codes(staff)) == {other.tracking_code}
    c = codes(citizen)
    assert set(c) == {own.tracking_code, other.tracking_code}
    assert c[own.tracking_code] and c[other.tracking_code] is None  # can only open own report


def test_map_requires_login(client):
    assert client.get("/api/map/").status_code == 302
