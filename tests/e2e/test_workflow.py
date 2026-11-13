"""End-to-end: citizen reports, admin assigns, staff completes, admin verifies, citizen confirms.

Runs a real Chromium browser against Django's live test server. Map tiles are blocked so the
test needs no internet (this also exercises the tile-failure fallback).
"""
import io
import os
import re

import pytest
from PIL import Image

from accounts.models import User
from tests.conftest import PASSWORD

os.environ.setdefault("DJANGO_ALLOW_ASYNC_UNSAFE", "true")  # Playwright's sync API runs an event loop

pytestmark = [pytest.mark.django_db(transaction=True), pytest.mark.e2e]


def png_bytes():
    buf = io.BytesIO()
    Image.new("RGB", (32, 32), "green").save(buf, "PNG")
    return buf.getvalue()


@pytest.fixture
def people():
    def make(username, role):
        return User.objects.create_user(username=username, email=f"{username}@example.test",
                                        password=PASSWORD, role=role, first_name=username.title())
    return make("citizen", "CITIZEN"), make("admin", "ADMIN"), make("staff", "STAFF")


def test_full_workflow_in_browser(live_server, page, people):
    citizen, admin, staff = people
    page.route(re.compile(r"https://tile\.openstreetmap\.org/.*"), lambda route: route.abort())
    page.set_viewport_size({"width": 1280, "height": 900})
    base = live_server.url

    def login(user):
        page.goto(f"{base}/login/")
        page.fill("#id_username", user.email)
        page.fill("#id_password", PASSWORD)
        with page.expect_navigation():
            page.click("button:has-text('Sign in')")

    def logout():
        with page.expect_navigation():
            page.click("button:has-text('Sign out')")

    def action(label):
        # every workflow button posts a form and redirects; wait for that navigation
        with page.expect_navigation():
            page.click(f"button:has-text('{label}')")

    # Citizen reports
    login(citizen)
    page.goto(f"{base}/issues/new/")
    page.fill("#id_title", "Water pipe burst near market")
    page.fill("#id_description", "Clean water is leaking onto the road since morning.")
    page.select_option("#id_category", "WATER")
    page.fill("#id_location_text", "Market road (fictional)")
    page.fill("#id_latitude", "12.500000")
    page.fill("#id_longitude", "77.500000")
    action("Submit report")
    code = re.search(r"/issues/(CP-\d{4}-\d{4})/", page.url).group(1)
    assert page.locator("text=Report submitted").first.is_visible()
    logout()

    # Admin reviews and assigns
    login(admin)
    page.goto(f"{base}/issues/{code}/")
    action("Start review")
    page.select_option("#staff", str(staff.pk))
    action("Assign")
    logout()

    # Staff works and submits evidence
    login(staff)
    page.goto(f"{base}/issues/{code}/")
    action("Start work")
    page.set_input_files("#evidence", files=[{"name": "done.png", "mimeType": "image/png", "buffer": png_bytes()}])
    action("Upload evidence")
    action("Submit for verification")
    logout()

    # Admin verifies
    login(admin)
    page.goto(f"{base}/issues/{code}/")
    action("Verify and resolve")
    logout()

    # Citizen confirms
    login(citizen)
    page.goto(f"{base}/issues/{code}/")
    action("Yes, it is fixed")
    assert page.locator("main .badge", has_text="Resolved").first.is_visible()
    assert page.locator("text=Reporter confirmed the fix.").is_visible()
