from django.contrib import admin

from .models import Issue, IssueEvent


class ReadOnlyEventInline(admin.TabularInline):
    model = IssueEvent
    extra = 0
    can_delete = False
    readonly_fields = ("kind", "actor", "old_status", "new_status", "note", "created_at")

    def has_add_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(Issue)
class IssueAdmin(admin.ModelAdmin):
    list_display = ("tracking_code", "title", "category", "priority", "status", "created_at")
    list_filter = ("status", "category", "priority")
    search_fields = ("tracking_code", "title")
    readonly_fields = ("tracking_code", "status", "assigned_to", "reporter")
    inlines = [ReadOnlyEventInline]
