from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, HttpResponse
from django.views.decorators.http import require_http_methods
from django.utils import timezone
from django.contrib import messages
from django.template.loader import render_to_string

@login_required
def terms_of_service(request):
    """Display Terms of Service"""
    # Only show acceptance in workflow contexts, not when browsing from footer
    show_acceptance = False
    return render(request, 'legal/terms_of_service.html', {'show_acceptance': show_acceptance})

@login_required  
def privacy_policy(request):
    """Display Privacy Policy"""
    # Only show acceptance in workflow contexts, not when browsing from footer
    show_acceptance = False
    return render(request, 'legal/privacy_policy.html', {'show_acceptance': show_acceptance})

@login_required
def user_agreement(request):
    """Display User Agreement"""
    # Only show acceptance in workflow contexts, not when browsing from footer
    show_acceptance = False
    return render(request, 'legal/user_agreement.html', {'show_acceptance': show_acceptance})

@login_required
def payment_terms(request):
    """Display Payment Terms"""
    # Only show acceptance in workflow contexts, not when browsing from footer
    show_acceptance = False
    return render(request, 'legal/payment_terms.html', {'show_acceptance': show_acceptance})

@login_required
def payment_holding_agreement(request):
    """Display Payment Holding Service Agreement"""
    # Only show acceptance in workflow contexts, not when browsing from footer
    show_acceptance = False
    return render(request, 'legal/payment_holding_agreement.html', {'show_acceptance': show_acceptance})

@login_required
def data_processing_agreement(request):
    """Display Data Processing Agreement (for EU users)"""
    # Only show acceptance in workflow contexts, not when browsing from footer
    show_acceptance = False
    return render(request, 'legal/data_processing_agreement.html', {'show_acceptance': show_acceptance})

@login_required
def product_listing_agreement(request):
    """Display Product Listing and Commission Agreement"""
    # Only show acceptance in workflow contexts, not when browsing from footer
    show_acceptance = False
    return render(request, 'legal/product_listing_agreement.html', {'show_acceptance': show_acceptance})

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

@login_required
def download_legal_document(request, document_type):
    """Generate and download full legal document as text file"""
    
    def get_full_document_content(doc_type):
        """Return full legal document content"""
        
        if doc_type == 'terms-of-service':
            return """FEND AI, INC. TERMS OF SERVICE
Effective Date: June 24, 2025
Version: 1.40

1. ACCEPTANCE OF TERMS

By accessing, browsing, or using the FEND AI Platform (the "Platform"), creating an account, or accepting any FEND services, you acknowledge that you have read, understood, and agree to be bound by these Terms of Service ("Terms") and our Privacy Policy. If you do not agree to these Terms, you may not use the Platform.

2. ABOUT FEND AI

FEND AI, Inc. ("FEND," "we," "us," or "our") operates a B2B marketplace platform that connects enterprises seeking innovative solutions with startups offering cutting-edge technology. Our Platform facilitates pilot program lifecycles from discovery to completion, featuring an integrated escrow payment system and subscription model.

3. PLATFORM SERVICES

3.1 Core Services
- B2B pilot project marketplace connecting enterprises and startups
- Secure escrow payment processing for all pilot transactions
- Business verification and intelligent matching algorithms
- Comprehensive project management and collaboration tools
- Quality assurance frameworks and performance analytics
- Subscription-based access with tiered pricing models

3.2 User Categories
- Startup Users: Companies with fewer than 500 employees who bid on pilot opportunities
- Enterprise Partners: Companies with 500+ employees who post pilot opportunities
- Automatic upgrade from Startup to Enterprise pricing when company reaches 500+ employees

3.3 Subscription Plans
- Startup Plans: $10/month or $100/year for unlimited bidding
- Enterprise Plans: $100/month (5 pilots) or $1000/year (unlimited pilots)
- All plans include platform access, basic support, and core features

4. PLATFORM FEES AND PAYMENT STRUCTURE

4.1 Transaction Fees
- Total platform fee: 10% (5% from enterprise, 5% from startup)
- Enterprise Creator pays 105% upfront (100% pilot value + 5% platform fee)
- Startup Completer receives 95% upon completion (5% platform fee deducted)
- Cancellation fee: 1.5% of pilot value for cancelled projects

4.2 Payment Protection
- All pilot payments held in secure escrow until completion approval
- FDIC-insured accounts with segregated fund management
- 60-day review period for completion verification
- Automatic dispute escalation if no approval within review period

5. USER RESPONSIBILITIES

5.1 Account Requirements
- Provide accurate business information including EIN
- Maintain active subscription for platform access
- Ensure authorized personnel conduct all platform activities
- Notify FEND of changes in company size (for plan upgrades)

5.2 Platform Usage
- Follow pilot completion requirements and Definition of Done
- Respect confidentiality obligations and business information
- Comply with platform usage rules and community standards
- Respond to communications within reasonable timeframes

5.3 Business Verification
- Submit required corporate documentation
- Maintain current business registration and licensing
- Provide accurate contact information and project details
- Comply with applicable laws and regulations

6. INTELLECTUAL PROPERTY

6.1 Platform Ownership
- FEND retains all rights to Platform software, design, and functionality
- Users retain ownership of their business information and project deliverables
- Platform-generated analytics and matching data remains FEND property

6.2 User Content
- Users grant FEND license to use business information for platform operations
- Project communications and deliverables remain property of respective parties
- Users responsible for ensuring they have rights to all submitted content

7. PRIVACY AND DATA PROTECTION

7.1 Privacy Practices
- Data collection and use governed by our Privacy Policy
- Business information used for platform operations and matching
- Industry-standard encryption and security measures
- GDPR compliance for EU-based users through Data Processing Agreement

7.2 Confidentiality
- Platform facilitates confidential business discussions
- Users responsible for their own confidentiality agreements
- FEND maintains confidentiality of business information per Privacy Policy

8. PROHIBITED ACTIVITIES

8.1 Platform Misuse
- Circumventing payment systems or fee structures
- Creating multiple accounts to avoid restrictions
- Sharing account credentials or unauthorized access
- Interfering with platform functionality or other users

8.2 Business Conduct
- Misrepresenting company information or capabilities
- Engaging in fraudulent or deceptive practices
- Violating intellectual property rights
- Conducting illegal activities through the platform

9. TERMINATION AND SUSPENSION

9.1 Account Termination
- Either party may terminate account with 30 days written notice
- FEND may suspend accounts for Terms violations
- Outstanding pilot commitments must be completed or properly transferred
- Refunds processed according to our refund policy

9.2 Effect of Termination
- Access to platform immediately revoked
- Outstanding payments processed according to escrow terms
- Data retention according to Privacy Policy and legal requirements

10. LIMITATION OF LIABILITY

TO THE MAXIMUM EXTENT PERMITTED BY LAW, FEND'S LIABILITY IS LIMITED TO THE FEES PAID BY USER IN THE 12 MONTHS PRECEDING THE CLAIM. FEND IS NOT LIABLE FOR INDIRECT, INCIDENTAL, CONSEQUENTIAL, OR PUNITIVE DAMAGES.

11. DISPUTE RESOLUTION

11.1 Pilot Disputes
- Platform provides mediation services for pilot-related disputes
- Escalation procedures for unresolved completion disagreements
- Final resolution through binding arbitration if mediation fails

11.2 Platform Disputes
- Good faith negotiation required before formal proceedings
- Binding arbitration under Delaware law for platform-related disputes
- Class action waiver - disputes resolved individually

12. GOVERNING LAW

These Terms are governed by Delaware law without regard to conflict of law principles. Exclusive jurisdiction in Delaware courts for any disputes not subject to arbitration.

13. CHANGES TO TERMS

FEND may modify these Terms with 30 days notice to users. Continued use after notice period constitutes acceptance of modified Terms. Material changes require explicit user acceptance.

14. CONTACT INFORMATION

For legal matters:
Email: legal@thefend.com
Phone: (650) 735-2255

For general support:
Email: support@thefend.com
Email: business@thefend.com

FEND AI, Inc.
131 Continental Dr Suite 305
Newark, DE 19713, USA

15. ENTIRE AGREEMENT

These Terms, together with our Privacy Policy, Payment Terms, Payment Holding Service Agreement, User Agreement, and (for EU users) Data Processing Agreement, constitute the entire agreement between you and FEND regarding use of the Platform.

© 2025 FEND AI, Inc. All rights reserved.
Document Version: 1.40 • Effective Date: June 24, 2025"""

        elif doc_type == 'privacy-policy':
            return """FEND AI, INC. PRIVACY POLICY
Effective Date: June 24, 2025
Version: 1.7

1. INTRODUCTION

FEND AI, Inc. ("FEND," "we," "us," or "our") is committed to protecting the privacy and security of business information provided by users of our B2B marketplace platform. This Privacy Policy explains how we collect, use, disclose, and safeguard business and personal information in connection with our Platform services.

2. INFORMATION WE COLLECT

2.1 Business Account Information
- Company name, address, and business registration details
- Employer Identification Number (EIN) and tax information
- Business contact information including names, email addresses, phone numbers
- Job titles and roles of authorized platform users
- Company size, industry classification, and business descriptions

2.2 Platform Usage Data
- Login credentials and account authentication information
- Platform navigation patterns and feature usage analytics
- Project communications and collaboration data
- Payment processing and transaction information
- Device information, IP addresses, and browser details

2.3 Project and Communication Data
- Pilot project descriptions, requirements, and specifications
- Bid submissions, proposals, and project deliverables
- Platform messaging, comments, and business communications
- File uploads, documents, and project-related materials
- Performance metrics and completion verification data

2.4 Payment and Billing Information
- Bank account information for ACH transfers and wire payments
- Corporate credit card information for subscription payments
- Billing addresses and payment authorization contacts
- Transaction history and payment processing records
- Escrow account activity and fund transfer details

3. HOW WE USE INFORMATION

3.1 Platform Operations
- User authentication and account management
- Business matching and pilot opportunity recommendations
- Project management and collaboration facilitation
- Payment processing and escrow services
- Customer support and technical assistance

3.2 Business Analytics
- Platform performance monitoring and optimization
- User engagement analysis and feature development
- Business matching algorithm improvement
- Market research and industry trend analysis
- Quality assurance and fraud prevention

3.3 Legal and Compliance
- Compliance with applicable laws and regulations
- Response to legal process and government requests
- Protection of FEND's rights and property
- Enforcement of Terms of Service and platform policies
- Tax reporting and financial record maintenance

4. INFORMATION SHARING AND DISCLOSURE

4.1 Business Matching
- Company profiles shared with potential pilot partners
- Project information disclosed to qualified bidders
- Business contact information for approved partnerships
- Performance history for reputation and trust building

4.2 Service Providers
- Payment processors for transaction handling
- Cloud hosting providers for data storage and platform operations
- Analytics services for platform performance monitoring
- Customer support tools for user assistance

4.3 Legal Requirements
- Compliance with court orders, subpoenas, and legal process
- Cooperation with law enforcement and regulatory investigations
- Protection of rights, property, and safety of FEND and users
- Response to government requests and regulatory compliance

4.4 Business Transfers
- In connection with mergers, acquisitions, or sale of business assets
- Transfer to successor entities or acquiring companies
- Due diligence processes for potential business transactions

5. DATA SECURITY AND PROTECTION

5.1 Technical Safeguards
- Industry-standard encryption for data transmission and storage
- Multi-factor authentication for account access
- Regular security monitoring and vulnerability assessments
- Secure data centers with physical access controls
- Regular data backups and disaster recovery procedures

5.2 Access Controls
- Role-based access permissions for platform features
- Regular review and audit of user access privileges
- Secure authentication protocols and session management
- Monitoring and logging of data access activities

5.3 Employee Training
- Regular security awareness training for all staff
- Confidentiality agreements and privacy obligations
- Background checks for employees with data access
- Incident response procedures and breach notification protocols

6. DATA RETENTION

6.1 Retention Periods
- Active account data retained for duration of business relationship
- Financial records maintained for 7 years per business requirements
- Communication history preserved for legal and audit purposes
- Platform usage analytics retained for business optimization

6.2 Data Deletion
- Account closure triggers data deletion procedures
- Users may request data deletion subject to legal obligations
- Automated deletion of temporary files and cache data
- Secure disposal of backup media and archived information

7. INTERNATIONAL DATA TRANSFERS

7.1 Cross-Border Processing
- Data may be processed in United States and other countries
- Adequate data protection measures for international transfers
- Standard Contractual Clauses for transfers to third countries
- Compliance with applicable data protection regulations

7.2 EU Data Protection
- GDPR compliance for European Union users
- Data Processing Agreement automatically applies to EU customers
- Lawful basis for processing business and personal data
- Right to lodge complaints with supervisory authorities

8. YOUR RIGHTS AND CHOICES

8.1 Access and Control
- Right to access personal and business information we maintain
- Ability to update and correct account information
- Options to control communication preferences and notifications
- Right to request data portability in standard electronic formats

8.2 EU/GDPR Rights (for EU users)
- Right to rectification of inaccurate personal data
- Right to erasure (deletion) subject to legal obligations
- Right to restrict processing activities
- Right to data portability
- Right to withdraw consent where applicable
- Right to object to processing for legitimate interests

8.3 Marketing Communications
- Opt-out options for promotional emails and communications
- Granular control over notification types and frequency
- Respect for communication preferences across all channels

9. COOKIES AND TRACKING TECHNOLOGIES

9.1 Cookie Usage
- Essential cookies for platform functionality and security
- Analytics cookies for performance monitoring and optimization
- Preference cookies for user interface customization
- Session cookies for authentication and navigation

9.2 Third-Party Services
- Integration with business analytics and monitoring services
- Customer support chat and help desk functionality
- Payment processing and fraud prevention services
- Social media integration for business networking

10. CHILDREN'S PRIVACY

The Platform is designed exclusively for business-to-business use and is not intended for individuals under 18 years of age. We do not knowingly collect personal information from minors.

11. CHANGES TO PRIVACY POLICY

We may update this Privacy Policy periodically to reflect changes in our practices or applicable law. Material changes will be communicated through platform notifications or email, with continued use constituting acceptance of updated terms.

12. CONTACT INFORMATION

For privacy-related questions, data access requests, or concerns:

Privacy Officer:
Email: privacy@thefend.com
Phone: (650) 735-2255

General Support:
Email: support@thefend.com

EU Data Protection Officer:
Email: privacy@thefend.com
(For GDPR requests, data access, rectification, erasure, or portability)

FEND AI, Inc.
131 Continental Dr Suite 305
Newark, DE 19713, USA

For EU users: You have the right to lodge a complaint with your local supervisory authority if you believe our processing of your personal data violates applicable data protection law.

© 2025 FEND AI, Inc. All rights reserved.
Document Version: 1.7 • Effective Date: June 24, 2025"""

        elif doc_type == 'user-agreement':
            return """FEND AI, INC. USER AGREEMENT
Effective Date: June 24, 2025
Version: 1.20

1. AGREEMENT SCOPE

This User Agreement supplements the FEND AI Terms of Service and provides additional terms specific to your selected user category. In case of conflict, the Terms of Service controls. By creating an account, you agree to this User Agreement, the Terms of Service, Privacy Policy, Payment Terms, and Payment Holding Service Agreement. EU-based companies also automatically accept the Data Processing Agreement.

2. USER CATEGORIES

2.1 Startup Users
Companies with fewer than 500 employees. Select Startup plan pricing during registration.

2.2 Enterprise Partner Users
Companies with 500 or more employees. Select Enterprise Partner plan pricing during registration.

3. CATEGORY-SPECIFIC REQUIREMENTS

3.1 Startup User Requirements
- Provide accurate employee count and company documentation including EIN
- Notify FEND when company reaches 500+ employees
- Automatic upgrade to Enterprise Partner pricing at next renewal when exceeding 500 employees
- Access to standard Platform features and Service Level Agreement commitments
- Eligible for payment holding services with standard processing timeframes
- May participate in Product Listing and Commission program subject to separate agreement

3.2 Enterprise Partner User Requirements
- Provide corporate documentation including EIN and certificate of incorporation
- Ensure authorized personnel conduct all Platform activities
- Maintain corporate compliance standards for all Platform use
- Receive enhanced Service Level Agreement commitments and priority support
- Access to enterprise-grade payment holding services with expedited processing
- Enhanced GDPR compliance support for EU-based Enterprise Partners
- Priority access to Product Listing and Commission program features

4. SUBSCRIPTION PLANS AND BILLING

4.1 Startup Plans
- Monthly: $10/month for unlimited bidding on pilot opportunities
- Annual: $100/year for unlimited bidding (equivalent to $8.33/month)
- Includes standard platform access, basic support, and core features
- Standard response time for customer support during business hours

4.2 Enterprise Partner Plans
- Monthly: $100/month for up to 5 pilot postings
- Annual: $1000/year for unlimited pilot postings (equivalent to $83.33/month)
- Includes priority support, enhanced SLA, and advanced features
- Expedited payment processing and dedicated account management for high-volume users

4.3 Plan Upgrades
- Startups automatically upgrade to Enterprise pricing when reaching 500+ employees
- Upgrade effective at next billing cycle after employee threshold reached
- No downgrade available from Enterprise to Startup pricing
- Grandfathered pricing maintained for existing contracts until renewal

5. PLATFORM ACCESS AND FEATURES

5.1 Core Platform Features (All Users)
- Account creation and business profile management
- Platform navigation and basic search functionality
- Secure messaging and communication tools
- Document upload and basic file management
- Payment processing through integrated escrow system

5.2 Startup-Specific Features
- Browse and search pilot opportunities posted by Enterprise Partners
- Submit bids and proposals for pilot projects
- Track bid status and manage active pilot engagements
- Access to standard project management and collaboration tools
- Basic analytics and performance tracking

5.3 Enterprise Partner-Specific Features
- Create and post pilot opportunities with detailed requirements
- Review and evaluate bids from qualified Startup Users
- Advanced search and filtering for startup partner discovery
- Enhanced project management and milestone tracking
- Priority customer support with dedicated account management
- Advanced analytics and reporting capabilities

6. SERVICE LEVEL AGREEMENTS

6.1 Startup User SLA
- Platform uptime: 99.5% monthly availability
- Customer support response: Within 24 hours during business hours
- Payment processing: Standard timeframes (2-3 business days for ACH)
- Feature updates: Regular quarterly releases with new functionality

6.2 Enterprise Partner SLA
- Platform uptime: 99.9% monthly availability with priority restoration
- Customer support response: Within 4 hours during business hours, 24-hour emergency support
- Payment processing: Expedited timeframes (same-day to 1 business day)
- Feature updates: Early access to beta features and monthly releases
- Dedicated account management for users with high transaction volumes

7. COMPLIANCE AND VERIFICATION

7.1 Business Verification Requirements
- Valid Employer Identification Number (EIN) for all users
- Business registration documentation and certificates of incorporation
- Authorized signatory verification for Enterprise Partners
- Regular compliance checks and documentation updates

7.2 EU Compliance (Applicable to EU-based Users)
- Automatic acceptance of Data Processing Agreement upon account creation
- GDPR compliance support and data protection assistance
- Enhanced data security measures and breach notification procedures
- Right to data portability and deletion requests

8. PAYMENT TERMS INTEGRATION

8.1 Subscription Billing
- Monthly plans billed in advance on account creation anniversary
- Annual plans billed in advance with automatic renewal
- Payment method updates required before billing date to avoid service interruption
- Refunds available within 30 days of initial subscription purchase

8.2 Transaction Fees
- Platform transaction fees apply to all completed pilot projects
- Fees automatically calculated and collected through escrow system
- No additional charges for subscription plan features
- Volume discounts available for Enterprise Partners with high transaction activity

9. CONTACT AND SUPPORT

9.1 Category-Specific Support
- Startup Users: Standard support channels during business hours
- Enterprise Partners: Priority support with enhanced SLA response times and dedicated account management for high-volume users

9.2 Contact Information
For all support requests, contact:
Email: support@thefend.com
Phone: (650) 735-2255

For legal matters:
Email: legal@thefend.com
FEND AI, Inc.
131 Continental Dr Suite 305
Newark, DE 19713, USA

10. TERMS MODIFICATION AND ACCEPTANCE

This User Agreement may be updated periodically with 30 days advance notice. Continued use of Platform services after notice period constitutes acceptance of modified terms. Material changes to subscription pricing or core features require explicit user acceptance.

By selecting your user category and clicking "I Agree," you accept this User Agreement, the Terms of Service, Privacy Policy, Payment Terms, Payment Holding Service Agreement, and if applicable, the Data Processing Agreement.

© 2025 FEND AI, Inc. All rights reserved.
Document Version: 1.20 • Effective Date: June 24, 2025"""

        elif doc_type == 'payment-terms':
            return """FEND AI, INC. PAYMENT TERMS
Effective Date: June 24, 2025
Version: 1.12

1. PAYMENT STRUCTURE OVERVIEW

1.1 Platform Fee Structure
FEND operates on a dual-fee model where both Enterprise Creators and Startup Completers contribute to platform sustainability:
- Total Platform Fee: 10% (split equally between parties)
- Enterprise Creator Fee: 5% (paid upfront with pilot funding)
- Startup Completer Fee: 5% (deducted from payment upon completion)

1.2 Payment Flow Process
- Enterprise Creator funds 105% of pilot value (100% pilot + 5% platform fee)
- Funds held in secure escrow until pilot completion approval
- Startup Completer receives 95% of pilot value (5% platform fee deducted)
- Payment released within 2 business days of completion approval

2. ENTERPRISE CREATOR PAYMENT RESPONSIBILITIES

2.1 Upfront Payment Requirements
- Must fund escrow account with 105% of stated pilot value before pilot activation
- Payment must be received and verified before pilot goes live
- Accepted payment methods: ACH transfers (preferred), wire transfers, corporate checks
- International payments supported with USD conversion at current exchange rates

2.2 Payment Processing Timeframes
- ACH transfers: 2-3 business days processing
- Wire transfers: 1-2 business days processing
- Corporate checks: 5-7 business days clearing period
- International wire transfers: 3-5 business days processing

2.3 Cancellation Terms
- Pilot cancellation fee: 1.5% of pilot value
- Full refund available if pilot cancelled before startup selection
- Partial refund available if cancelled during early project phases
- No refund if cancellation occurs after 50% milestone completion

3. STARTUP COMPLETER PAYMENT TERMS

3.1 Payment Calculation
- Receive 95% of stated pilot value upon completion approval
- 5% platform fee automatically deducted from final payment
- No upfront fees or charges for participating in pilot opportunities
- Milestone payments available for large projects (subject to enterprise approval)

3.2 Payment Methods and Processing
- Primary method: ACH direct deposit to business bank account
- Alternative method: Wire transfer for international recipients
- Payment processing time: 2 business days for ACH, 1 business day for wire
- Minimum payment threshold: $100 (smaller amounts held until threshold met)

3.3 Payment Protection
- Funds secured in escrow throughout pilot duration
- Protection against non-payment through verified funding requirements
- Dispute resolution support for payment-related issues
- Full payment guarantee upon completion verification

4. ACCEPTED PAYMENT METHODS

4.1 For Enterprise Creators (Pilot Funding)
- ACH Bank Transfers (preferred method - lowest fees)
- Corporate Checks (subject to clearing periods)
- Domestic Wire Transfers
- International Wire Transfers with USD conversion

4.2 For Startup Completers (Payment Receipt)
- ACH Direct Deposit (standard method)
- Wire Transfer (for international recipients or special circumstances)
- Corporate checks available upon request for amounts over $10,000

4.3 International Payment Support
- Multi-currency support with automatic USD conversion
- Competitive exchange rates updated daily
- International wire transfer capabilities
- Compliance with international banking regulations

5. ESCROW AND PAYMENT SECURITY

5.1 Fund Security Measures
- All pilot funds held in FDIC-insured business accounts
- Segregated accounting separating held funds from FEND operational funds
- Regular reconciliation and audit procedures
- Investment in highly liquid, FDIC-insured instruments only

5.2 Payment Release Conditions
- Enterprise Creator approval required for payment release
- 60-day automatic release if no objection raised
- Dispute escalation procedures for contested completions
- Mediation services available for payment disputes

6. SUBSCRIPTION BILLING TERMS

6.1 Startup Subscription Plans
- Monthly Plan: $10/month, billed monthly on account anniversary
- Annual Plan: $100/year, billed annually with automatic renewal
- Payment required in advance of billing period
- Service suspension for overdue accounts after 7-day grace period

6.2 Enterprise Partner Subscription Plans
- Monthly Plan: $100/month for up to 5 pilot postings
- Annual Plan: $1,000/year for unlimited pilot postings
- Advanced payment required for account activation
- Priority support and enhanced SLA included in all plans

6.3 Billing and Renewal
- Automatic renewal unless cancelled 30 days before renewal date
- Payment method updates required before renewal to avoid service interruption
- Pro-rated refunds available within 30 days of initial subscription
- Plan upgrades effective immediately with pro-rated billing adjustment

7. DISPUTE RESOLUTION AND REFUNDS

7.1 Payment Disputes
- Good faith negotiation required before formal dispute procedures
- Mediation services provided for payment-related disagreements
- Binding arbitration for unresolved disputes over $10,000
- Escrow funds frozen during active dispute resolution

7.2 Refund Policies
- Subscription refunds: Full refund within 30 days of initial purchase
- Pilot payment refunds: Available for cancelled pilots per cancellation terms
- Platform fee refunds: Not available except in cases of platform error
- Processing fee refunds: Available only for cancelled transactions

8. TAX RESPONSIBILITIES

8.1 Tax Reporting
- Annual 1099 forms issued to US-based recipients of payments over $600
- International payment reporting per applicable tax treaties
- Users responsible for all applicable income taxes
- FEND provides transaction summaries for tax preparation

8.2 Sales Tax
- Platform fees subject to applicable state and local sales taxes
- Tax rates determined by business location and applicable regulations
- International users subject to applicable VAT or GST requirements
- Tax-inclusive pricing displayed during checkout process

9. LATE PAYMENT AND COLLECTIONS

9.1 Late Payment Terms
- Subscription payments: 7-day grace period before service suspension
- Interest charges: 1.5% per month on overdue subscription balances
- Collection fees: Reasonable collection costs added to overdue amounts
- Account reinstatement available upon full payment of outstanding balance

9.2 Collections Procedures
- Email and phone reminders for overdue accounts
- Service suspension after grace period expiration
- Third-party collections for accounts over 90 days past due
- Legal action reserved for significant outstanding balances

10. PAYMENT MODIFICATIONS

Changes to payment terms require 30 days advance notice to all users. Continued use of Platform services after notice period constitutes acceptance of modified payment terms.

11. CONTACT INFORMATION

For payment support and questions:
Email: support@thefend.com
Phone: (650) 735-2255

For legal and compliance matters:
Email: legal@thefend.com

FEND AI, Inc.
131 Continental Dr Suite 305
Newark, DE 19713, USA

© 2025 FEND AI, Inc. All rights reserved.
Document Version: 1.12 • Effective Date: June 24, 2025"""

        elif doc_type == 'payment-holding-agreement':
            return """FEND AI, INC. PAYMENT HOLDING SERVICE AGREEMENT
Effective Date: June 24, 2025
Version: 2.0

1. AGREEMENT SCOPE AND INTEGRATION

This Payment Holding Service Agreement ("Holding Agreement") governs FEND AI's payment holding services for Pilot project payments and is incorporated into the FEND AI Terms of Service. By creating Pilots or accepting Pilot work, you agree to these payment holding terms.

2. PAYMENT HOLDING SERVICE OVERVIEW

FEND AI acts as payment holding service provider for all Pilot payments, securely holding funds from Pilot Creators and releasing them to Pilot Completers upon successful project completion according to the Definition of Done.

3. PAYMENT FUNDING REQUIREMENTS

3.1 Creator Funding Obligation
- Pilot Creators must fund payment holding account with 105% of stated Pilot value before Pilot goes live
- Payment includes: 100% Pilot value + 5% Creator platform fee
- Payment must be received via ACH transfer or other approved payment method
- Pilots remain inactive until full payment funding is confirmed

3.2 Accepted Payment Methods
- ACH bank transfers (preferred method)
- Corporate checks (subject to clearing periods)
- Wire transfers (for international transactions)
- Other payment methods as approved by FEND

4. PAYMENT RELEASE CONDITIONS

4.1 Completion Approval Process
- Pilot Completer submits deliverables according to Definition of Done
- Pilot Creator has 60 days to review and approve completion
- Creator clicks "Pilot Completed" button to authorize payment release
- Automatic dispute escalation if no approval within 60 days

4.2 Payment Release Calculation
- Pilot Completer receives 95% of stated Pilot value
- FEND retains 5% as Completer platform fee
- Example: $100,000 Pilot = $95,000 to Completer, $5,000 to FEND
- Creator's 5% platform fee was collected during payment funding

5. FUND SECURITY AND PROTECTION

5.1 Fund Security Measures
- All held funds maintained in FDIC-insured business accounts
- Segregated accounting maintains clear separation of held funds from FEND operating funds
- Regular reconciliation and audit procedures for all payment holding accounts
- Held funds invested only in FDIC-insured, highly liquid instruments

5.2 Dispute Protection
- Disputed funds remain in holding account until resolution through FEND's dispute process
- Neither party may claim disputed funds without proper resolution
- FEND may require additional documentation before releasing disputed payments
- Legal process required for any third-party claims against held funds

6. MILESTONE PAYMENTS

6.1 Milestone Payment Structure
- Large Pilots may be structured with milestone-based payments
- Each milestone requires separate Definition of Done and approval process
- Milestone payments released independently upon individual completion approval
- Remaining funds held in escrow until final project completion

6.2 Milestone Modification
- Milestone terms may be modified by mutual agreement of both parties
- All modifications must be documented and approved through Platform interface
- FEND reserves right to approve milestone modifications for fund security
- Modified milestones subject to same approval and release procedures

7. AUTOMATIC RELEASE PROCEDURES

7.1 60-Day Automatic Release
- Funds automatically released to Completer if Creator provides no response within 60 days
- Creator receives multiple notifications during review period
- Final 7-day warning before automatic release
- Creator may request dispute escalation during 60-day period to prevent automatic release

7.2 Dispute Escalation Prevention
- Creator must provide specific reasons for withholding approval
- FEND reviews dispute claims for validity and good faith
- Frivolous dispute claims may result in immediate payment release
- Mediation services available for legitimate completion disagreements

8. CANCELLATION AND REFUND PROCEDURES

8.1 Pilot Cancellation by Creator
- Creator may cancel Pilot before Completer selection with full refund minus 1.5% cancellation fee
- Cancellation after Completer selection subject to compensation requirements
- Cancellation after 50% completion requires full payment to Completer
- FEND retains cancellation fees and any earned platform fees

8.2 Pilot Abandonment by Completer
- Completer abandonment results in full refund to Creator minus platform fees
- Creator receives refund of original Pilot value (100% of stated amount)
- FEND retains earned platform fees and any applicable cancellation fees
- Abandoned work product transfers to Creator ownership

9. INTERNATIONAL PAYMENT CONSIDERATIONS

9.1 Currency Conversion
- All Pilot values denominated in US Dollars (USD)
- International payments converted to USD at current exchange rates
- Exchange rate risks borne by paying party
- FEND partners with established international payment processors

9.2 International Compliance
- Compliance with applicable international banking regulations
- Know Your Customer (KYC) and Anti-Money Laundering (AML) procedures
- Reporting requirements for international transactions over specified thresholds
- Cooperation with international regulatory and law enforcement requests

10. ACCOUNT RECONCILIATION AND REPORTING

10.1 Account Reconciliation
- Monthly reconciliation of all payment holding accounts
- Independent audit procedures performed quarterly
- Transaction logs maintained for all payment holding activities
- Discrepancy resolution procedures for any account inconsistencies

10.2 User Reporting
- Real-time payment status available through Platform interface
- Monthly statements for users with payment holding activity
- Annual summaries for tax reporting purposes
- Transaction history downloadable in multiple formats

11. EMERGENCY PROCEDURES

11.1 Platform Disruption
- Emergency procedures for payment release during Platform outages
- Alternative communication methods for urgent payment issues
- Manual processing capabilities for critical payment situations
- Business continuity plans for extended service disruptions

11.2 Legal and Regulatory Compliance
- Procedures for compliance with court orders and legal process
- Cooperation with law enforcement investigations
- Regulatory examination cooperation and documentation
- User notification procedures for legal holds on funds

12. FEES AND CHARGES

12.1 Payment Holding Fees
- No additional fees for standard payment holding services
- Platform fees collected as part of standard transaction processing
- Wire transfer fees passed through to requesting party
- Currency conversion fees applied to international transactions

12.2 Special Services
- Expedited payment processing available for additional fee
- Enhanced dispute resolution services available for complex cases
- Additional documentation and reporting services available upon request
- Custom payment structures subject to additional service fees

13. TERMINATION OF PAYMENT HOLDING SERVICES

13.1 Service Termination
- Payment holding services terminate upon completion of all active Pilots
- Users may not terminate services while funds are held in escrow
- FEND may terminate services for Terms of Service violations
- Orderly wind-down procedures for service termination

13.2 Account Closure
- All funds must be properly released before account closure
- Final reconciliation required before account termination
- Record retention requirements continue after account closure
- Dispute procedures remain available for specified period after closure

14. CONTACT INFORMATION

For all payment holding service questions, disputes, or issues:
Email: support@thefend.com
Phone: (650) 735-2255

Legal and Compliance:
Email: legal@thefend.com
FEND AI, Inc.
131 Continental Dr Suite 305
Newark, DE 19713, USA

By funding a Pilot payment holding account or accepting Pilot work, you agree to these payment holding terms and acknowledge FEND AI as your payment holding service provider for Platform transactions.

© 2025 FEND AI, Inc. All rights reserved.
Document Version: 2.0 • Effective Date: June 24, 2025"""

        elif doc_type == 'data-processing-agreement':
            return """FEND AI, INC. DATA PROCESSING AGREEMENT
Effective Date: June 24, 2025
Version: 1.5

1. AGREEMENT SCOPE AND APPLICATION

This Data Processing Agreement ("DPA") governs the processing of personal data by FEND AI, Inc. ("FEND," "Processor") on behalf of European Union business customers ("Controller," "Customer") in connection with the FEND AI Platform services. This DPA supplements and forms part of the FEND AI Terms of Service and Privacy Policy.

2. DEFINITIONS

For purposes of this DPA:
- "Controller" means the EU business customer that determines the purposes and means of processing personal data
- "Processor" means FEND AI, Inc. acting on behalf of and under instructions from Controller
- "Data Subject" means identified or identifiable employees, contractors, or authorized users of Controller
- "Personal Data" means any information relating to an identified or identifiable Data Subject as defined under GDPR
- "Processing" means any operation performed on personal data as defined under GDPR
- "GDPR" means Regulation (EU) 2016/679 of the European Parliament and of the Council

3. DATA PROCESSING DETAILS

3.1 Categories of Data Subjects
- Employees and contractors of Controller authorized to use the Platform
- Authorized representatives and contact persons designated by Controller
- Business contacts and project stakeholders identified by Controller

3.2 Categories of Personal Data Processed
- Contact Information: Names, business email addresses, business phone numbers, job titles
- Account Information: User credentials, account settings, authorization levels
- Communication Data: Platform messages, project communications, business correspondence
- Technical Data: IP addresses, browser information, Platform usage logs
- Payment Data: Billing contact information, payment authorization details

3.3 Purposes of Processing
- User authentication and account management
- Platform functionality and service delivery
- Business matching and pilot opportunity facilitation
- Communication and collaboration support
- Payment processing and financial services
- Customer support and technical assistance
- Legal compliance and regulatory requirements

4. PROCESSOR OBLIGATIONS

4.1 Processing Instructions
- Process personal data only on documented instructions from Controller
- Immediately inform Controller if instructions violate GDPR or other EU data protection laws
- Not process personal data for FEND's own purposes outside of Platform service delivery
- Delete or return personal data upon termination of services unless legal retention required

4.2 Confidentiality and Security
- Ensure persons authorized to process personal data are bound by confidentiality obligations
- Implement appropriate technical and organizational measures to secure personal data
- Maintain confidentiality of personal data except as required by EU or Member State law
- Notify Controller immediately of any personal data breaches

4.3 Sub-Processing
- Obtain Controller's prior written consent for any sub-processors
- Impose same data protection obligations on sub-processors through written contracts
- Remain fully liable to Controller for performance of sub-processor obligations
- Maintain current list of sub-processors available to Controller upon request

5. DATA SUBJECT RIGHTS SUPPORT

5.1 Data Subject Requests
When FEND receives Data Subject requests directly, FEND shall:
- Forward the request to Controller within 2 business days
- Provide reasonable assistance to Controller in responding to the request
- Not respond directly to Data Subjects unless specifically instructed by Controller

5.2 Technical Assistance
FEND shall provide technical assistance to Controller for:
- Access Requests: Providing copies of personal data in FEND's systems
- Rectification: Correcting inaccurate personal data upon Controller instruction
- Erasure: Deleting personal data upon Controller instruction, subject to legal retention requirements
- Data Portability: Providing personal data in commonly used electronic format
- Restriction: Limiting processing activities upon Controller request

6. SECURITY MEASURES

6.1 Technical Safeguards
- Encryption: Personal data encrypted in transit and at rest using industry-standard encryption
- Access Controls: Multi-factor authentication and role-based access controls for Platform access
- Network Security: Firewalls, intrusion detection systems, and regular security monitoring
- Data Backup: Regular encrypted backups with secure storage and tested recovery procedures

6.2 Organizational Measures
- Employee training on data protection and privacy requirements
- Background checks for employees with access to personal data
- Incident response procedures and breach notification protocols
- Regular security assessments and vulnerability testing

7. DATA BREACH NOTIFICATION

7.1 Breach Response
- Notify Controller of personal data breaches within 72 hours of becoming aware
- Provide all relevant information about the breach, affected Data Subjects, and response measures
- Cooperate with Controller in breach investigation and regulatory notification requirements
- Implement immediate measures to contain and mitigate breach impact

7.2 Documentation
- Maintain records of all personal data breaches, including facts, effects, and remedial action taken
- Provide breach documentation to Controller and regulatory authorities upon request
- Assist Controller with Data Subject notification requirements where applicable

8. DATA PROTECTION IMPACT ASSESSMENTS

8.1 DPIA Support
- Provide information necessary for Controller to conduct Data Protection Impact Assessments
- Assist with DPIA preparation when Platform processing presents high privacy risks
- Implement additional safeguards identified through DPIA process
- Cooperate with supervisory authority consultations when required

9. INTERNATIONAL DATA TRANSFERS

9.1 Transfer Mechanisms
- Processing may occur in United States and other countries outside European Economic Area
- Standard Contractual Clauses implemented for transfers to countries without adequacy decisions
- Additional safeguards implemented where required by supervisory authority guidance
- Regular review of transfer mechanisms for continued compliance

9.2 Transfer Documentation
- Maintain documentation of all international transfer mechanisms
- Update transfer documentation promptly following regulatory guidance changes
- Provide transfer documentation to Controller and supervisory authorities upon request

10. AUDITS AND COMPLIANCE

10.1 Audit Rights
- Controller may audit FEND's compliance with this DPA upon reasonable notice
- FEND shall provide reasonable assistance and access for audit activities
- Third-party audits acceptable with appropriate confidentiality protections
- Audit costs borne by Controller unless material non-compliance discovered

10.2 Compliance Monitoring
- Regular internal compliance assessments and documentation
- Annual compliance reporting to Controllers upon request
- Prompt implementation of corrective measures for any compliance gaps
- Cooperation with supervisory authority examinations and investigations

11. SUB-PROCESSORS

11.1 Current Sub-Processors
FEND currently engages the following categories of sub-processors:
- Cloud hosting and infrastructure providers
- Payment processing and financial services
- Customer support and help desk services
- Analytics and monitoring services

11.2 Sub-Processor Changes
- Written notice to Controllers at least 30 days before new sub-processor engagement
- Controllers may object to new sub-processors within notice period
- Alternative arrangements or service termination available if Controller objects
- Updated sub-processor list maintained and available to Controllers

12. TERM AND TERMINATION

12.1 Term
This DPA remains in effect for the duration of Platform services and any applicable retention periods.

12.2 Termination Obligations
- Delete or return all personal data upon service termination unless legal retention required
- Provide certification of deletion or return upon Controller request
- Continue to protect personal data during any required retention period
- Assist with data migration to new processor if requested by Controller

13. LIABILITY AND INDEMNIFICATION

13.1 Liability Limitation
- FEND's liability limited to direct damages caused by FEND's breach of this DPA
- Liability cap consistent with Terms of Service unless superseded by mandatory law
- No liability for damages caused by Controller's instructions or third-party actions

13.2 Regulatory Compliance
- Each party responsible for compliance with applicable data protection laws
- Cooperation in responding to supervisory authority investigations and enforcement actions
- Shared responsibility for Data Subject compensation where both parties at fault

14. GOVERNING LAW AND DISPUTE RESOLUTION

14.1 Governing Law
This DPA governed by laws of Ireland for EU data protection matters, Delaware law for other provisions.

14.2 Dispute Resolution
- Good faith negotiation for DPA-related disputes
- Supervisory authority consultation available for data protection disputes
- Arbitration or court proceedings for unresolved commercial disputes

15. CONTACT INFORMATION

15.1 Data Protection Officer
FEND Data Protection Officer
Email: privacy@thefend.com
Phone: (650) 735-2255

15.2 Legal and Compliance
FEND Legal Department
Email: legal@thefend.com
FEND AI, Inc.
131 Continental Dr Suite 305
Newark, DE 19713, USA

This DPA is automatically accepted by EU-based business customers upon account creation and forms part of the Terms of Service agreement. Controllers may request a separately executed copy of this DPA by contacting legal@thefend.com.

© 2025 FEND AI, Inc. All rights reserved.
Document Version: 1.5 • Effective Date: June 24, 2025"""

        elif doc_type == 'product-listing-agreement':
            return """FEND AI, INC. PRODUCT LISTING AND COMMISSION AGREEMENT
Effective Date: June 24, 2025
Version: 1.0

1. AGREEMENT SCOPE AND INTEGRATION

This Product Listing and Commission Agreement ("Listing Agreement") governs the promotion and sale of User products and services through FEND's Deals page and is incorporated into the FEND AI Terms of Service. By participating in the Deals program, you agree to these additional terms.

2. DEALS PROGRAM OVERVIEW

FEND operates a Deals page that showcases products and services offered by Platform Users to promote business opportunities and facilitate sales within the FEND ecosystem. FEND earns commissions on successful sales generated through the Deals page.

2.1 Program Purpose
- Promote User products and services to the FEND community
- Generate additional revenue opportunities for Platform Users
- Create value-added marketplace beyond Pilot projects
- Build stronger business relationships within the FEND ecosystem

2.2 Eligible Participants
- All verified Startup and Enterprise Partner Users in good standing
- Users must have legal authority to sell listed products/services
- Products/services must be business-to-business offerings
- Compliance with Platform verification and documentation requirements

3. PRODUCT AND SERVICE LISTING REQUIREMENTS

3.1 Eligible Offerings
Acceptable Products and Services:
- Software products and licensing
- Professional services and consulting
- Hardware and physical products for business use
- Training and educational services
- Digital tools and platforms
- Business subscriptions and memberships

Prohibited Offerings:
- Consumer products not intended for business use
- Financial investment products or securities
- Products requiring special licensing without proper authorization
- Adult content or gambling-related services
- Products that compete directly with FEND Platform services

3.2 Listing Standards
- Accurate product descriptions and pricing information
- Professional product imagery and documentation
- Clear terms of sale and delivery information
- Compliance with applicable consumer protection laws
- Regular updates to maintain current and accurate listings

4. COMMISSION STRUCTURE AND PAYMENT TERMS

4.1 Commission Structure
- Startup Users: Commission rate as specified in individual listing agreement between User and FEND
- Enterprise Partner Users: Commission rate as specified in individual listing agreement between User and FEND
- Determined based on product type, sales volume projections, and strategic value to Platform
- Default minimum commission: $50 per transaction for Startups, $100 for Enterprise Partners

4.2 Commission Agreement Process
- Individual commission agreements required for each product/service listing
- Commission terms finalized prior to product listing approval
- Written agreement specifying exact commission rate, minimum thresholds, and payment terms
- Standard commission agreement template available through Platform interface

4.3 Payment Processing
- Commissions calculated on net sale amount (excluding taxes and shipping)
- Monthly commission payments processed within 30 days of month end
- Payment via ACH transfer to User's registered bank account
- Annual commission reporting for tax purposes

5. SALES PROCESS AND CUSTOMER MANAGEMENT

5.1 FEND's Role in Sales Process
- Lead Generation: Display User products/services on FEND Deals page
- Referral Links: Provide referral links and contact information to interested prospects
- Customer Screening: Basic product information and initial customer screening
- Attribution: Referral tracking and commission attribution

5.2 User Responsibilities for Customer Management
- Respond to FEND referrals within 48 hours
- Provide professional sales support and customer service
- Honor pricing and terms displayed on FEND Deals page
- Maintain customer satisfaction standards consistent with FEND community values
- Report sale completion and payment confirmation to FEND

6. INTELLECTUAL PROPERTY AND LICENSING

6.1 Product Ownership
- Users retain all ownership rights to their products and services
- Users grant FEND limited license to market and promote listed products
- FEND may use product information and imagery for marketing purposes
- Users responsible for ensuring they have rights to all listed content

6.2 FEND Platform Rights
- FEND retains ownership of Deals page design and functionality
- User-generated content subject to Platform Terms of Service
- FEND may remove listings that violate Platform policies
- Analytics and customer data generated through Platform remains FEND property

7. CUSTOMER DATA AND PRIVACY

7.1 Lead Information Sharing
- FEND provides basic contact information for qualified leads
- Users must comply with applicable privacy laws in handling customer data
- Customer relationship management remains User responsibility
- FEND Privacy Policy governs Platform data collection and use

7.2 Customer Privacy Protection
- Users must obtain appropriate consent for marketing communications
- Compliance with CAN-SPAM, GDPR, and other applicable privacy regulations
- Customer data may not be used for purposes outside of facilitated sale
- Data breach notification requirements apply to User handling of customer information

8. QUALITY ASSURANCE AND PERFORMANCE STANDARDS

8.1 Product Quality Requirements
- Products and services must meet professional business standards
- Accurate representation of capabilities and deliverables
- Timely delivery according to promised timelines
- Professional customer service and support

8.2 Performance Monitoring
- FEND monitors customer satisfaction and feedback for listed products
- Performance metrics tracked for referral quality and conversion rates
- Users with consistently poor performance may have listings suspended
- Regular performance reviews and improvement recommendations

9. MARKETING AND PROMOTION

9.1 FEND Marketing Support
- Featured placement opportunities for high-performing products
- Integration with Platform marketing and communication channels
- Cross-promotion opportunities with related Platform services
- Analytics and performance reporting for listed products

9.2 User Marketing Obligations
- Accurate and truthful marketing claims and representations
- Compliance with applicable advertising and marketing regulations
- Professional presentation consistent with FEND Platform standards
- Prompt response to customer inquiries and sales opportunities

10. TERM AND TERMINATION

10.1 Agreement Term
- This Agreement remains in effect for duration of Platform participation
- Individual product listings subject to separate termination provisions
- Either party may terminate with 30 days written notice
- Outstanding commission obligations survive Agreement termination

10.2 Termination Effects
- Immediate removal of product listings from Deals page
- Processing of pending commissions according to standard payment terms
- Return of any FEND marketing materials or confidential information
- Continuation of customer support obligations for existing sales

11. DISPUTE RESOLUTION

11.1 Sales Disputes
- Users responsible for resolving customer disputes related to their products
- FEND provides mediation support for Platform-related issues
- Commission disputes resolved through Platform dispute resolution procedures
- Customer refunds handled directly between User and customer

11.2 Platform Disputes
- Good faith negotiation required before formal dispute procedures
- Binding arbitration for unresolved disputes over commission terms
- Delaware law governs all Platform-related disputes
- Legal fees allocated according to arbitration decision

12. COMPLIANCE AND LEGAL REQUIREMENTS

12.1 Regulatory Compliance
- Users responsible for compliance with all applicable laws and regulations
- Product licensing and certification requirements User responsibility
- International sales compliance for cross-border transactions
- Tax obligations and reporting requirements

12.2 Platform Policy Compliance
- Adherence to Platform Terms of Service and community standards
- Regular review and updates to maintain policy compliance
- Cooperation with Platform investigations and compliance reviews
- Prompt implementation of required policy changes

13. MODIFICATION AND UPDATES

Changes to this Listing Agreement require 30 days advance notice to participating Users. Continued participation in Deals program after notice period constitutes acceptance of modified terms.

14. CONTACT INFORMATION

For Deals program questions, applications, or support:
Email: support@thefend.com
Phone: (650) 735-2255

Business Development:
Email: business@thefend.com

Legal and Compliance:
Email: legal@thefend.com
FEND AI, Inc.
131 Continental Dr Suite 305
Newark, DE 19713, USA

By submitting products/services for listing on the FEND Deals page or participating in the Deals program, you agree to this Product Listing and Commission Agreement and acknowledge your obligations under these terms.

© 2025 FEND AI, Inc. All rights reserved.
Document Version: 1.0 • Effective Date: June 24, 2025"""
        
        else:
            return f"Full legal document content not available for {doc_type}"
    
    document_templates = {
        'terms-of-service': {
            'filename': 'FEND_Terms_of_Service.txt',
            'title': 'Terms of Service'
        },
        'privacy-policy': {
            'filename': 'FEND_Privacy_Policy.txt',
            'title': 'Privacy Policy'
        },
        'user-agreement': {
            'filename': 'FEND_User_Agreement.txt', 
            'title': 'User Agreement'
        },
        'payment-terms': {
            'filename': 'FEND_Payment_Terms.txt',
            'title': 'Payment Terms'
        },
        'payment-holding-agreement': {
            'filename': 'FEND_Payment_Holding_Agreement.txt',
            'title': 'Payment Holding Service Agreement'
        },
        'data-processing-agreement': {
            'filename': 'FEND_Data_Processing_Agreement.txt',
            'title': 'Data Processing Agreement'
        },
        'product-listing-agreement': {
            'filename': 'FEND_Product_Listing_Agreement.txt',
            'title': 'Product Listing and Commission Agreement'
        }
    }
    
    if document_type not in document_templates:
        return HttpResponse('Document not found', status=404)
    
    doc_info = document_templates[document_type]
    
    # Get full document content
    content = get_full_document_content(document_type)
    
    response = HttpResponse(content, content_type='text/plain')
    response['Content-Disposition'] = f'attachment; filename="{doc_info["filename"]}"'
    return response