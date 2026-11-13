from django.conf import settings
from django.utils import timezone
from django.utils.decorators import method_decorator
from django_ratelimit.decorators import ratelimit
from datetime import timedelta
from django.contrib import messages
from django.http import JsonResponse
from django.urls import reverse
from django.contrib.auth import get_user_model
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import ValidationError
from django.db.models import Case, Count, IntegerField, Q, Value, When
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, redirect
from django.utils.http import url_has_allowed_host_and_scheme
from django.views import View
from django.views.generic import DetailView, FormView, ListView, TemplateView

from accounts.permissions import (
    ADMIN, CITIZEN, STAFF, RoleRequiredMixin, can_update_issue, can_view_issue,
    community_issues, has_role, home_url, is_admin, is_reporter,
)

from . import services, smart
from .csv_export import export_csv
from .forms import IssueForm
from .models import Category, Issue, IssueMedia
from .validators import validate_image

S = Issue.Status


def get_visible_issue(user, code):
    """Fetch by tracking code, then check access. Hidden issues look like they do not exist."""
    issue = get_object_or_404(
        Issue.objects.select_related("reporter", "assigned_to"), tracking_code=code
    )
    if not can_view_issue(user, issue):
        raise Http404
    return issue


class DashboardView(RoleRequiredMixin, TemplateView):
    template_name = "issues/dashboard.html"

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated and not has_role(request.user, CITIZEN):
            return redirect(home_url(request.user))
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        mine = Issue.objects.filter(reporter=self.request.user)
        stats = mine.aggregate(
            total=Count("id"),
            open=Count("id", filter=Q(status__in=Issue.OPEN_STATUSES)),
            resolved=Count("id", filter=Q(status=S.RESOLVED)),
        )
        return super().get_context_data(stats=stats, recent=mine[:5], **kwargs)


@method_decorator(ratelimit(key="user", rate=settings.RATE_REPORT, method="POST", block=True), name="post")
class IssueCreateView(RoleRequiredMixin, FormView):
    allowed_roles = (CITIZEN,)
    template_name = "issues/issue_form.html"
    form_class = IssueForm
    extra_context = {"map_center": settings.MAP_DEFAULT_CENTER}

    def form_valid(self, form):
        # Idempotency guard: the same title from the same person within 2 minutes is a double submit.
        recent = Issue.objects.filter(
            reporter=self.request.user, title__iexact=form.cleaned_data["title"],
            created_at__gte=timezone.now() - timedelta(minutes=2),
        ).first()
        if recent:
            messages.info(self.request, f"This report was already submitted as {recent.tracking_code}.")
            return redirect("issues:detail", code=recent.tracking_code)
        issue = services.create_issue(
            self.request.user, form.issue_data(),
            photo=form.cleaned_data.get("photo"), photo_mime=form.photo_mime,
            notes=form.cleaned_data.get("notes", ""),
        )
        messages.success(self.request, f"Report submitted. Your tracking code is {issue.tracking_code}.")
        return redirect("issues:detail", code=issue.tracking_code)


PRIORITY_ORDER = Case(
    When(priority="HIGH", then=Value(0)), When(priority="MEDIUM", then=Value(1)),
    default=Value(2), output_field=IntegerField(),
)
SORTS = {"newest": ["-created_at"], "oldest": ["created_at"],
         "priority": [PRIORITY_ORDER, "-created_at"], "votes": ["-vote_count", "-created_at"]}


def filter_issues(qs, g):
    """Search, filter and sort from GET params. Shared by the lists and the CSV export."""
    if q := g.get("q", "").strip():
        qs = qs.filter(Q(title__icontains=q) | Q(description__icontains=q)
                       | Q(tracking_code__icontains=q) | Q(location_text__icontains=q))
    for field, choices in (("status", S), ("category", Category), ("priority", Issue.Priority)):
        if (v := g.get(field)) in choices.values:
            qs = qs.filter(**{field: v})
    if g.get("sort") == "votes" and "vote_count" not in qs.query.annotations:
        qs = qs.annotate(vote_count=Count("votes"))
    return qs.order_by(*SORTS.get(g.get("sort"), SORTS["newest"]))


@method_decorator(ratelimit(key="user", rate=settings.RATE_EXPORT, block=True), name="get")
class ExportView(RoleRequiredMixin, View):
    allowed_roles = (ADMIN,)

    def get(self, request):
        return export_csv(filter_issues(Issue.objects.all(), request.GET))


class BaseIssueListView(RoleRequiredMixin, ListView):
    template_name = "issues/issue_list.html"
    paginate_by = 15
    heading = ""
    mode = ""

    def scope(self):
        raise NotImplementedError

    def get_queryset(self):
        qs = self.scope().select_related("reporter", "assigned_to").annotate(vote_count=Count("votes"))
        return filter_issues(qs, self.request.GET)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        params = self.request.GET.copy()
        params.pop("page", None)
        ctx.update(
            heading=self.heading, mode=self.mode, qs=params.urlencode(), f=self.request.GET,
            status_choices=S.choices, category_choices=Category.choices,
            priority_choices=Issue.Priority.choices,
            sort_choices=[("newest", "Newest"), ("oldest", "Oldest"), ("priority", "Priority"), ("votes", "Most supported")],
        )
        if self.mode == "community":
            ctx["voted_ids"] = set(self.request.user.votes.values_list("issue_id", flat=True))
        return ctx


class MyIssuesView(BaseIssueListView):
    allowed_roles = (CITIZEN,)
    heading, mode = "My reports", "mine"

    def scope(self):
        return Issue.objects.filter(reporter=self.request.user)


class IssueListView(BaseIssueListView):
    allowed_roles = (ADMIN, CITIZEN)

    def scope(self):
        if is_admin(self.request.user):
            self.heading, self.mode = "All issues", "admin"
            return Issue.objects.all()
        self.heading, self.mode = "Community reports", "community"
        return community_issues()


class TaskListView(BaseIssueListView):
    allowed_roles = (STAFF,)
    heading, mode = "My tasks", "tasks"

    def scope(self):
        return Issue.objects.filter(assigned_to=self.request.user)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["task_stats"] = self.scope().aggregate(
            to_start=Count("id", filter=Q(status=S.ASSIGNED)),
            in_progress=Count("id", filter=Q(status=S.IN_PROGRESS, verification_pending=False)),
            awaiting=Count("id", filter=Q(status=S.IN_PROGRESS, verification_pending=True)),
        )
        return ctx


def map_scope(user):
    """Same visibility as the lists: admin all, staff assigned, citizens the community list."""
    if is_admin(user):
        return Issue.objects.all(), "Showing every report."
    if has_role(user, STAFF):
        return Issue.objects.filter(assigned_to=user), "Showing only reports assigned to you."
    if has_role(user, CITIZEN):
        return community_issues(), "Showing community reports. You can open details for your own."
    return Issue.objects.none(), ""


class MapView(LoginRequiredMixin, TemplateView):
    template_name = "issues/map.html"

    def get_context_data(self, **kwargs):
        return super().get_context_data(
            center=settings.MAP_DEFAULT_CENTER, scope_note=map_scope(self.request.user)[1],
            status_choices=S.choices, category_choices=Category.choices, **kwargs,
        )


class MapDataView(LoginRequiredMixin, View):
    def get(self, request):
        qs = map_scope(request.user)[0]
        if (v := request.GET.get("status")) in S.values:
            qs = qs.filter(status=v)
        if (v := request.GET.get("category")) in Category.values:
            qs = qs.filter(category=v)
        issues = []
        for i in qs.order_by("-created_at")[:1000]:
            issues.append({
                "code": i.tracking_code, "title": i.title,
                "lat": float(i.latitude), "lng": float(i.longitude),
                "status": i.status, "status_label": i.get_status_display(),
                "category": i.category, "category_label": i.get_category_display(),
                "url": reverse("issues:detail", args=[i.tracking_code]) if can_view_issue(request.user, i) else None,
            })
        return JsonResponse({"issues": issues})


class IssueDetailView(LoginRequiredMixin, DetailView):
    template_name = "issues/issue_detail.html"
    context_object_name = "issue"

    def get_object(self, queryset=None):
        return get_visible_issue(self.request.user, self.kwargs["code"])

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        issue, user = self.object, self.request.user
        admin, reporter, staff = is_admin(user), is_reporter(user, issue), can_update_issue(user, issue)
        ctx.update(
            events=issue.events.select_related("actor"),
            photos=issue.media.all(),
            vote_count=issue.votes.count(),
            is_admin=admin,
            is_reporter=reporter,
            can_review=admin and issue.status == S.REPORTED,
            can_reject=admin and issue.status in (S.REPORTED, S.UNDER_REVIEW),
            can_assign=admin and issue.status in (S.UNDER_REVIEW, S.ASSIGNED, S.IN_PROGRESS),
            can_prioritise=admin and issue.is_open,
            can_resolve=admin and issue.status == S.IN_PROGRESS and issue.verification_pending,
            can_start=staff and issue.status == S.ASSIGNED,
            can_confirm=reporter and issue.status == S.RESOLVED and issue.reporter_confirmed is None,
            can_reopen=reporter and issue.status == S.RESOLVED,
            can_request_info=admin and issue.is_open,
            can_merge=admin and issue.status in (S.REPORTED, S.UNDER_REVIEW) and not issue.merged_into_id,
            can_progress=staff and issue.status in (S.ASSIGNED, S.IN_PROGRESS),
            can_upload_evidence=staff and issue.status == S.IN_PROGRESS,
            can_submit=staff and issue.status == S.IN_PROGRESS and not issue.verification_pending
            and issue.media.filter(kind=IssueMedia.Kind.EVIDENCE).exists(),
            priority_choices=Issue.Priority.choices,
        )
        if admin:
            cat, words = smart.suggest_category(issue.title, issue.description)
            prio, reasons = smart.recommend_priority(issue.category, issue.title, issue.description, ctx["vote_count"])
            ctx["smart"] = {
                "category": cat, "category_label": Category(cat).label if cat else "", "words": words,
                "priority": prio, "priority_label": Issue.Priority(prio).label, "reasons": reasons,
                "duplicates": smart.find_duplicates(
                    issue.title, issue.description, issue.category, issue.latitude, issue.longitude,
                    Issue.objects.all(), exclude_pk=issue.pk,
                ) if issue.is_open else [],
            }
            ctx["assignments"] = issue.assignments.select_related("staff", "assigned_by")
            ctx["staff_list"] = get_user_model().objects.filter(role=STAFF, is_active=True).annotate(
                open_tasks=Count("tasks", filter=Q(tasks__status__in=[S.ASSIGNED, S.IN_PROGRESS]))
            ).order_by("first_name", "username")
        return ctx


class IssueActionView(LoginRequiredMixin, View):
    """Single POST endpoint for workflow buttons. Services enforce every rule."""

    def post(self, request, code):
        issue = get_visible_issue(request.user, code)
        action, note, user = request.POST.get("action"), request.POST.get("note", ""), request.user
        handlers = {
            "review": lambda: services.change_status(issue, S.UNDER_REVIEW, user, note),
            "reject": lambda: services.change_status(issue, S.REJECTED, user, note),
            "assign": lambda: services.assign(issue, self._staff(request.POST.get("staff")), user),
            "priority": lambda: services.set_priority(issue, request.POST.get("priority"), user),
            "start": lambda: services.change_status(issue, S.IN_PROGRESS, user, note),
            "resolve": lambda: services.change_status(issue, S.RESOLVED, user, note),
            "confirm": lambda: services.confirm_resolution(issue, user),
            "reopen": lambda: services.change_status(issue, S.UNDER_REVIEW, user, note),
            "comment": lambda: services.add_comment(issue, user, note),
            "request_info": lambda: services.request_info(issue, user, note),
            "merge": lambda: services.merge_issues(issue, request.POST.get("target"), user),
            "send_back": lambda: services.send_back(issue, user, note),
            "progress": lambda: services.add_progress(issue, user, note),
            "evidence": lambda: self._evidence(issue, user, request.FILES.get("photo")),
            "submit": lambda: services.submit_for_verification(issue, user),
            "category": lambda: services.set_category(issue, request.POST.get("category"), user),
        }
        if action not in handlers:
            messages.error(request, "Unknown action.")
        else:
            try:
                handlers[action]()
                messages.success(request, "Saved.")
            except ValidationError as e:
                messages.error(request, " ".join(e.messages))
        return redirect("issues:detail", code=issue.tracking_code)

    @staticmethod
    def _evidence(issue, user, photo):
        if not photo:
            raise ValidationError("Choose a photo to upload.")
        mime = validate_image(photo)
        services.add_evidence(issue, user, photo, mime)

    @staticmethod
    def _staff(pk):
        if not str(pk or "").isdigit():
            return None
        return get_user_model().objects.filter(pk=pk, role=STAFF, is_active=True).first()


class VoteView(RoleRequiredMixin, View):
    allowed_roles = (CITIZEN,)

    def post(self, request, code):
        issue = get_object_or_404(community_issues(), tracking_code=code)
        try:
            added = services.vote(issue, request.user)
            messages.success(request, "Thanks for your support." if added else "You already support this report.")
        except ValidationError as e:
            messages.error(request, " ".join(e.messages))
        nxt = request.POST.get("next", "/issues/")
        if not url_has_allowed_host_and_scheme(nxt, {request.get_host()}, request.is_secure()):
            nxt = "/issues/"
        return redirect(nxt)


class MediaView(LoginRequiredMixin, View):
    """Uploads are never served publicly; each request is permission checked."""

    def get(self, request, code, pk):
        issue = get_visible_issue(request.user, code)
        media = get_object_or_404(IssueMedia, pk=pk, issue=issue)
        return FileResponse(media.file.open("rb"), content_type=media.media_type)


class SuggestView(RoleRequiredMixin, TemplateView):
    """HTMX fragment for the report form: category hint and similar open reports nearby."""

    allowed_roles = (CITIZEN,)
    template_name = "issues/_suggestions.html"

    def get_context_data(self, **kwargs):
        g = self.request.GET
        title, desc, current = g.get("title", "")[:100], g.get("description", "")[:1000], g.get("category", "")
        cat, words = smart.suggest_category(title, desc)
        dups = []
        try:
            lat, lng = float(g.get("latitude", "")), float(g.get("longitude", ""))
            if abs(lat) <= 90 and abs(lng) <= 180 and (title or desc):
                dups = smart.find_duplicates(title, desc, current or cat, lat, lng, community_issues())
        except ValueError:
            pass
        return super().get_context_data(
            cat=cat, cat_label=Category(cat).label if cat else "", words=words,
            current=current, dups=dups, **kwargs,
        )
