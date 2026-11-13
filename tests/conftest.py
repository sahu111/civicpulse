import io
from decimal import Decimal

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from PIL import Image

from accounts.models import User
from issues import services
from issues.models import IssueMedia

PASSWORD = "Test-pass-9271"
ISSUE_DATA = {
    "title": "Large pothole near school",
    "description": "Deep pothole causing traffic problems every morning.",
    "category": "ROADS",
    "location_text": "Demo street (fictional)",
    "latitude": Decimal("12.500000"),
    "longitude": Decimal("77.500000"),
}


@pytest.fixture(autouse=True)
def media_tmp(settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path


@pytest.fixture(autouse=True)
def clear_rate_limits():
    from django.core.cache import cache

    cache.clear()
    yield
    cache.clear()


@pytest.fixture
def make_user(db):
    counter = {"n": 0}

    def _make(role="CITIZEN"):
        counter["n"] += 1
        n = counter["n"]
        return User.objects.create_user(
            username=f"user{n}", email=f"user{n}@example.test", password=PASSWORD, role=role
        )

    return _make


@pytest.fixture
def make_issue(make_user):
    def _make(reporter=None, **overrides):
        return services.create_issue(reporter or make_user(), {**ISSUE_DATA, **overrides})

    return _make


def png_upload(name="photo.png"):
    buf = io.BytesIO()
    Image.new("RGB", (8, 8), "red").save(buf, "PNG")
    return SimpleUploadedFile(name, buf.getvalue(), content_type="image/png")


def add_evidence(issue, staff):
    IssueMedia.objects.create(issue=issue, file=png_upload(), media_type="image/png",
                              kind=IssueMedia.Kind.EVIDENCE, uploaded_by=staff)
