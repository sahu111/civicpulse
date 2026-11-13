import re
from functools import lru_cache

from django import template
from django.conf import settings
from django.utils.html import escape
from django.utils.safestring import mark_safe

register = template.Library()
ICON_DIR = settings.BASE_DIR / "static" / "vendor" / "icons"


@lru_cache(maxsize=64)
def _load(name: str) -> str:
    if not re.fullmatch(r"[a-z0-9-]+", name):
        return ""
    try:
        svg = (ICON_DIR / f"{name}.svg").read_text(encoding="utf-8")
    except FileNotFoundError:
        return ""
    svg = re.sub(r"<!--.*?-->", "", svg, flags=re.S)
    return re.sub(r'\s(width|height|class)="[^"]*"', "", svg).strip()


STATUS_CLASSES = {
    "REPORTED": "bg-slate-50 text-slate-700 ring-slate-300",
    "UNDER_REVIEW": "bg-sky-50 text-sky-700 ring-sky-200",
    "ASSIGNED": "bg-violet-50 text-violet-700 ring-violet-200",
    "IN_PROGRESS": "bg-amber-50 text-amber-700 ring-amber-200",
    "RESOLVED": "bg-emerald-50 text-emerald-700 ring-emerald-200",
    "REJECTED": "bg-red-50 text-red-700 ring-red-200",
}
PRIORITY_CLASSES = {
    "HIGH": "bg-red-50 text-red-700 ring-red-200",
    "MEDIUM": "bg-amber-50 text-amber-700 ring-amber-200",
    "LOW": "bg-slate-50 text-slate-600 ring-slate-300",
}


@register.filter
def status_classes(status):
    return STATUS_CLASSES.get(status, STATUS_CLASSES["REPORTED"])


@register.filter
def priority_classes(priority):
    return PRIORITY_CLASSES.get(priority, PRIORITY_CLASSES["LOW"])


@register.simple_tag
def icon(name, css="size-5"):
    """Inline a local Lucide SVG. Only reads vetted files from static/vendor/icons."""
    svg = _load(name)
    if not svg:
        return ""
    return mark_safe(svg.replace("<svg", f'<svg class="{escape(css)}" aria-hidden="true"', 1))
