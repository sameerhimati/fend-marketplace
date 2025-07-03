from django.urls import path
from . import views
from . import views_ajax

app_name = 'payments'

urlpatterns = [
    # =============================================================================
    # USER PAYMENT URLS - Subscription Management
    # =============================================================================
    
    # Subscription Selection & Checkout
    path('select-plan/', views.payment_selection, name='payment_selection'),
    path('validate-free-code/', views.validate_free_code, name='validate_free_code'),
    path('checkout/success/', views.checkout_success, name='checkout_success'),
    path('checkout/cancel/', views.checkout_cancel, name='checkout_cancel'),
    path('webhook/', views.stripe_webhook, name='stripe_webhook'),
    
    # Subscription Management
    path('subscription/', views.subscription_detail, name='subscription_detail'),
    path('subscription/cancel/', views.cancel_subscription, name='cancel_subscription'),
    path('subscription/cancel/undo/', views.cancel_subscription_undo, name='cancel_subscription_undo'),
    path('subscription/upgrade/', views.upgrade_subscription, name='upgrade_subscription'),
    path('subscription/complete-payment/', views.complete_payment, name='complete_payment'),
    
    # Payment Holding Service User Views (Enterprise-facing)
    path('payment-holding/<int:payment_id>/', 
         views.payment_holding_instructions, 
         name='payment_holding_instructions'),
    path('payment-holding/<int:payment_id>/confirm/', 
         views.payment_holding_confirmation, 
         name='payment_holding_confirmation'),
    
    # =============================================================================
    # ADMIN URLS - 4-Stage Payment Management Workflow
    # =============================================================================
    
    # Main Admin Dashboard
    path('admin/dashboard/', 
         views.admin_payment_dashboard, 
         name='admin_payment_dashboard'),
    
    # Payment List & Management
    path('admin/payment-holding-services/', 
         views.admin_payment_holding_services, 
         name='admin_payment_holding_services'),
    
    # Individual Payment Management
    path('admin/payment-holding/<int:payment_id>/', 
         views.admin_payment_holding_detail, 
         name='admin_payment_holding_detail'),
    
    # =============================================================================
    # 4-STAGE WORKFLOW ACTIONS
    # =============================================================================
    
    # Stage 1 → Stage 2: Generate and send invoice
    path('admin/bid/<int:bid_id>/mark-invoice-sent/', 
         views.admin_mark_invoice_sent, 
         name='admin_mark_invoice_sent'),
    
    # Stage 2 → Stage 3: Confirm payment received AND activate work (combined step)
    path('admin/payment/<int:payment_id>/confirm-and-activate/', 
         views.admin_confirm_payment_and_activate, 
         name='admin_confirm_payment_and_activate'),
    
    # Stage 3 → Stage 4: Release payment to startup after work completion
    path('admin/payment/<int:payment_id>/release-startup-payment/', 
         views.admin_release_startup_payment, 
         name='admin_release_startup_payment'),
    
    # Admin Utilities
    path('admin/payment-holding-services/export-csv/', 
         views.admin_export_payments_csv, 
         name='admin_export_payments_csv'),

    # =============================================================================
    # NEW: ACTIVE WORK MANAGEMENT
    # =============================================================================
    
    # Active pilots dashboard
    path('admin/active-pilots/', 
         views.admin_active_pilots_dashboard, 
         name='admin_active_pilots_dashboard'),
    
    # Mark pilot work as started (approved → live)
    path('admin/pilot/<int:bid_id>/start-work/', 
         views.admin_start_pilot_work, 
         name='admin_start_pilot_work'),
    
    # Quick completion actions
    path('admin/pilot/<int:bid_id>/mark-completion-requested/', 
         views.admin_mark_completion_requested, 
         name='admin_mark_completion_requested'),
    
    # Contact management
    path('admin/pilot/<int:bid_id>/contact-parties/', 
         views.admin_contact_pilot_parties, 
         name='admin_contact_pilot_parties'),

    # =============================================================================
    # FREE ACCOUNT CODES MANAGEMENT
    # =============================================================================
    
    # Free codes dashboard
    path('admin/free-codes/', 
         views.admin_free_codes_dashboard, 
         name='admin_free_codes_dashboard'),
    
    # Individual code management
    path('admin/free-codes/<int:code_id>/', 
         views.admin_free_code_detail, 
         name='admin_free_code_detail'),
    
    # Generate new codes
    path('admin/free-codes/generate/', 
         views.admin_generate_free_codes, 
         name='admin_generate_free_codes'),
    
    # Export codes as CSV
    path('admin/free-codes/export-csv/', 
         views.admin_export_free_codes_csv, 
         name='admin_export_free_codes_csv'),
    
    # Bulk delete codes
    path('admin/free-codes/bulk-delete/', 
         views.admin_bulk_delete_free_codes, 
         name='admin_bulk_delete_free_codes'),
    
    # =============================================================================
    # AJAX ENDPOINTS
    # =============================================================================
    
    # Dismiss subscription warning for session
    path('ajax/dismiss-warning/', 
         views_ajax.dismiss_subscription_warning, 
         name='dismiss_subscription_warning'),
]