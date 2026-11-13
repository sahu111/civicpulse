import csv

from django.http import HttpResponse
from django.utils import timezone

# Cells starting with these can run as formulas in Excel or Sheets.
DANGEROUS_PREFIXES = ("=", "+", "-", "@", "\t", "\r")
COLUMNS = ["Tracking code", "Title", "Category", "Priority", "Status", "Created", "Resolved"]


def safe_cell(value):
    text = "" if value is None else str(value)
    return "'" + text if text.startswith(DANGEROUS_PREFIXES) else text


def export_csv(queryset):
    response = HttpResponse(content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = f'attachment; filename="civicpulse-reports-{timezone.localdate():%Y%m%d}.csv"'
    response.write("﻿")  # lets Excel detect UTF-8
    writer = csv.writer(response)
    writer.writerow(COLUMNS)
    for i in queryset.iterator():
        writer.writerow([safe_cell(v) for v in (
            i.tracking_code, i.title, i.get_category_display(), i.get_priority_display(),
            i.get_status_display(),
            timezone.localtime(i.created_at).strftime("%Y-%m-%d %H:%M"),
            timezone.localtime(i.resolved_at).strftime("%Y-%m-%d %H:%M") if i.resolved_at else "",
        )])
    return response
