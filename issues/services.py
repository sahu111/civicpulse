"""Business rules for the issue lifecycle. Every multi-write action runs in one transaction."""
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone

from accounts.permissions import (
    CITIZEN, can_update_issue, can_view_issue, community_issues, has_role, is_admin, is_reporter,
)
from notifications.services import notify, notify_admins

from . import smart
from .models import Category, Issue, IssueAssignment, IssueEvent, IssueMedia, IssueVote, TrackingCounter

S = Issue.Status
E = IssueEvent.Kind

# (from, to) -> who may make the move. Anything not listed is refused.
TRANSITIONS = {
    (S.REPORTED, S.UNDER_REVIEW): "admin",
    (S.REPORTED, S.REJECTED): "admin",
    (S.UNDER_REVIEW, S.REJECTED): "admin",
    (S.UNDER_REVIEW, S.ASSIGNED): "admin",
    (S.ASSIGNED, S.IN_PROGRESS): "assigned_staff",
    (S.IN_PROGRESS, S.RESOLVED): "admin",
    (S.RESOLVED, S.UNDER_REVIEW): "reporter",
}


def _allowed(rule, actor, issue):
    if rule == "admin":
        return is_admin(actor)
    if rule == "assigned_staff":
        return can_update_issue(actor, issue)
    if rule == "reporter":
        return is_reporter(actor, issue)
    return False


def _name(user):
    return user.get_full_name() or user.username


def next_tracking_code():
    """CP-YYMM-0001. Must run inside the caller's transaction; the counter row is locked."""
    period = f"{timezone.localtime():%y%m}"
    counter, _ = TrackingCounter.objects.select_for_update().get_or_create(period=period)
    counter.value += 1
    counter.save(update_fields=["value"])
    return f"CP-{period}-{counter.value:04d}"


@transaction.atomic
def create_issue(reporter, data, photo=None, photo_mime="", notes=""):
    if not has_role(reporter, CITIZEN):
        raise PermissionDenied("Only citizens can submit reports.")
    issue = Issue(reporter=reporter, tracking_code=next_tracking_code(), **data)
    issue.suggested_category = smart.suggest_category(issue.title, issue.description)[0]
    issue.suggested_priority, issue.priority_reason = smart.recommend_priority(
        issue.category, issue.title, issue.description
    )
    issue.priority = issue.suggested_priority  # starting point; admins can change it
    issue.full_clean(exclude=["tracking_code"])
    issue.save()
    if photo:
        IssueMedia.objects.create(
            issue=issue, file=photo, media_type=photo_mime,
            kind=IssueMedia.Kind.REPORT, uploaded_by=reporter,
        )
    IssueEvent.objects.create(issue=issue, actor=reporter, kind=E.STATUS, new_status=S.REPORTED)
    if notes.strip():
        IssueEvent.objects.create(issue=issue, actor=reporter, kind=E.COMMENT, note=notes.strip())
    notify_admins(issue, f"New report {issue.tracking_code}: {issue.title}")
    return issue


def change_status(issue, to_status, actor, note=""):
    """The only way to change Issue.status. Validates, saves, logs and notifies atomically."""
    note = (note or "").strip()
    with transaction.atomic():
        issue = Issue.objects.select_for_update().get(pk=issue.pk)
        frm = issue.status
        rule = TRANSITIONS.get((frm, to_status))
        if rule is None:
            raise ValidationError(
                f"A report cannot move from {S(frm).label} to {S(to_status).label}."
            )
        if not _allowed(rule, actor, issue):
            raise PermissionDenied("You are not allowed to make this change.")
        if to_status == S.REJECTED and not note:
            raise ValidationError("A written reason is required to reject a report.")
        if to_status == S.ASSIGNED and not issue.assigned_to_id:
            raise ValidationError("Choose a staff member first.")
        if to_status == S.RESOLVED and not issue.verification_pending:
            raise ValidationError("Staff have not submitted this work for verification yet.")
        if frm == S.RESOLVED and not note:
            raise ValidationError("Please say what is still wrong.")

        issue.status = to_status
        if to_status == S.RESOLVED:
            issue.resolved_at = timezone.now()
            issue.verification_pending = False
            issue.reporter_confirmed = None
        if frm == S.RESOLVED:
            issue.resolved_at = None
            issue.reporter_confirmed = False
        issue.save()
        IssueEvent.objects.create(
            issue=issue, actor=actor, kind=E.STATUS, old_status=frm, new_status=to_status, note=note
        )
        msg = f"{issue.tracking_code} is now {issue.get_status_display()}."
        notify(issue.reporter, issue, msg, exclude=actor)
        notify(issue.assigned_to, issue, msg, exclude=actor)
        if rule != "admin":
            notify_admins(issue, msg, exclude=actor)
    return issue


def assign(issue, staff, actor):
    """Assign or reassign. Closes the open assignment and opens a new one."""
    if not is_admin(actor):
        raise PermissionDenied("Only admins can assign reports.")
    if staff is None or not has_role(staff, "STAFF"):
        raise ValidationError("Choose an active staff member.")
    with transaction.atomic():
        issue = Issue.objects.select_for_update().get(pk=issue.pk)
        if issue.status not in (S.UNDER_REVIEW, S.ASSIGNED, S.IN_PROGRESS):
            raise ValidationError("Only reports under review or in work can be assigned.")
        if issue.assigned_to_id == staff.id:
            raise ValidationError("This report is already assigned to that staff member.")
        old = issue.assigned_to
        IssueAssignment.objects.filter(issue=issue, ended_at__isnull=True).update(ended_at=timezone.now())
        IssueAssignment.objects.create(issue=issue, staff=staff, assigned_by=actor)
        issue.assigned_to = staff
        issue.save(update_fields=["assigned_to", "updated_at"])
        note = f"Reassigned from {_name(old)} to {_name(staff)}" if old else f"Assigned to {_name(staff)}"
        IssueEvent.objects.create(issue=issue, actor=actor, kind=E.ASSIGN, note=note)
        notify(staff, issue, f"You have been assigned {issue.tracking_code}: {issue.title}")
        if old:
            notify(old, issue, f"{issue.tracking_code} has been reassigned to another staff member.")
        if issue.status == S.UNDER_REVIEW:
            issue = change_status(issue, S.ASSIGNED, actor)
    return issue


@transaction.atomic
def set_priority(issue, priority, actor):
    if not is_admin(actor):
        raise PermissionDenied("Only admins can change priority.")
    if priority not in Issue.Priority.values:
        raise ValidationError("Choose a valid priority.")
    issue = Issue.objects.select_for_update().get(pk=issue.pk)
    if issue.priority == priority:
        return issue
    old = issue.get_priority_display()
    issue.priority = priority
    issue.save(update_fields=["priority", "updated_at"])
    IssueEvent.objects.create(
        issue=issue, actor=actor, kind=E.PRIORITY,
        note=f"Priority changed from {old} to {issue.get_priority_display()}",
    )
    return issue


@transaction.atomic
def add_comment(issue, actor, note):
    note = (note or "").strip()
    if not can_view_issue(actor, issue):
        raise PermissionDenied
    if not note:
        raise ValidationError("Write a comment first.")
    if len(note) > 1000:
        raise ValidationError("Comments can be at most 1000 characters.")
    IssueEvent.objects.create(issue=issue, actor=actor, kind=E.COMMENT, note=note)
    msg = f"New comment on {issue.tracking_code} from {_name(actor)}."
    notify(issue.reporter, issue, msg, exclude=actor)
    notify(issue.assigned_to, issue, msg, exclude=actor)


@transaction.atomic
def confirm_resolution(issue, actor):
    issue = Issue.objects.select_for_update().get(pk=issue.pk)
    if not is_reporter(actor, issue):
        raise PermissionDenied
    if issue.status != S.RESOLVED or issue.reporter_confirmed is not None:
        raise ValidationError("Only a newly resolved report can be confirmed.")
    issue.reporter_confirmed = True
    issue.save(update_fields=["reporter_confirmed", "updated_at"])
    IssueEvent.objects.create(issue=issue, actor=actor, kind=E.VERIFY, note="Reporter confirmed the fix.")
    notify_admins(issue, f"{issue.tracking_code} was confirmed fixed by the reporter.")
    return issue


@transaction.atomic
def submit_for_verification(issue, actor):
    issue = Issue.objects.select_for_update().get(pk=issue.pk)
    if not can_update_issue(actor, issue):
        raise PermissionDenied
    if issue.status != S.IN_PROGRESS or issue.verification_pending:
        raise ValidationError("Only work in progress can be submitted for verification.")
    if not issue.media.filter(kind=IssueMedia.Kind.EVIDENCE).exists():
        raise ValidationError("Upload at least one evidence photo first.")
    issue.verification_pending = True
    issue.save(update_fields=["verification_pending", "updated_at"])
    IssueEvent.objects.create(issue=issue, actor=actor, kind=E.VERIFY, note="Work submitted for verification.")
    notify_admins(issue, f"{issue.tracking_code} is ready for verification.")
    return issue


def vote(issue, user):
    """Support a community report once. Returns False if the user already supported it."""
    if not has_role(user, CITIZEN):
        raise PermissionDenied
    if not community_issues().filter(pk=issue.pk).exists():
        raise ValidationError("This report cannot be supported.")
    try:
        with transaction.atomic():
            IssueVote.objects.create(issue=issue, user=user)
    except IntegrityError:
        return False
    return True


@transaction.atomic
def request_info(issue, actor, note):
    """Admin asks the reporter for more details."""
    note = (note or "").strip()
    if not is_admin(actor):
        raise PermissionDenied
    if not note:
        raise ValidationError("Write what information you need.")
    if not issue.is_open:
        raise ValidationError("This report is closed.")
    IssueEvent.objects.create(issue=issue, actor=actor, kind=E.INFO, note=note)
    notify(issue.reporter, issue, f"The city needs more information about {issue.tracking_code}: {note[:150]}")


def merge_issues(duplicate, target_code, actor):
    """Close a duplicate as REJECTED and move its supporters to the target without double votes."""
    if not is_admin(actor):
        raise PermissionDenied
    with transaction.atomic():
        dup = Issue.objects.select_for_update().get(pk=duplicate.pk)
        target = Issue.objects.select_for_update().filter(
            tracking_code=(target_code or "").strip().upper()
        ).first()
        if target is None or target.pk == dup.pk:
            raise ValidationError("Enter the tracking code of a different report.")
        if target.merged_into_id or target.status == S.REJECTED:
            raise ValidationError("You cannot merge into a rejected or merged report.")
        if dup.status not in (S.REPORTED, S.UNDER_REVIEW):
            raise ValidationError("Only new or reviewed reports can be merged.")
        supporters = set(IssueVote.objects.filter(issue=target).values_list("user_id", flat=True))
        moved = 0
        for v in IssueVote.objects.filter(issue=dup):
            if v.user_id in supporters:
                v.delete()
            else:
                v.issue = target
                v.save(update_fields=["issue"])
                supporters.add(v.user_id)
                moved += 1
        if dup.reporter_id not in supporters and dup.reporter_id != target.reporter_id:
            IssueVote.objects.create(issue=target, user_id=dup.reporter_id)
            moved += 1
        dup.merged_into = target
        dup.save(update_fields=["merged_into", "updated_at"])
        change_status(dup, S.REJECTED, actor, f"Merged into {target.tracking_code} as a duplicate.")
        IssueEvent.objects.create(
            issue=target, actor=actor, kind=E.MERGE,
            note=f"{dup.tracking_code} merged into this report. {moved} supporter(s) moved.",
        )
    return target


@transaction.atomic
def send_back(issue, actor, note):
    """Admin refuses the staff submission; work stays in progress."""
    note = (note or "").strip()
    if not is_admin(actor):
        raise PermissionDenied
    issue = Issue.objects.select_for_update().get(pk=issue.pk)
    if issue.status != S.IN_PROGRESS or not issue.verification_pending:
        raise ValidationError("Nothing is waiting for verification.")
    if not note:
        raise ValidationError("Say what still needs to be done.")
    issue.verification_pending = False
    issue.save(update_fields=["verification_pending", "updated_at"])
    IssueEvent.objects.create(issue=issue, actor=actor, kind=E.VERIFY, note=f"Sent back to staff: {note}")
    notify(issue.assigned_to, issue, f"{issue.tracking_code} was sent back: {note[:150]}")
    return issue


@transaction.atomic
def add_progress(issue, actor, note):
    note = (note or "").strip()
    issue = Issue.objects.select_for_update().get(pk=issue.pk)
    if not can_update_issue(actor, issue):
        raise PermissionDenied
    if issue.status not in (S.ASSIGNED, S.IN_PROGRESS):
        raise ValidationError("Progress notes can only be added to active tasks.")
    if not note or len(note) > 1000:
        raise ValidationError("Write a note of up to 1000 characters.")
    IssueEvent.objects.create(issue=issue, actor=actor, kind=E.PROGRESS, note=note)
    notify(issue.reporter, issue, f"Progress update on {issue.tracking_code}.")


@transaction.atomic
def add_evidence(issue, actor, photo, mime):
    """Attach a completion photo. The caller must already have run validate_image()."""
    issue = Issue.objects.select_for_update().get(pk=issue.pk)
    if not can_update_issue(actor, issue):
        raise PermissionDenied
    if issue.status != S.IN_PROGRESS:
        raise ValidationError("Start work before uploading evidence.")
    IssueMedia.objects.create(issue=issue, file=photo, media_type=mime,
                              kind=IssueMedia.Kind.EVIDENCE, uploaded_by=actor)
    IssueEvent.objects.create(issue=issue, actor=actor, kind=E.EVIDENCE, note="Evidence photo uploaded.")


@transaction.atomic
def set_category(issue, category, actor):
    if not is_admin(actor):
        raise PermissionDenied
    if category not in Category.values:
        raise ValidationError("Choose a valid category.")
    issue = Issue.objects.select_for_update().get(pk=issue.pk)
    if issue.category == category:
        return issue
    old = issue.get_category_display()
    issue.category = category
    issue.save(update_fields=["category", "updated_at"])
    IssueEvent.objects.create(issue=issue, actor=actor, kind=E.INFO,
                              note=f"Category changed from {old} to {issue.get_category_display()}")
    return issue
