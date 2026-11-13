from decimal import Decimal

import pytest

from issues import smart
from issues.models import Issue
from issues.services import change_status

pytestmark = pytest.mark.django_db


def test_category_suggestion_title_weighs_double():
    assert smart.suggest_category("Huge pothole on the road")[0] == "ROADS"
    # title says garbage (x2) vs one water word in description
    assert smart.suggest_category("Garbage dump", "near the water tank")[0] == "SANITATION"
    assert smart.suggest_category("Hello there")[0] == ""


def test_priority_recommendation_explains_itself():
    prio, reasons = smart.recommend_priority("ELECTRICITY", "Exposed live wire near school")
    assert prio == "HIGH"
    assert any('"live wire"' in r for r in reasons) and any('"school"' in r for r in reasons)
    prio, reasons = smart.recommend_priority("OTHER", "Minor graffiti on wall")
    assert prio == "LOW" and reasons[-1].startswith("Total -2 points")
    assert smart.recommend_priority("PARKS", "Bench broken", supporters=5)[1][-2].startswith("5 people")


def test_jaccard_and_haversine():
    assert smart.jaccard("deep pothole road", "pothole road deep") == 1.0
    assert smart.jaccard("", "anything") == 0.0
    assert 1100 < smart.haversine_m(21.0, 79.0, 21.01, 79.0) < 1120


def test_duplicates_near_and_similar_only(make_user, make_issue):
    admin = make_user("ADMIN")
    near = make_issue()
    make_issue(latitude=Decimal("12.520000"))  # about 2.2 km away
    make_issue(title="Tree fell on park bench", description="Large branch blocking the park path", category="PARKS")
    closed = make_issue()
    change_status(closed, Issue.Status.REJECTED, admin, "dup")
    found = smart.find_duplicates(
        "Pothole near school gate", "Deep pothole causing traffic problems", "ROADS",
        12.5005, 77.5005, Issue.objects.all(),
    )
    assert [d["issue"].pk for d in found] == [near.pk]


def test_hotspots_threshold(make_issue):
    for _ in range(3):
        make_issue()
    make_issue(latitude=Decimal("13.500000"))
    spots = smart.hotspots(Issue.objects.all())
    assert len(spots) == 1 and spots[0]["count"] == 3


def test_new_issue_stores_recommendations(make_issue):
    issue = make_issue()
    assert issue.suggested_category == "ROADS"
    assert issue.suggested_priority == issue.priority == "MEDIUM"  # roads 2 + school 2
    assert issue.priority_reason
