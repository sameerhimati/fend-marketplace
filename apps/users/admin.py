from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.utils.html import format_html
from .models import User

@admin.register(User)
class CustomUserAdmin(UserAdmin):
    list_display = ('username', 'email', 'organization_info', 'is_staff', 'is_active')
    list_filter = ('is_staff', 'is_active', 'organization__type', 'organization__approval_status')
    
    fieldsets = UserAdmin.fieldsets + (
        ('Organization', {'fields': ('organization',)}),
    )
    
    add_fieldsets = UserAdmin.add_fieldsets + (
        ('Organization', {'fields': ('organization',)}),
    )
    
    search_fields = ('username', 'email', 'organization__name')
    
    def organization_info(self, obj):
        if obj.organization:
            org_type = obj.organization.get_type_display()
            approval_status = obj.organization.approval_status
            
            # Set color based on organization type and approval status
            if approval_status == 'approved':
                color = '#10B981' if obj.organization.type == 'enterprise' else '#3B82F6'
            elif approval_status == 'pending':
                color = '#F59E0B'  # amber for pending
            else:
                color = '#EF4444'  # red for rejected
                
            status_text = f" [{approval_status}]" if approval_status != 'approved' else ""
            
            return format_html(
                '<span style="color: {};">{}{} ({})</span>',
                color,
                obj.organization.name,
                status_text,
                org_type
            )
        return '-'
    organization_info.short_description = 'Organization'
    organization_info.admin_order_field = 'organization__name'
    
    def get_queryset(self, request):
        """Optimize queryset to avoid N+1 queries"""
        qs = super().get_queryset(request)
        return qs.select_related('organization')