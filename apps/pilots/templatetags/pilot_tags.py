from django import template
from decimal import Decimal, DecimalException

register = template.Library()

@register.filter
def format_currency(value):
    """Format a number as currency"""
    try:
        decimal_value = Decimal(str(value))
        return "{:,.2f}".format(decimal_value)
    except (ValueError, TypeError, DecimalException):
        return value
        
@register.filter
def calculate_total(amount, fee_amount):
    """Calculate total by adding amount and fee"""
    try:
        amount_decimal = Decimal(str(amount))
        fee_decimal = Decimal(str(fee_amount))
        total = amount_decimal + fee_decimal
        return total
    except (ValueError, TypeError, DecimalException):
        return amount