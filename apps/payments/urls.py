from django.urls import path
from . import views

app_name = 'payments'

urlpatterns = [
    # =============================================================================
    # USER PAYMENT URLS - Subscription Management
    # =============================================================================
    
    # Subscription Selection & Checkout
    path('select-plan/', views.payment_selection, name='payment_selection'),
    path('checkout/success/', views.checkout_success, name='checkout_success'),
    path('checkout/cancel/', views.checkout_cancel, name='checkout_cancel'),
    path('webhook/', views.stripe_webhook, name='stripe_webhook'),
    
    # Subscription Management
    path('subscription/', views.subscription_detail, name='subscription_detail'),
    path('subscription/cancel/', views.cancel_subscription, name='cancel_subscription'),
    path('subscription/cancel/undo/', views.cancel_subscription_undo, name='cancel_subscription_undo'),
    path('subscription/upgrade/', views.upgrade_subscription, name='upgrade_subscription'),
    path('subscription/complete-payment/', views.complete_payment, name='complete_payment'),
    
    # Escrow Payment User Views (Enterprise-facing)
    path('escrow-payment/<int:payment_id>/', 
         views.escrow_payment_instructions, 
         name='escrow_payment_instructions'),
    path('escrow-payment/<int:payment_id>/confirm/', 
         views.escrow_payment_confirmation, 
         name='escrow_payment_confirmation'),
    
    # =============================================================================
    # ADMIN URLS - Payment Management Workflow
    # =============================================================================
    
    # Main Admin Dashboard
    path('admin/dashboard/', 
         views.admin_payment_dashboard, 
         name='admin_payment_dashboard'),
    
    # Payment List & Management
    path('admin/escrow-payments/', 
         views.admin_escrow_payments, 
         name='admin_escrow_payments'),
    
    # Individual Payment Management
    path('admin/escrow-payment/<int:payment_id>/', 
         views.admin_escrow_payment_detail, 
         name='admin_escrow_payment_detail'),
    
    # Payment Workflow Actions
    path('admin/escrow-payment/<int:payment_id>/received/', 
         views.admin_mark_payment_received, 
         name='admin_mark_payment_received'),
    
    path('admin/escrow-payment/<int:payment_id>/release/', 
         views.admin_release_payment, 
         name='admin_release_payment'),
    
    path('admin/escrow-payment/<int:payment_id>/kickoff/', 
         views.admin_kickoff_pilot, 
         name='admin_kickoff_pilot'),
    
    # NEW: Enhanced Workflow Actions
    path('admin/bid/<int:bid_id>/mark-invoice-sent/', 
         views.admin_mark_invoice_sent, 
         name='admin_mark_invoice_sent'),
    
    path('admin/payment/<int:payment_id>/activate-work/', 
         views.admin_activate_pilot_work, 
         name='admin_activate_pilot_work'),
    
    path('admin/payment/<int:payment_id>/release-startup-payment/', 
         views.admin_release_startup_payment, 
         name='admin_release_startup_payment'),
    
    # Admin Utilities
    path('admin/escrow-payments/export-csv/', 
         views.admin_export_payments_csv, 
         name='admin_export_payments_csv'),
]