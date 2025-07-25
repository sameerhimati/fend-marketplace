from django.urls import path
from . import views

app_name = 'pilots'

urlpatterns = [
    # =============================================================================
    # UNIFIED PILOT URLS - Single entry point for all pilot-related activities
    # =============================================================================
    
    # Main pilots page (replaces both pilot list and bid list)
    path('', views.UnifiedPilotListView.as_view(), name='list'),
    
    # Pilot management
    path('create/', views.PilotCreateView.as_view(), name='create'),
    path('<int:pk>/', views.StatusAwarePilotDetailView.as_view(), name='detail'),
    path('<int:pk>/edit/', views.PilotUpdateView.as_view(), name='edit'),
    path('<int:pk>/publish/', views.publish_pilot, name='publish'),
    path('pilots/<int:pk>/delete/', views.delete_pilot, name='delete'),
    
    # Bid management (integrated into pilot workflow)
    path('<int:pilot_id>/bid/', views.create_bid, name='create_bid'),
    path('bids/<int:pk>/update-status/', views.update_bid_status, name='update_bid_status'),
    path('bids/<int:pk>/delete/', views.delete_bid, name='delete_bid'),
    
    # Bid workflow actions
    path('bids/<int:bid_id>/request-completion/', views.request_completion, name='request_completion'),
    path('bids/<int:bid_id>/verify-completion/', views.verify_completion, name='verify_completion'),
    
    # Legacy bid routes (redirect to unified experience)
    path('bids/', views.BidListView.as_view(), name='bid_list'),  
    path('bids/<int:pk>/', views.BidDetailView.as_view(), name='bid_detail'), 

    # =============================================================================
    # ADMIN URLS - Pilot Verification Workflow
    # =============================================================================
    
    # Main Admin Verification Dashboard
    path('admin/verify/', 
         views.admin_verify_pilots, 
         name='admin_verify_pilots'),
    
    # Individual Pilot Verification
    path('admin/verify/<int:pk>/', 
         views.admin_verify_pilot_detail, 
         name='admin_verify_pilot_detail'),
    
    # Pilot Approval Actions
    path('admin/verify/<int:pk>/approve/', 
         views.admin_approve_pilot, 
         name='admin_approve_pilot'),
    
    path('admin/verify/<int:pk>/reject/', 
         views.admin_reject_pilot, 
         name='admin_reject_pilot'),
    
    # Bid Admin Actions
    path('admin/bid/<int:pk>/mark-as-live/', 
         views.admin_mark_bid_as_live, 
         name='admin_mark_bid_as_live'),
    
    # =============================================================================
    # SECURE FILE SERVING - Fallback for permission issues
    # =============================================================================
    
    # Secure pilot file serving
    path('files/pilot/<int:pilot_id>/<str:file_type>/', 
         views.serve_pilot_file, 
         name='serve_pilot_file'),
    
    # Secure bid file serving  
    path('files/bid/<int:bid_id>/', 
         views.serve_bid_file, 
         name='serve_bid_file'),
]