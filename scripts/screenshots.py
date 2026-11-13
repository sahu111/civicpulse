"""Capture presentation screenshots of each role's main pages from a running dev server.

Usage: start the server, run seed_demo with DEMO_PASSWORD set, then
    DEMO_PASSWORD=... python scripts/screenshots.py [base_url]
"""
import os
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8001"
PASSWORD = os.environ["DEMO_PASSWORD"]
OUT = Path(__file__).resolve().parent.parent / "docs" / "screenshots"

PAGES = {
    None: [("01-landing", "/"), ("02-login", "/login/")],
    "citizen1@civicpulse.test": [
        ("10-citizen-dashboard", "/dashboard/"), ("11-citizen-report-form", "/issues/new/"),
        ("12-citizen-my-reports", "/issues/mine/"), ("13-citizen-community", "/issues/"),
        ("14-citizen-map", "/map/"), ("15-citizen-notifications", "/notifications/"),
    ],
    "admin@civicpulse.test": [
        ("20-admin-overview", "/admin-panel/"), ("21-admin-all-issues", "/issues/"),
        ("22-admin-issue-detail", "/issues/{pending}/"), ("23-admin-staff", "/admin-panel/staff/"),
        ("24-admin-map", "/map/"),
    ],
    "staff1@civicpulse.test": [("30-staff-tasks", "/tasks/"), ("31-staff-task-detail", "/issues/{progress}/")],
}


def main():
    sys.path.insert(0, str(OUT.parent.parent))
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.dev")
    import django
    django.setup()
    from issues.models import Issue
    codes = {
        "pending": Issue.objects.filter(verification_pending=True).first().tracking_code,
        "progress": Issue.objects.filter(status="IN_PROGRESS", verification_pending=False).first().tracking_code,
    }
    OUT.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch()
        for email, pages in PAGES.items():
            ctx = browser.new_context(viewport={"width": 1366, "height": 860})
            page = ctx.new_page()
            if email:
                page.goto(f"{BASE}/login/")
                page.fill("#id_username", email)
                page.fill("#id_password", PASSWORD)
                page.click("button:has-text('Sign in')")
                page.wait_for_load_state("networkidle")
            for name, path in pages:
                page.goto(BASE + path.format(**codes))
                page.wait_for_load_state("networkidle")
                page.wait_for_timeout(600)
                page.screenshot(path=OUT / f"{name}.png", full_page=True)
            ctx.close()
        mobile = browser.new_context(viewport={"width": 390, "height": 844}, is_mobile=True)
        page = mobile.new_page()
        page.goto(f"{BASE}/")
        page.screenshot(path=OUT / "40-mobile-landing.png", full_page=True)
        browser.close()
    print(f"Saved screenshots to {OUT}")


if __name__ == "__main__":
    main()
