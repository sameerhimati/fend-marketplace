from django.contrib import admin
from .models import Notification, NotificationPreferences

@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ('title', 'recipient', 'type', 'read', 'created_at')
    list_filter = ('type', 'read', 'created_at')
    search_fields = ('title', 'message', 'recipient__username', 'recipient__email')
    readonly_fields = ('created_at',)
    
    fieldsets = (
        (None, {
            'fields': ('recipient', 'type', 'title', 'message', 'read')
        }),
        ('Related Objects', {
            'fields': ('related_pilot', 'related_bid'),
            'classes': ('collapse',)
        }),
        ('Metadata', {
            'fields': ('created_at',),
            'classes': ('collapse',)
        })
    )
    
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if not request.user.is_superuser:
            # Non-superusers only see their own notifications
            return qs.filter(recipient=request.user)
        return qs
    
    def has_change_permission(self, request, obj=None):
        if not request.user.is_superuser:
            if obj is None:
                return True  # Allow viewing the list
            # Only allow changing own notifications
            return obj.recipient == request.user
        return super().has_change_permission(request, obj)


@admin.register(NotificationPreferences)
class NotificationPreferencesAdmin(admin.ModelAdmin):
    list_display = ('user', 'enabled')
    list_filter = ('enabled',)
    search_fields = ('user__username', 'user__email')
    
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if not request.user.is_superuser:
            # Non-superusers only see their own preferences
            return qs.filter(user=request.user)
        return qs
    
    def has_change_permission(self, request, obj=None):
        if not request.user.is_superuser:
            if obj is None:
                return True  # Allow viewing the list
            # Only allow changing own preferences
            return obj.user == request.user
        return super().has_change_permission(request, obj)