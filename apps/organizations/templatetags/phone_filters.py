from django import template

register = template.Library()

@register.filter
def format_phone(phone_number, country_code='+1'):
    """Format phone number for display based on country code"""
    if not phone_number:
        return ''
    
    # Ensure we have just digits
    digits = ''.join(filter(str.isdigit, str(phone_number)))
    
    if country_code == '+1' and len(digits) == 10:
        # Format as (123) 456-7890 for US/Canada
        return f"({digits[:3]}) {digits[3:6]}-{digits[6:]}"
    
    # For other countries or invalid US numbers, return as-is
    return digits