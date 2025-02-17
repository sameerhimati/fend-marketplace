from django.contrib import admin
from django.core.exceptions import PermissionDenied
from .models import Pilot

@admin.register(Pilot)
class PilotAdmin(admin.ModelAdmin):
    list_display = ('title', 'organization', 'status', 'created_at')
    list_filter = ('status', 'organization')
    search_fields = ('title', 'description')

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if not request.user.is_superuser:
            # If user belongs to an organization, filter accordingly
            if hasattr(request.user, 'organization'):
                if request.user.organization.type == 'enterprise':
                    # Enterprise users see only their pilots
                    return qs.filter(organization=request.user.organization)
                elif request.user.organization.type == 'startup':
                    # Startup users can see all pilots but can't modify them
                    return qs
        return qs

    def has_add_permission(self, request):
        if not request.user.is_superuser:
            if hasattr(request.user, 'organization'):
                return request.user.organization.type == 'enterprise'
        return super().has_add_permission(request)

    def has_change_permission(self, request, obj=None):
        if not request.user.is_superuser:
            if obj is None:
                return request.user.organization.type == 'enterprise'
            return obj.organization == request.user.organization
        return super().has_change_permission(request, obj)

    def has_delete_permission(self, request, obj=None):
        if not request.user.is_superuser:
            if obj is None:
                return request.user.organization.type == 'enterprise'
            return obj.organization == request.user.organization
        return super().has_delete_permission(request, obj)