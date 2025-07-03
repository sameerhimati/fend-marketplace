from django import template
from django.utils.safestring import mark_safe
import re

register = template.Library()


@register.filter
def normalize_url(url):
    """
    Normalize a URL by adding https:// if no protocol is present.
    Handles various input formats gracefully.
    """
    if not url:
        return ""
    
    url = url.strip()
    
    # If already has protocol, return as-is
    if url.startswith(('http://', 'https://')):
        return url
    
    # Add https:// prefix
    return f"https://{url}"


@register.filter  
def clean_url_display(url):
    """
    Clean URL for display purposes - remove protocol and www.
    """
    if not url:
        return ""
    
    cleaned = url.strip()
    
    # Remove protocol
    cleaned = re.sub(r'^https?://', '', cleaned)
    
    # Remove www.
    cleaned = re.sub(r'^www\.', '', cleaned)
    
    # Remove trailing slash
    cleaned = cleaned.rstrip('/')
    
    return cleaned


@register.filter
def company_link(organization, link_text="Visit Company"):
    """
    Generate a beautiful company link with icon.
    """
    if not organization or not organization.website:
        return ""
    
    clean_url = normalize_url(organization.website)
    display_text = clean_url_display(organization.website)
    
    # Truncate very long URLs for display
    if len(display_text) > 25:
        display_text = display_text[:22] + "..."
    
    return mark_safe(f'''
        <a href="{clean_url}" 
           target="_blank" 
           rel="noopener noreferrer"
           class="inline-flex items-center space-x-2 text-indigo-600 hover:text-indigo-800 transition-colors group">
            <svg class="w-4 h-4 group-hover:translate-x-0.5 transition-transform" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14"/>
            </svg>
            <span class="font-medium">{link_text}</span>
            <span class="text-xs text-gray-500">({display_text})</span>
        </a>
    ''')


@register.filter
def simple_company_link(organization):
    """
    Styled company button for directory cards - clean and professional.
    """
    if not organization or not organization.website:
        return ""
    
    clean_url = normalize_url(organization.website)
    display_text = clean_url_display(organization.website)
    
    return mark_safe(f'''
        <a href="{clean_url}" 
           target="_blank" 
           rel="noopener noreferrer"
           class="inline-flex items-center px-3 py-1.5 bg-gray-50 hover:bg-gray-100 border border-gray-200 rounded-md text-sm font-medium text-gray-700 hover:text-gray-900 transition-colors group">
            <svg class="w-3.5 h-3.5 mr-1.5 text-gray-400 group-hover:text-gray-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14"/>
            </svg>
            Visit Company
        </a>
    ''')