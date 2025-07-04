from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.utils.html import format_html
from django.contrib import messages
from django.utils.crypto import get_random_string
from django.utils import timezone
from .models import User, PasswordReset

@admin.register(User)
class CustomUserAdmin(UserAdmin):
    list_display = ('username', 'email', 'organization_info', 'must_change_password', 'is_staff', 'is_active')
    list_filter = ('is_staff', 'is_active', 'must_change_password', 'organization__type', 'organization__approval_status')
    actions = ['reset_password']
    
    fieldsets = UserAdmin.fieldsets + (
        ('Organization', {'fields': ('organization',)}),
        ('Password Management', {'fields': ('must_change_password', 'password_changed_at')}),
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
    
    def reset_password(self, request, queryset):
        """Admin action to reset user passwords"""
        count = 0
        for user in queryset:
            # Generate temporary password
            temp_password = get_random_string(12)
            
            # Set the password
            user.set_password(temp_password)
            user.must_change_password = True
            user.save()
            
            # Create reset record
            PasswordReset.objects.create(
                user=user,
                admin=request.user,
                temporary_password=temp_password
            )
            
            count += 1
            
            # Show the temporary password in messages
            self.message_user(
                request,
                f"Password reset for {user.username}: {temp_password}",
                level=messages.SUCCESS
            )
        
        if count > 1:
            self.message_user(
                request,
                f"Successfully reset passwords for {count} users.",
                level=messages.SUCCESS
            )
    
    reset_password.short_description = "Reset password (generate temporary)"


@admin.register(PasswordReset)
class PasswordResetAdmin(admin.ModelAdmin):
    list_display = ('user', 'admin', 'created_at', 'used_at', 'temporary_password')
    list_filter = ('created_at', 'used_at')
    search_fields = ('user__username', 'user__email', 'admin__username')
    readonly_fields = ('user', 'admin', 'temporary_password', 'created_at', 'used_at')
    
    def has_add_permission(self, request):
        # Prevent manual creation - should only be created via reset action
        return False
    
    def has_delete_permission(self, request, obj=None):
        # Only superusers can delete reset records
        return request.user.is_superuser