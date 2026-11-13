from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import User


@admin.register(User)
class CivicUserAdmin(UserAdmin):
    list_display = ("email", "username", "role", "is_active")
    list_filter = ("role", "is_active")
    fieldsets = UserAdmin.fieldsets + (("CivicPulse", {"fields": ("role",)}),)
