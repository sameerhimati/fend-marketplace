import re
from django.core.exceptions import ValidationError
from django.core.validators import URLValidator


def clean_and_validate_website(website):
    """
    Centralized website cleaning and validation.
    
    - Strips whitespace and converts to lowercase
    - Removes protocol prefixes (http://, https://)
    - Removes www. prefix
    - Validates format (must have domain.tld structure)
    - Limits length to 100 characters
    
    Returns cleaned website URL without protocol.
    """
    if not website:
        return ""
    
    # Clean the input
    website = website.strip()
    
    # Remove protocol prefixes
    if website.startswith('http://'):
        website = website[7:]
    elif website.startswith('https://'):
        website = website[8:]
    
    # Remove www. prefix
    if website.startswith('www.'):
        website = website[4:]
    
    # Convert to lowercase for consistency
    website = website.lower()
    
    # Remove trailing slash
    website = website.rstrip('/')
    
    # Validate format - must have domain.tld structure
    domain_pattern = r'^[a-zA-Z0-9]([a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?(\.[a-zA-Z0-9]([a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?)*\.[a-zA-Z]{2,}$'
    
    if not re.match(domain_pattern, website):
        raise ValidationError(
            "Please enter a valid website URL (e.g., company.com or subdomain.company.org)"
        )
    
    # Check length limit
    if len(website) > 100:
        raise ValidationError(
            "Website URL is too long. Please use a shorter domain name."
        )
    
    # Additional validation - test if it could be a valid URL
    try:
        # Test with https prefix to ensure it's a valid URL structure
        url_validator = URLValidator()
        url_validator(f"https://{website}")
    except ValidationError:
        raise ValidationError(
            "Please enter a valid website URL (e.g., company.com)"
        )
    
    return website


def validate_industry_tags(tags_string):
    """
    Validate and clean industry tags.
    
    - Splits by commas
    - Strips whitespace
    - Validates each tag length and format
    - Limits total number of tags
    
    Returns list of cleaned tags.
    """
    if not tags_string:
        return []
    
    # Split by commas and clean
    tags = [tag.strip().title() for tag in tags_string.split(',') if tag.strip()]
    
    # Remove duplicates while preserving order
    seen = set()
    unique_tags = []
    for tag in tags:
        if tag.lower() not in seen:
            seen.add(tag.lower())
            unique_tags.append(tag)
    
    # Validate tag count
    if len(unique_tags) > 10:
        raise ValidationError("Maximum 10 industry tags allowed.")
    
    # Validate each tag
    for tag in unique_tags:
        if len(tag) < 2:
            raise ValidationError(f"Tag '{tag}' is too short. Minimum 2 characters.")
        if len(tag) > 30:
            raise ValidationError(f"Tag '{tag}' is too long. Maximum 30 characters.")
        if not re.match(r'^[a-zA-Z0-9\s&-]+$', tag):
            raise ValidationError(f"Tag '{tag}' contains invalid characters. Use only letters, numbers, spaces, & and -.")
    
    return unique_tags