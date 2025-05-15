from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import User

@admin.register(User)
class CustomUserAdmin(UserAdmin):
    list_display = ('username', 'email', 'organization', 'is_staff', 'is_active')
    list_filter = ('is_staff', 'is_active', 'organization__type')
    fieldsets = UserAdmin.fieldsets + (
        ('Organization', {'fields': ('organization',)}),
    )
    add_fieldsets = UserAdmin.add_fieldsets + (
        ('Organization', {'fields': ('organization',)}),
    )
    search_fields = ('username', 'email', 'organization__name')