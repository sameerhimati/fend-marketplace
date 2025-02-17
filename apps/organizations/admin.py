from django.contrib import admin
from .models import Organization

@admin.register(Organization)
class OrganizationAdmin(admin.ModelAdmin):
    list_display = ('name', 'type', 'created_at')
    list_filter = ('type',)
    search_fields = ('name', 'domain')