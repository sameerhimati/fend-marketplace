from django.urls import path
from django.contrib.auth.views import LogoutView
from . import views
from . import legal_views

app_name = 'organizations'

urlpatterns = [
    # User Registration & Authentication
    path('register/', 
         views.OrganizationRegistrationView.as_view(), 
         name='register'),
    path('register/complete/',
         views.RegistrationCompleteView.as_view(),
         name='registration_complete'),
    path('login/', views.CustomLoginView.as_view(), name='login'),
    path('logout/', LogoutView.as_view(next_page='landing'), name='logout'),
    path('pending-approval/', views.PendingApprovalView.as_view(), name='pending_approval'),
    
    # User Dashboards
    path('dashboard/', views.DashboardView.as_view(), name='dashboard'),
    path('dashboard/enterprise/', views.EnterpriseDashboardView.as_view(), name='enterprise_dashboard'),
    path('dashboard/startup/', views.StartupDashboardView.as_view(), name='startup_dashboard'),
    
    # Organization Directories & Profiles
    path('directory/', 
         views.DirectoryView.as_view(), 
         name='directory'),
    
    # Organization Profiles
    path('profile/<int:pk>/', views.OrganizationProfileView.as_view(), name='profile'),
    path('profile/edit/', views.ProfileEditView.as_view(), name='profile_edit'),
    path('profile/remove-logo/', views.remove_logo, name='remove_logo'),

    # Deals
    path('deals/', views.DealsView.as_view(), name='deals'),
    
    # =============================================================================
    # LEGAL DOCUMENT VIEWS
    # =============================================================================
    
    # Legal document views
    path('legal/terms-of-service/', legal_views.terms_of_service, name='terms_of_service'),
    path('legal/privacy-policy/', legal_views.privacy_policy, name='privacy_policy'),
    path('legal/user-agreement/', legal_views.user_agreement, name='user_agreement'),
    path('legal/payment-terms/', legal_views.payment_terms, name='payment_terms'),
    path('legal/payment-holding-agreement/', legal_views.payment_holding_agreement, name='payment_holding_agreement'),
    path('legal/data-processing-agreement/', legal_views.data_processing_agreement, name='data_processing_agreement'),
    path('legal/product-listing-agreement/', legal_views.product_listing_agreement, name='product_listing_agreement'),
    path('legal/accept/', legal_views.accept_legal_document, name='accept_legal_document'),
    path('legal/status/', legal_views.legal_status, name='legal_status'),
    path('legal/download/<str:document_type>/', legal_views.download_legal_document, name='download_legal_document'),
    
    # =============================================================================
    # PARTNER PROMOTION MANAGEMENT
    # =============================================================================
    
    # List all partner promotions for the organization
    path('partner-promotions/', 
         views.PartnerPromotionListView.as_view(), 
         name='partner_promotions_list'),
    
    # Create new partner promotion
    path('partner-promotions/create/', 
         views.PartnerPromotionCreateView.as_view(), 
         name='partner_promotion_create'),
    
    # Edit existing partner promotion
    path('partner-promotions/<int:pk>/edit/', 
         views.PartnerPromotionUpdateView.as_view(), 
         name='partner_promotion_edit'),
    
    # Delete partner promotion
    path('partner-promotions/<int:pk>/delete/', 
         views.PartnerPromotionDeleteView.as_view(), 
         name='partner_promotion_delete'),
    
    # =============================================================================
    # ADMIN URLS - Organization Approval Workflow
    # =============================================================================
    
    # Main admin approval dashboard
    path('admin/pending/', 
         views.admin_pending_approvals, 
         name='admin_pending_approvals'),
    
    # Individual organization review
    path('admin/organization/<int:org_id>/', 
         views.admin_organization_detail, 
         name='admin_organization_detail'),
    
    # Organization approval actions
    path('admin/organization/<int:org_id>/approve/', 
         views.admin_approve_organization, 
         name='admin_approve_organization'),
    
    path('admin/organization/<int:org_id>/reject/', 
         views.admin_reject_organization, 
         name='admin_reject_organization'),
]