from django.contrib import admin
from .models import (
    PricingPlan, 
    Subscription, 
    Payment, 
    TokenPackage, 
    TokenTransaction, 
    TokenConsumptionLog,
    EscrowPayment,
    EscrowPaymentLog
)

@admin.register(EscrowPayment)
class EscrowPaymentAdmin(admin.ModelAdmin):
    list_display = ('reference_code', 'pilot_bid', 'total_amount', 'startup_amount', 'status', 'created_at')
    list_filter = ('status',)
    search_fields = ('reference_code', 'pilot_bid__pilot__title')
    raw_id_fields = ('pilot_bid',)
    readonly_fields = ('created_at',)

@admin.register(EscrowPaymentLog)
class EscrowPaymentLogAdmin(admin.ModelAdmin):
    list_display = ('escrow_payment', 'previous_status', 'new_status', 'changed_by', 'created_at')
    list_filter = ('new_status',)
    search_fields = ('escrow_payment__reference_code',)
    raw_id_fields = ('escrow_payment', 'changed_by')

# Register other models if they're not already registered
admin.site.register(PricingPlan)
admin.site.register(Subscription)
admin.site.register(Payment)
admin.site.register(TokenPackage)
admin.site.register(TokenTransaction)
admin.site.register(TokenConsumptionLog)