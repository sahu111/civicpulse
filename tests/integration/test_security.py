import pytest

from issues.models import Issue
from tests.conftest import ISSUE_DATA, PASSWORD

pytestmark = pytest.mark.django_db


def test_login_rate_limit_per_email(client, make_user):
    user = make_user()
    # Limits use fixed one-minute windows, so allow for one window rollover during the test.
    codes = [client.post("/login/", {"username": user.email, "password": "wrong"}).status_code for _ in range(12)]
    assert 429 in codes and codes[:5] == [200] * 5
    assert client.post("/login/", {"username": user.email, "password": PASSWORD}).status_code == 429


def test_register_rate_limit(client):
    statuses = []
    for i in range(6):
        statuses.append(client.post("/register/", {
            "first_name": "A", "username": f"x{i}", "email": f"x{i}@example.test",
            "password1": PASSWORD, "password2": PASSWORD,
        }).status_code)
        client.logout()
    assert statuses[:5] == [302] * 5 and statuses[5] == 429


def test_double_submit_creates_one_report(client, make_user):
    client.force_login(make_user())
    first = client.post("/issues/new/", ISSUE_DATA)
    second = client.post("/issues/new/", ISSUE_DATA)
    assert Issue.objects.count() == 1
    assert first.url == second.url  # both land on the same report


def test_security_headers(client):
    r = client.get("/")
    assert "default-src 'self'" in r["Content-Security-Policy"]
    assert "frame-ancestors 'none'" in r["Content-Security-Policy"]
    assert r["X-Frame-Options"] == "DENY"
    assert r["X-Content-Type-Options"] == "nosniff"
    assert r["Referrer-Policy"] == "same-origin"


def test_csrf_enforced_on_post(make_user):
    from django.test import Client

    c = Client(enforce_csrf_checks=True)
    c.force_login(make_user())
    assert c.post("/issues/new/", ISSUE_DATA).status_code == 403
    assert Issue.objects.count() == 0


def test_media_not_public(client, make_user):
    client.force_login(make_user())
    from tests.conftest import png_upload

    client.post("/issues/new/", {**ISSUE_DATA, "photo": png_upload()})
    issue = Issue.objects.get()
    media = issue.media.get()
    url = f"/issues/{issue.tracking_code}/media/{media.pk}/"
    assert client.get(url).status_code == 200
    client.force_login(make_user())  # another citizen
    assert client.get(url).status_code == 404
    client.logout()
    assert client.get(f"/media/{media.file.name}").status_code == 404  # no public media URL


def test_prod_settings_are_hardened():
    from config.settings import prod

    assert prod.DEBUG is False
    assert prod.SESSION_COOKIE_SECURE and prod.CSRF_COOKIE_SECURE and prod.SECURE_SSL_REDIRECT
