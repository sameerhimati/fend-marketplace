from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.utils.html import format_html
from .models import User, EmailVerificationToken


class EmailVerificationTokenInline(admin.TabularInline):
    model = EmailVerificationToken
    extra = 0
    readonly_fields = ('token', 'created_at', 'used')
    can_delete = False
    
    def has_add_permission(self, request, obj=None):
        return False


@admin.register(User)
class CustomUserAdmin(UserAdmin):
    list_display = ('username', 'email', 'organization_info', 'is_verified', 'is_staff', 'is_active')
    list_filter = ('is_staff', 'is_active', 'is_verified', 'organization__type')
    
    fieldsets = UserAdmin.fieldsets + (
        ('Organization', {'fields': ('organization', 'is_verified')}),
    )
    
    add_fieldsets = UserAdmin.add_fieldsets + (
        ('Organization', {'fields': ('organization', 'is_verified')}),
    )
    
    search_fields = ('username', 'email', 'organization__name')
    
    inlines = [EmailVerificationTokenInline]
    
    def organization_info(self, obj):
        if obj.organization:
            org_type = obj.organization.get_type_display()
            color = '#10B981' if obj.organization.type == 'enterprise' else '#3B82F6'
            return format_html(
                '<span style="color: {};">{} ({})</span>',
                color,
                obj.organization.name,
                org_type
            )
        return '-'
    organization_info.short_description = 'Organization'
    organization_info.admin_order_field = 'organization__name'
    
    def get_queryset(self, request):
        """Optimize queryset to avoid N+1 queries"""
        qs = super().get_queryset(request)
        return qs.select_related('organization')


@admin.register(EmailVerificationToken)
class EmailVerificationTokenAdmin(admin.ModelAdmin):
    list_display = ('user', 'token_preview', 'created_at', 'used', 'is_expired_display')
    list_filter = ('used', 'created_at')
    search_fields = ('user__username', 'user__email', 'token')
    readonly_fields = ('token', 'created_at')
    
    def token_preview(self, obj):
        """Show first and last 4 characters of token for security"""
        if len(obj.token) > 8:
            return f"{obj.token[:4]}...{obj.token[-4:]}"
        return obj.token
    token_preview.short_description = 'Token'
    
    def is_expired_display(self, obj):
        """Show if token is expired with color coding"""
        is_expired = obj.is_expired()
        color = '#DC2626' if is_expired else '#10B981'
        status = 'Expired' if is_expired else 'Valid'
        return format_html(
            '<span style="color: {};">{}</span>',
            color,
            status
        )
    is_expired_display.short_description = 'Status'
    
    def get_queryset(self, request):
        """Optimize queryset to avoid N+1 queries"""
        qs = super().get_queryset(request)
        return qs.select_related('user')
    
    def has_add_permission(self, request):
        """Don't allow manual creation of verification tokens"""
        return False