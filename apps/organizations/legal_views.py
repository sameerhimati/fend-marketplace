from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.utils import timezone
from django.contrib import messages
from django.template.loader import render_to_string
from apps.core.services import LegalDocumentService

def legal_portal_homepage(request):
    """Legal portal homepage showing all available legal documents"""
    documents = LegalDocumentService.get_all_documents()
    
    context = {
        'documents': documents,
        'page_title': 'Legal Portal',
        'page_description': 'Access all FEND AI legal documents and agreements'
    }
    return render(request, 'legal/portal_homepage.html', context)

def legal_document_full(request, document_type):
    """Display full legal document content on web page"""
    # Get document configuration
    context = LegalDocumentService.get_document_context(document_type, show_acceptance=False)
    
    # Get full document content
    full_content = LegalDocumentService.get_full_document_content(document_type)
    
    if full_content.startswith("Full legal document content not available"):
        # Document not found
        context['error'] = True
        context['error_message'] = f"Document '{document_type}' not found"
    else:
        # Format content with proper HTML headings and structure
        formatted_content = LegalDocumentService.format_legal_content(full_content)
        context['full_content'] = formatted_content
        context['show_full_content'] = True
    
    return render(request, 'legal/document_full.html', context)



@login_required
@require_http_methods(["POST"])
def accept_legal_document(request):
    """AJAX endpoint to accept a legal document"""
    if not request.user.organization:
        return JsonResponse({'error': 'No organization found'}, status=400)
    
    document_type = request.POST.get('document_type')
    if not document_type:
        return JsonResponse({'error': 'Document type required'}, status=400)
    
    organization = request.user.organization
    
    # Accept the document
    success = organization.accept_legal_document(document_type)
    
    if success:
        return JsonResponse({
            'success': True,
            'message': f'{document_type.replace("_", " ").title()} accepted successfully',
            'accepted_at': timezone.now().isoformat()
        })
    else:
        return JsonResponse({'error': 'Failed to accept document'}, status=400)

@login_required
def legal_status(request):
    """Check legal document acceptance status"""
    if not request.user.organization:
        return JsonResponse({'error': 'No organization found'}, status=400)
    
    org = request.user.organization
    
    status = {
        'terms_of_service': {
            'accepted': org.terms_of_service_accepted,
            'accepted_at': org.terms_of_service_accepted_at.isoformat() if org.terms_of_service_accepted_at else None
        },
        'privacy_policy': {
            'accepted': org.privacy_policy_accepted,
            'accepted_at': org.privacy_policy_accepted_at.isoformat() if org.privacy_policy_accepted_at else None
        },
        'user_agreement': {
            'accepted': org.user_agreement_accepted,
            'accepted_at': org.user_agreement_accepted_at.isoformat() if org.user_agreement_accepted_at else None
        },
        'payment_terms': {
            'accepted': org.payment_terms_accepted,
            'accepted_at': org.payment_terms_accepted_at.isoformat() if org.payment_terms_accepted_at else None
        },
        'payment_holding_agreement': {
            'accepted': org.payment_holding_agreement_accepted,
            'accepted_at': org.payment_holding_agreement_accepted_at.isoformat() if org.payment_holding_agreement_accepted_at else None
        },
        'has_required_acceptances': org.has_required_legal_acceptances(),
        'has_payment_acceptances': org.has_payment_legal_acceptances(),
        'has_deals_acceptances': org.has_deals_legal_acceptances(),
    }
    
    # Add EU-specific status if applicable
    if org.is_eu_based():
        status['data_processing_agreement'] = {
            'accepted': org.data_processing_agreement_accepted,
            'accepted_at': org.data_processing_agreement_accepted_at.isoformat() if org.data_processing_agreement_accepted_at else None
        }
    
    return JsonResponse(status)
