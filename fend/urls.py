"""
URL configuration for fend project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.1/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from . import views
from .views import LandingPageView
from django.contrib.auth.views import LogoutView
from apps.organizations import legal_views

urlpatterns = [
    path('admin/logout/', LogoutView.as_view(next_page='landing'), name='admin_logout'),
    path('admin/dashboard/', views.enhanced_admin_dashboard, name='admin_dashboard'),
    path('admin/orgs/', views.admin_org_dashboard, name='admin_org_dashboard'),
    path('admin/orgs/<int:org_id>/', views.admin_org_detail, name='admin_org_detail'),
    path('admin/orgs/<int:org_id>/edit/', views.admin_org_edit, name='admin_org_edit'),
    path('admin/pilots/', views.admin_pilot_dashboard, name='admin_pilot_dashboard'),
    path('admin/search/', views.admin_global_search, name='admin_global_search'),
    path('admin/export/', views.admin_export_csv, name='admin_export_csv'),
    path('admin/', admin.site.urls),
    path('', LandingPageView.as_view(), name='landing'),
    
    # Legal portal at root level
    path('legal/', legal_views.legal_portal_homepage, name='legal_portal'),
    path('legal/<str:document_type>/', legal_views.legal_document_full, name='legal_document'),
    
    path('pilots/', include('apps.pilots.urls')),
    path('organizations/', include('apps.organizations.urls')),
    path('notifications/', include('apps.notifications.urls')),
    path('payments/', include('apps.payments.urls')),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
    
    # Add debug toolbar URLs
    try:
        import debug_toolbar
        urlpatterns += [path('__debug__/', include('debug_toolbar.urls'))]
    except ImportError:
        pass