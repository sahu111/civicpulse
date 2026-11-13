import io
import secrets
from decimal import Decimal

from decouple import config
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management.base import BaseCommand
from django.db import transaction
from PIL import Image

from accounts.models import User
from issues import services
from issues.models import Issue, IssueMedia

S = Issue.Status

# All coordinates are FICTIONAL demo points around a made-up city centre.
DEMO_CENTRE = (Decimal("21.145800"), Decimal("79.088200"))

USERS = [
    ("admin", "admin@civicpulse.test", "Asha", "Admin", "ADMIN"),
    ("staff1", "staff1@civicpulse.test", "Ravi", "Field", "STAFF"),
    ("staff2", "staff2@civicpulse.test", "Meera", "Works", "STAFF"),
    ("citizen1", "citizen1@civicpulse.test", "Kiran", "Citizen", "CITIZEN"),
    ("citizen2", "citizen2@civicpulse.test", "Neha", "Resident", "CITIZEN"),
]

ISSUES = [
    ("Deep pothole outside primary school", "ROADS", S.REPORTED),
    ("Garbage not collected for a week", "SANITATION", S.REPORTED),
    ("Street light flickering all night", "STREETLIGHT", S.UNDER_REVIEW),
    ("Water pipe leaking on main road", "WATER", S.ASSIGNED),
    ("Open drain overflowing after rain", "DRAINAGE", S.IN_PROGRESS),
    ("Broken bench and swings in park", "PARKS", "PENDING"),
    ("Exposed live wire near bus stop", "ELECTRICITY", S.RESOLVED),
    ("Graffiti on private wall", "OTHER", S.REJECTED),
]


def _png():
    buf = io.BytesIO()
    Image.new("RGB", (64, 48), (79, 70, 229)).save(buf, "PNG")
    return SimpleUploadedFile("evidence.png", buf.getvalue(), content_type="image/png")


class Command(BaseCommand):
    help = "Create demo users (one per role and more) and issues in every status. Coordinates are fictional."

    @transaction.atomic
    def handle(self, *args, **opts):
        password = config("DEMO_PASSWORD", default="") or secrets.token_urlsafe(9)
        users = {}
        for username, email, first, last, role in USERS:
            u, _ = User.objects.get_or_create(
                email=email, defaults={"username": username, "first_name": first, "last_name": last, "role": role}
            )
            u.role, u.is_staff = role, role == "ADMIN"
            u.set_password(password)
            u.save()
            users[username] = u

        if Issue.objects.exists():
            self.stdout.write("Issues already exist; skipped creating demo issues.")
        else:
            self._issues(users)

        self.stdout.write(self.style.SUCCESS("\nDemo accounts (password shown once, not stored in code):"))
        for username, email, *_rest, role in USERS:
            self.stdout.write(f"  {role:<8} {email}")
        self.stdout.write(f"  Password: {password}\n")

    def _issues(self, u):
        admin, staff, citizens = u["admin"], u["staff1"], [u["citizen1"], u["citizen2"]]
        lat0, lng0 = DEMO_CENTRE
        for i, (title, cat, target) in enumerate(ISSUES):
            data = {
                "title": title, "category": cat,
                "description": f"{title}. Demo report created by seed_demo.",
                "location_text": f"Demo Ward {i + 1} (fictional location)",
                "latitude": lat0 + Decimal(i) * Decimal("0.004"),
                "longitude": lng0 - Decimal(i) * Decimal("0.003"),
            }
            issue = services.create_issue(citizens[i % 2], data)
            if target == S.REPORTED:
                continue
            issue = services.change_status(issue, S.UNDER_REVIEW, admin)
            if target == S.REJECTED:
                services.change_status(issue, S.REJECTED, admin, "Private property; not a city matter.")
                continue
            if target == S.UNDER_REVIEW:
                continue
            issue = services.assign(issue, staff, admin)
            if target == S.ASSIGNED:
                continue
            issue = services.change_status(issue, S.IN_PROGRESS, staff)
            if target == S.IN_PROGRESS:
                continue
            IssueMedia.objects.create(issue=issue, file=_png(), media_type="image/png",
                                      kind=IssueMedia.Kind.EVIDENCE, uploaded_by=staff)
            issue = services.submit_for_verification(issue, staff)
            if target == "PENDING":
                continue
            services.change_status(issue, S.RESOLVED, admin, "Checked on site.")
        services.vote(Issue.objects.get(title=ISSUES[0][0]), citizens[1])
        self.stdout.write(f"Created {len(ISSUES)} demo issues.")
