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

@register.filter
def pilot_completion_count(pilot):
    """Calculate the number of completed requirements for a pilot"""
    count = 0
    
    if pilot.technical_specs_doc or pilot.technical_specs_text:
        count += 1
    if pilot.performance_metrics or pilot.performance_metrics_doc:
        count += 1
    if pilot.compliance_requirements or pilot.compliance_requirements_doc:
        count += 1
    if pilot.legal_agreement_accepted:
        count += 1
    if pilot.price and pilot.price > 0:
        count += 1
        
    return count