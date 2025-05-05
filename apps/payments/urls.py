from django.urls import path
from . import views

app_name = 'payments'

urlpatterns = [
    path('select-plan/', views.payment_selection, name='payment_selection'),
    path('checkout/success/', views.checkout_success, name='checkout_success'),
    path('checkout/cancel/', views.checkout_cancel, name='checkout_cancel'),
    path('subscription/', views.subscription_detail, name='subscription_detail'),
    path('subscription/cancel/', views.cancel_subscription, name='cancel_subscription'),
    path('subscription/upgrade/', views.upgrade_subscription, name='upgrade_subscription'),
    path('webhook/', views.stripe_webhook, name='stripe_webhook'),
    path('transaction/<int:transaction_id>/process/', views.process_transaction, name='process_transaction'),
    path('transaction/<int:transaction_id>/success/', views.transaction_success, name='transaction_success'),
    path('transaction/<int:transaction_id>/cancel/', views.transaction_cancel, name='transaction_cancel'),
    path('tokens/', views.token_packages, name='token_packages'),
    path('tokens/purchase/', views.purchase_tokens, name='purchase_tokens'),
    path('tokens/purchase/<int:package_id>/', views.purchase_tokens, name='purchase_tokens'),
    path('tokens/success/', views.token_purchase_success, name='token_purchase_success'),
    path('tokens/cancel/', views.token_purchase_cancel, name='token_purchase_cancel'),
    path('tokens/history/', views.token_history, name='token_history'),
    path('subscription/cancel/undo/', views.cancel_subscription_undo, name='cancel_subscription_undo'),
    path('subscription/complete-payment/', views.complete_payment, name='complete_payment'),
    # path('enterprise-fee/<int:fee_id>/process/', views.process_enterprise_fee, name='process_enterprise_fee'),
    # path('enterprise-fee/<int:fee_id>/success/', views.enterprise_fee_success, name='enterprise_fee_success'),
    # path('enterprise-fee/<int:fee_id>/cancel/', views.enterprise_fee_cancel, name='enterprise_fee_cancel'),
    path('escrow-payment/<int:payment_id>/', views.escrow_payment_instructions, name='escrow_payment_instructions'),
    path('escrow-payment/<int:payment_id>/confirm/', views.escrow_payment_confirmation, name='escrow_payment_confirmation'),
    path('admin/dashboard/', views.admin_payment_dashboard, name='admin_payment_dashboard'),
    path('admin/escrow-payments/', views.admin_escrow_payments, name='admin_escrow_payments'),
    path('admin/escrow-payment/<int:payment_id>/', views.admin_escrow_payment_detail, name='admin_escrow_payment_detail'),
    path('admin/escrow-payment/<int:payment_id>/received/', views.admin_mark_payment_received, name='admin_mark_payment_received'),
    path('admin/escrow-payment/<int:payment_id>/release/', views.admin_release_payment, name='admin_release_payment'),
    path('admin/escrow-payment/<int:payment_id>/update-status/', views.admin_update_payment_status, name='admin_update_payment_status'),
    path('admin/escrow-payments/export-csv/', views.admin_export_payments_csv, name='admin_export_payments_csv'),
]