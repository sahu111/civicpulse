import uuid

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import Q
from django.utils import timezone

User = settings.AUTH_USER_MODEL


class Category(models.TextChoices):
    ROADS = "ROADS", "Roads and potholes"
    STREETLIGHT = "STREETLIGHT", "Street lights"
    WATER = "WATER", "Water supply"
    DRAINAGE = "DRAINAGE", "Drainage and sewage"
    SANITATION = "SANITATION", "Garbage and sanitation"
    ELECTRICITY = "ELECTRICITY", "Electricity"
    PARKS = "PARKS", "Parks and public spaces"
    OTHER = "OTHER", "Other"


EXT_FOR_MIME = {"image/jpeg": "jpg", "image/png": "png", "image/webp": "webp"}


def safe_upload_path(instance, filename):
    """Ignore the uploaded name entirely: random UUID plus an extension from the verified type."""
    ext = EXT_FOR_MIME.get(instance.media_type, "bin")
    return f"issues/{timezone.now():%Y/%m}/{uuid.uuid4().hex}.{ext}"


class Issue(models.Model):
    class Status(models.TextChoices):
        REPORTED = "REPORTED", "Reported"
        UNDER_REVIEW = "UNDER_REVIEW", "Under review"
        ASSIGNED = "ASSIGNED", "Assigned"
        IN_PROGRESS = "IN_PROGRESS", "In progress"
        RESOLVED = "RESOLVED", "Resolved"
        REJECTED = "REJECTED", "Rejected"

    class Priority(models.TextChoices):
        LOW = "LOW", "Low"
        MEDIUM = "MEDIUM", "Medium"
        HIGH = "HIGH", "High"

    OPEN_STATUSES = [Status.REPORTED, Status.UNDER_REVIEW, Status.ASSIGNED, Status.IN_PROGRESS]

    tracking_code = models.CharField(max_length=20, unique=True, editable=False)
    title = models.CharField(max_length=100)
    description = models.TextField(max_length=1000)
    category = models.CharField(max_length=20, choices=Category.choices, db_index=True)
    priority = models.CharField(max_length=6, choices=Priority.choices, default=Priority.MEDIUM)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.REPORTED, db_index=True)
    latitude = models.DecimalField(
        max_digits=9, decimal_places=6, validators=[MinValueValidator(-90), MaxValueValidator(90)]
    )
    longitude = models.DecimalField(
        max_digits=9, decimal_places=6, validators=[MinValueValidator(-180), MaxValueValidator(180)]
    )
    location_text = models.CharField(max_length=200)
    reporter = models.ForeignKey(User, on_delete=models.PROTECT, related_name="reported_issues")
    assigned_to = models.ForeignKey(
        User, null=True, blank=True, on_delete=models.SET_NULL, related_name="tasks"
    )
    merged_into = models.ForeignKey("self", null=True, blank=True, on_delete=models.SET_NULL)
    verification_pending = models.BooleanField(default=False)
    reporter_confirmed = models.BooleanField(null=True, blank=True)
    suggested_category = models.CharField(max_length=20, blank=True)
    suggested_priority = models.CharField(max_length=6, blank=True)
    priority_reason = models.JSONField(default=list, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)
    resolved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["status", "priority"]),
            models.Index(fields=["assigned_to", "status"]),
            models.Index(fields=["latitude", "longitude"]),
        ]
        constraints = [
            models.CheckConstraint(
                condition=Q(latitude__gte=-90, latitude__lte=90)
                & Q(longitude__gte=-180, longitude__lte=180),
                name="valid_coordinates",
            )
        ]

    def __str__(self):
        return f"{self.tracking_code} {self.title}"

    @property
    def is_open(self):
        return self.status in self.OPEN_STATUSES


class TrackingCounter(models.Model):
    """One row per YYMM period, locked while the next tracking number is taken."""

    period = models.CharField(max_length=4, primary_key=True)
    value = models.PositiveIntegerField(default=0)


class IssueEvent(models.Model):
    """Append-only history. Rows are never edited or deleted."""

    class Kind(models.TextChoices):
        STATUS = "status", "Status"
        ASSIGN = "assign", "Assignment"
        PRIORITY = "priority", "Priority"
        COMMENT = "comment", "Comment"
        PROGRESS = "progress", "Progress"
        EVIDENCE = "evidence", "Evidence"
        INFO = "info", "Information"
        VERIFY = "verify", "Verification"
        MERGE = "merge", "Merge"

    issue = models.ForeignKey(Issue, on_delete=models.CASCADE, related_name="events")
    actor = models.ForeignKey(User, on_delete=models.PROTECT, related_name="+")
    kind = models.CharField(max_length=10, choices=Kind.choices)
    old_status = models.CharField(max_length=12, blank=True)
    new_status = models.CharField(max_length=12, blank=True)
    note = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at", "pk"]

    def save(self, *args, **kwargs):
        if self.pk:
            raise ValueError("IssueEvent rows are append-only.")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValueError("IssueEvent rows are append-only.")

    def summary(self):
        labels = dict(Issue.Status.choices)
        if self.kind == self.Kind.STATUS:
            if not self.old_status:
                return "Report submitted"
            return f"{labels.get(self.old_status)} to {labels.get(self.new_status)}"
        return self.get_kind_display()


class IssueMedia(models.Model):
    class Kind(models.TextChoices):
        REPORT = "report", "Report photo"
        EVIDENCE = "evidence", "Completion evidence"

    issue = models.ForeignKey(Issue, on_delete=models.CASCADE, related_name="media")
    file = models.ImageField(upload_to=safe_upload_path)
    media_type = models.CharField(max_length=20)
    kind = models.CharField(max_length=10, choices=Kind.choices, default=Kind.REPORT)
    uploaded_by = models.ForeignKey(User, on_delete=models.PROTECT, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)


class IssueAssignment(models.Model):
    issue = models.ForeignKey(Issue, on_delete=models.CASCADE, related_name="assignments")
    staff = models.ForeignKey(User, on_delete=models.PROTECT, related_name="assignments")
    assigned_by = models.ForeignKey(User, on_delete=models.PROTECT, related_name="+")
    assigned_at = models.DateTimeField(auto_now_add=True)
    ended_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-assigned_at"]


class IssueVote(models.Model):
    issue = models.ForeignKey(Issue, on_delete=models.CASCADE, related_name="votes")
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="votes")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["issue", "user"], name="one_vote_per_user")]
