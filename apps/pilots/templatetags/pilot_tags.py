from django import template
from decimal import Decimal, DecimalException
import os

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

@register.filter
def friendly_filename(file_path):
    """Extract a user-friendly filename from a file path
    
    Examples:
    - 'documents/pilots/snapchat-test-1/temp/technical/technical_my_document.pdf' -> 'My Document.pdf'
    - 'documents/pilots/company/123/performance/performance_metrics.pdf' -> 'Metrics.pdf'
    - 'documents/bids/startup/pilot/proposal_my_proposal_456.pdf' -> 'My Proposal.pdf'
    """
    if not file_path:
        return ""
    
    # Get the filename from the path
    filename = os.path.basename(str(file_path))
    
    # Get the file extension
    name, ext = os.path.splitext(filename)
    
    # Determine document type based on path and filename
    file_path_str = str(file_path).lower()
    
    # Extract meaningful name from the filename
    clean_name = name
    
    # Remove prefixes based on document type
    if 'technical' in file_path_str and clean_name.startswith('technical_'):
        clean_name = clean_name[10:]  # Remove 'technical_' prefix
        if not clean_name:
            return f"Technical Specifications{ext}"
    elif 'performance' in file_path_str and clean_name.startswith('performance_'):
        clean_name = clean_name[12:]  # Remove 'performance_' prefix
        if not clean_name:
            return f"Performance Metrics{ext}"
    elif 'compliance' in file_path_str and clean_name.startswith('compliance_'):
        clean_name = clean_name[11:]  # Remove 'compliance_' prefix
        if not clean_name:
            return f"Compliance Requirements{ext}"
    elif ('proposal' in file_path_str or 'bid' in file_path_str) and clean_name.startswith('proposal_'):
        clean_name = clean_name[9:]  # Remove 'proposal_' prefix
        # Remove bid ID suffix (usually _123 at the end)
        parts = clean_name.rsplit('_', 1)
        if len(parts) == 2 and parts[1].isdigit():
            clean_name = parts[0]
        if not clean_name:
            return f"Proposal Document{ext}"
    elif 'logo' in file_path_str:
        return f"Company Logo{ext}"
    
    # Clean up the remaining name
    if clean_name:
        # Replace underscores and hyphens with spaces
        clean_name = clean_name.replace('_', ' ').replace('-', ' ')
        
        # Remove numbers and hash-like strings from the end
        parts = clean_name.split()
        cleaned_parts = []
        for part in parts:
            # Skip parts that look like random hashes or IDs
            if (len(part) > 8 and not any(v in part.lower() for v in 'aeiou')) or part.isdigit():
                continue
            cleaned_parts.append(part.title())
        
        if cleaned_parts:
            return f"{' '.join(cleaned_parts)}{ext}"
    
    # Fallback to document type based on path
    if 'technical' in file_path_str:
        return f"Technical Specifications{ext}"
    elif 'performance' in file_path_str:
        return f"Performance Metrics{ext}"
    elif 'compliance' in file_path_str:
        return f"Compliance Requirements{ext}"
    elif 'proposal' in file_path_str or 'bid' in file_path_str:
        return f"Proposal Document{ext}"
    else:
        return f"Document{ext}"

@register.filter 
def file_size_mb(file_field):
    """Get file size in MB for display"""
    if file_field and hasattr(file_field, 'size'):
        try:
            size_mb = file_field.size / (1024 * 1024)
            return f"{size_mb:.1f} MB"
        except:
            return ""
    return ""