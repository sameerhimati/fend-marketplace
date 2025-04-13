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
]