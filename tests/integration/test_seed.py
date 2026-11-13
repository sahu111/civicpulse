import pytest
from django.core.management import call_command

from accounts.models import User
from issues.models import Issue

pytestmark = pytest.mark.django_db


def test_seed_demo_creates_every_role_and_status(capsys):
    call_command("seed_demo")
    assert set(User.objects.values_list("role", flat=True)) == {"ADMIN", "STAFF", "CITIZEN"}
    assert set(Issue.objects.values_list("status", flat=True)) == set(Issue.Status.values)
    assert Issue.objects.filter(verification_pending=True).exists()
    out = capsys.readouterr().out
    assert "admin@civicpulse.test" in out and "fictional" in Issue.objects.first().location_text
    call_command("seed_demo")  # safe to run twice
    assert Issue.objects.count() == 8
