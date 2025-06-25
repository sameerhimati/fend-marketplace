"""
Core services for shared business logic across apps.
This helps reduce circular dependencies and duplicate code.
"""

from django.contrib import messages
from django.utils import timezone


class NotificationService:
    """Centralized notification management to reduce duplicate patterns."""
    
    @staticmethod
    def create_payment_notification(payment, notification_type, title, message):
        """Create payment-related notifications with standard format."""
        from apps.notifications.services import create_notification
        
        # Notify enterprise users
        for user in payment.pilot_bid.pilot.organization.users.all():
            create_notification(
                recipient=user,
                notification_type=notification_type,
                title=title,
                message=message,
                related_pilot=payment.pilot_bid.pilot,
                related_bid=payment.pilot_bid
            )
    
    @staticmethod
    def create_bid_status_notification(bid, notification_type, title, message):
        """Create bid status change notifications."""
        from apps.notifications.services import create_bid_notification
        
        create_bid_notification(
            bid=bid,
            notification_type=notification_type,
            title=title,
            message=message
        )
    
    @staticmethod
    def create_admin_notification(title, message, related_pilot=None, related_bid=None):
        """Create admin notifications with consistent format."""
        from apps.notifications.services import create_admin_notification
        
        create_admin_notification(
            title=title,
            message=message,
            related_pilot=related_pilot,
            related_bid=related_bid
        )


class PermissionService:
    """Centralized permission checking to reduce duplicate code."""
    
    @staticmethod
    def can_user_edit_pilot(user, pilot):
        """Check if user can edit a specific pilot."""
        if user.is_superuser:
            return True
        
        user_org = getattr(user, 'organization', None)
        if not user_org:
            return False
            
        return user_org.type == 'enterprise' and pilot.organization == user_org
    
    @staticmethod
    def can_user_view_pilot(user, pilot):
        """Check if user can view a specific pilot."""
        if user.is_superuser:
            return True
            
        user_org = getattr(user, 'organization', None)
        if not user_org:
            return False
            
        if user_org.type == 'enterprise':
            return pilot.organization == user_org
        elif user_org.type == 'startup':
            return not pilot.is_private and pilot.status == 'published'
        
        return False
    
    @staticmethod
    def require_active_subscription(user):
        """Check if user has active subscription and return appropriate message."""
        user_org = getattr(user, 'organization', None)
        if not user_org:
            return False, "You need to be associated with an organization"
            
        if not user_org.has_active_subscription():
            return False, "Your organization needs an active subscription to access this feature"
            
        return True, None


class StatusValidationService:
    """Centralized status validation logic."""
    
    @staticmethod
    def validate_pilot_status_transition(pilot, new_status):
        """Validate if pilot status transition is allowed."""
        valid_transitions = {
            'draft': ['published'],
            'published': ['in_progress', 'cancelled'],
            'in_progress': ['completed', 'cancelled'],
            'completed': [],
            'cancelled': []
        }
        
        current_status = pilot.status
        allowed_statuses = valid_transitions.get(current_status, [])
        
        return new_status in allowed_statuses
    
    @staticmethod
    def validate_bid_status_transition(bid, new_status):
        """Validate if bid status transition is allowed."""
        valid_transitions = {
            'pending': ['under_review', 'approved', 'declined'],
            'under_review': ['approved', 'declined'],
            'approved': ['live'],
            'live': ['completion_pending'],
            'completion_pending': ['completed'],
            'completed': [],
            'declined': []
        }
        
        current_status = bid.status
        allowed_statuses = valid_transitions.get(current_status, [])
        
        return new_status in allowed_statuses


class LegalDocumentService:
    """Service for managing legal document display and acceptance."""
    
    DOCUMENT_CONFIGS = {
        'terms-of-service': {
            'title': 'Terms of Service',
            'effective_date': 'June 24, 2025',
            'version': '1.40',
            'summary_title': 'Terms of Service - Key Points',
            'summary_color': 'blue',
            'description': 'Legal terms governing your use of the FEND AI Platform'
        },
        'privacy-policy': {
            'title': 'Privacy Policy',
            'effective_date': 'June 24, 2025',
            'version': '1.7',
            'summary_title': 'Privacy Policy - Key Points',
            'summary_color': 'green',
            'description': 'How we collect, use, and protect your business information'
        },
        'user-agreement': {
            'title': 'User Agreement',
            'effective_date': 'June 24, 2025',
            'version': '1.20',
            'summary_title': 'User Agreement - Key Points',
            'summary_color': 'purple',
            'description': 'Category-specific requirements for Startup and Enterprise users'
        },
        'payment-terms': {
            'title': 'Payment Terms',
            'effective_date': 'June 24, 2025',
            'version': '1.12',
            'summary_title': 'Payment Terms - Key Points',
            'summary_color': 'yellow',
            'description': 'Payment structure, fees, and billing terms for Platform services'
        },
        'payment-holding-agreement': {
            'title': 'Payment Holding Service Agreement',
            'effective_date': 'June 24, 2025',
            'version': '2.0',
            'summary_title': 'Payment Holding Service - Key Points',
            'summary_color': 'orange',
            'description': 'Terms governing secure payment holding for Pilot projects'
        },
        'data-processing-agreement': {
            'title': 'Data Processing Agreement',
            'effective_date': 'June 24, 2025',
            'version': '1.5',
            'summary_title': 'GDPR Data Processing - Key Points',
            'summary_color': 'indigo',
            'description': 'GDPR compliance and data protection for EU-based customers'
        },
        'product-listing-agreement': {
            'title': 'Product Listing and Commission Agreement',
            'effective_date': 'June 24, 2025',
            'version': '1.0',
            'summary_title': 'Product Listing - Key Points',
            'summary_color': 'teal',
            'description': 'Terms for promoting and selling products through FEND Deals page'
        },
    }
    
    @classmethod
    def get_document_context(cls, document_slug, show_acceptance=False):
        """Get standardized context for legal document display."""
        config = cls.DOCUMENT_CONFIGS.get(document_slug, {})
        
        return {
            'show_acceptance': show_acceptance,
            'document_title': config.get('title', 'Legal Document'),
            'document_slug': document_slug,
            'effective_date': config.get('effective_date', 'Unknown'),
            'version': config.get('version', '1.0'),
            'summary_title': config.get('summary_title', 'Key Points'),
            'summary_color': config.get('summary_color', 'blue'),
            'description': config.get('description', 'Legal document')
        }
    
    @classmethod
    def get_all_documents(cls):
        """Get list of all available legal documents for portal homepage."""
        return [
            {
                'slug': slug,
                'title': config['title'],
                'description': config['description'],
                'effective_date': config['effective_date'],
                'version': config['version'],
                'color': config['summary_color']
            }
            for slug, config in cls.DOCUMENT_CONFIGS.items()
        ]
    
    @classmethod
    def format_legal_content(cls, content):
        """Format legal document content with proper HTML headings."""
        import re
        
        # Convert content to HTML with proper formatting
        lines = content.split('\n')
        formatted_lines = []
        in_list = False
        
        for line in lines:
            line = line.strip()
            if not line:
                if in_list:
                    formatted_lines.append('</ul>')
                    in_list = False
                continue
                
            # Main document title (all caps, starts with company name)
            if line.startswith('FEND AI, INC.') and line.isupper():
                if in_list:
                    formatted_lines.append('</ul>')
                    in_list = False
                formatted_lines.append(f'<h1 class="text-2xl font-bold text-gray-900 mb-4">{line}</h1>')
            
            # Version and date info
            elif line.startswith('Effective Date:') or line.startswith('Version:'):
                if in_list:
                    formatted_lines.append('</ul>')
                    in_list = False
                formatted_lines.append(f'<p class="text-sm text-gray-600 mb-6">{line}</p>')
            
            # Major section headings (numbers like "1. SECTION NAME", "15. CONTACT INFORMATION")
            elif re.match(r'^\d+\.\s+[A-Z][A-Z\s&,()-]+$', line):
                if in_list:
                    formatted_lines.append('</ul>')
                    in_list = False
                formatted_lines.append(f'<h2 class="text-xl font-semibold text-gray-800 mt-8 mb-4">{line}</h2>')
            
            # Subsection headings (like "1.1 Subsection Name", "12.3 Insurance and Liability")
            elif re.match(r'^\d+\.\d+\s+[A-Za-z]', line):
                if in_list:
                    formatted_lines.append('</ul>')
                    in_list = False
                formatted_lines.append(f'<h3 class="text-lg font-medium text-gray-700 mt-6 mb-3">{line}</h3>')
            
            # Sub-subsection headings (like "Step 1: Mandatory Mediation", "Access Controls:")
            elif re.match(r'^(Step \d+:|[A-Za-z][A-Za-z\s]+:)$', line):
                if in_list:
                    formatted_lines.append('</ul>')
                    in_list = False
                formatted_lines.append(f'<h4 class="text-base font-medium text-gray-600 mt-4 mb-2">{line}</h4>')
            
            # Bullet points (lines starting with -)
            elif line.startswith('- '):
                if not in_list:
                    formatted_lines.append('<ul class="list-disc ml-6 mb-4">')
                    in_list = True
                formatted_lines.append(f'<li class="mb-2">{line[2:]}</li>')
            
            # Regular paragraph
            else:
                if in_list:
                    formatted_lines.append('</ul>')
                    in_list = False
                formatted_lines.append(f'<p class="mb-4">{line}</p>')
        
        # Close any remaining list
        if in_list:
            formatted_lines.append('</ul>')
        
        return '\n'.join(formatted_lines)

    @classmethod
    def get_full_document_content(cls, document_type):
        """Get full legal document content for web display."""
        
        if document_type == 'terms-of-service':
            return """FEND AI, INC. TERMS OF SERVICE
Effective Date: June 24, 2025
Version: 1.40

1. ACCEPTANCE OF TERMS

By accessing, browsing, or using the FEND AI platform (the "Platform"), you acknowledge that you have read, understood, and agree to be bound by these Terms of Service ("Terms") and our Privacy Policy, which is incorporated herein by reference. If you do not agree to these Terms, you may not access or use the Platform.

These Terms constitute a legally binding agreement between you ("User," "you," or "your") and FEND AI, Inc., a Delaware corporation ("FEND," "we," "us," or "our").

2. DESCRIPTION OF SERVICE

FEND operates a B2B marketplace platform that connects companies to create and complete pilot projects ("Pilots") and promotes User products and services through marketplace channels. The Platform facilitates a comprehensive business ecosystem where Users can engage in multiple revenue-generating activities. The Platform provides:

Pilot Creation: Tools for creating detailed Pilot specifications with clear "Definition of Done" criteria
Pilot Discovery: Marketplace for browsing and bidding on available Pilots
Product and Service Promotion: Deals page featuring User offerings with commission-based sales
Secure Transactions: Payment Holding services, payment processing, and milestone management
Quality Assurance: Completion scoring and performance analytics
Project Management: Communication tools and progress tracking

3. USER CATEGORIES AND ELIGIBILITY

3.1 User Categories
Users are categorized based on company size for pricing and feature access:
Startups: Companies with fewer than 500 employees
Enterprise Partners: Companies with 500 or more employees

3.2 Eligibility Requirements
To use the Platform, you must:
Be at least 18 years old or the age of majority in your jurisdiction
Have the legal authority to enter into binding agreements on behalf of your company
Represent a legitimate business entity
Provide accurate employee count information for proper categorization
Not be prohibited from using the Platform under applicable laws

3.3 Account Registration and Verification
You must provide accurate, complete, and current company information during registration, including EIN and other required legal company details
All applicants undergo FEND's verification process to confirm company size, legitimacy, and proper categorization
You are responsible for maintaining the confidentiality of your account credentials
You must notify FEND if your company size changes categories
You may not transfer, sell, or assign your account to another party

4. SUBSCRIPTION FEES AND BILLING

4.1 Annual Subscription Fees
Startup Plans: Pricing based on selected plan tier as displayed during account registration
Enterprise Partner Plans: Pricing based on selected plan tier as displayed during account registration
Different plan tiers provide access to varying Platform features and capabilities
All subscription fees are billed annually at account creation and renewal
Current pricing for all plans is available on the Platform and may be updated by FEND with appropriate notice

4.2 Auto-Renewal
Subscriptions automatically renew for additional one-year terms
Users must provide 90 days' written notice prior to renewal date to cancel auto-renewal
Renewal fees are charged to the payment method on file
No refunds for unused portions of subscription periods except as required by law

4.3 Plan Changes and Upgrades
Users may upgrade their plan tier at any time, with pricing adjustments applied immediately
If your company grows from Startup to Enterprise Partner category, you will be required to select an appropriate Enterprise Partner plan at your next renewal
Plan downgrades are subject to FEND approval and feature access limitations
Pricing for plan changes is calculated on a pro-rated basis

5. PILOT PROJECTS FRAMEWORK

5.1 Pilot Creation and Approval Process
Any User may create Pilots with detailed project specifications and upload a Definition of Done document
Definition of Done: A document specifying minimum success metrics including product specifications, features, user metrics, revenue targets, or other business criteria required for Pilot completion
Created Pilots must be reviewed and approved by FEND before becoming Active Pilots
Active Pilots: FEND-approved Pilots that are live on the marketplace and may be designated as:
Public: Visible to all qualified Users on the Platform
Private: Visible only to pre-selected Users
Payment for Pilots must be made upfront and held by FEND's payment holding service before Pilots become active

5.2 Pilot Completion Process
Any User may bid on Active Pilots based on Creator criteria and be selected as the Pilot Completer
Selected Pilot Completers are contractually bound to deliver according to the Definition of Done document
Pilot Completers must maintain strict confidentiality of all information shared during the project
Completion Approval: Pilot Creators have final authority to determine completion by clicking "Pilot Completed" after reviewing deliverables against the Definition of Done
If a Creator does not approve completion within 60 days of deliverable submission, the matter automatically enters FEND's dispute resolution process

5.3 Pilot Modifications and Cancellations
Active Pilots with Assigned Completers cannot be cancelled or modified
Active Pilots without Assigned Completers may be:
Modified with FEND approval and clear communication to all bidders
Cancelled subject to 1.5% cancellation fee paid by the Pilot Creator
Unsuccessful Pilots: If no Completer successfully delivers according to the Definition of Done, Pilot Creators receive a full refund with no fees retained by FEND

6. PAYMENT TERMS AND SUCCESS FEES

6.1 Payment Holding Services
All Pilot payments are held by FEND's payment holding service from the time of Pilot funding until completion
Payments may be structured as:
Lump Sum: Released upon successful completion
Milestone-Based: Released according to pre-agreed schedule and deliverables
Disputed payments are subject to FEND's completion assessment and dispute resolution process

6.2 Platform Fees and Payment Structure
Creator Platform Fee: FEND charges a 5% platform fee to Pilot Creators, calculated as 5% of the stated Pilot value and paid in addition to the Pilot value
Payment Holding Funding: Pilot Creators fund payment holding account with 105% of the Pilot value (100% Pilot value + 5% Creator platform fee)
Completer Platform Fee: FEND charges a 5% platform fee to Pilot Completers, calculated as 5% of the stated Pilot value and deducted from their payment
Net Payment Calculation: Upon successful completion and Creator approval, Pilot Completers receive 95% of the original stated Pilot value
Example: For a $100,000 Pilot, Creator pays $105,000 to Payment Holding Services, Completer receives $95,000, FEND retains $10,000
Platform fees apply to all payment structures including lump sum and milestone-based payments

6.3 Payment Release and Milestone Structure
Lump Sum Payments: Released upon Creator approval of final deliverables
Milestone-Based Payments: Released according to pre-agreed schedule, which may include:
Monthly payments totaling the full Pilot value over the project duration
Version-based payments upon delivery of specified iterations or features
Creator Approval Required: All payments require explicit Creator approval through the "Pilot Completed" confirmation
Dispute Protection: Payments held in payment holding account pending resolution if completion is disputed beyond 60-day approval window

6.4 Additional Fees
Pilot Cancellation Fee: 1.5% of Pilot value (paid by cancelling Pilot Creator)
Payment Processing: Standard payment processing fees apply to all transactions
Dispute Resolution: Additional fees may apply for formal dispute resolution services

7. PLATFORM USAGE RULES

7.1 Permitted Uses
You may use the Platform to:
Create legitimate business Pilots with clear commercial purpose
Browse, bid on, and complete Pilots within your expertise
List and promote products and services through FEND's Deals program
Communicate with other Users through Platform messaging systems
Access reporting, analytics, and performance tracking tools
Build professional reputation through successful Pilot completion and product sales

7.2 Prohibited Uses
You may not:
Use the Platform for any unlawful purpose or in violation of applicable laws
Circumvent the Platform to conduct direct transactions with other Users
Post false, misleading, or fraudulent Pilot information
Bid on Pilots without genuine ability or intent to complete them
Share confidential information from Pilots outside the Platform
Harass, threaten, or discriminate against other Users
Attempt to gain unauthorized access to the Platform or other Users' accounts
Use automated systems (bots, scrapers) without FEND's written consent
Manipulate completion scores or provide false performance data

8. INTELLECTUAL PROPERTY RIGHTS AND WARRANTIES

8.1 Platform Intellectual Property
FEND retains all rights to the Platform, including software, algorithms, trademarks, and proprietary content
Users receive a limited, non-exclusive, non-transferable license to use the Platform during their active subscription

8.2 User Content and IP Warranties
Users retain ownership of content they create and upload to the Platform
User IP Warranty: Users represent and warrant that they:
Own or have sufficient rights to all content, materials, and information they provide
Have authority to grant licenses for any third-party content included in their submissions
Will not infringe upon any third-party intellectual property rights through their Platform use
Users grant FEND a worldwide, royalty-free, non-exclusive license to use, display, reproduce, and distribute User content for Platform operations, marketing, and improvement

8.3 Pilot Work Product and IP Rights
Default IP Assignment: Unless otherwise specified in individual Pilot agreements, all intellectual property rights in completed Pilot work product automatically assign to the Pilot Creator upon final payment release
Work-for-Hire: All Pilot work product constitutes "work made for hire" under applicable copyright law, with Creator as the commissioning party
Comprehensive IP Transfer: Assignment includes all copyrights, patents, trade secrets, trademarks, and other intellectual property rights in deliverables
Custom IP Arrangements: Pilot Creators and Completers may negotiate alternative IP arrangements within their specific Pilot terms, which must be documented in writing before Pilot commencement
Completer IP Warranty: Pilot Completers warrant that all work product delivered is:
Original work created specifically for the Pilot or properly licensed for transfer
Free from third-party intellectual property claims and encumbrances
Delivered with clear title and full rights to assign to Pilot Creator
Created without incorporation of Completer's pre-existing proprietary technology unless explicitly agreed
Creator IP Warranty: Pilot Creators warrant that all materials, specifications, and information provided to Completers are:
Owned by Creator or used with proper authorization from rights holders
Free from third-party claims that would prevent Completer's use in fulfilling the Pilot
Provided with sufficient rights to enable Completer performance without IP infringement

8.4 Platform Independence and FEND IP Disclaimer
No FEND Claims: FEND makes no claims to work product or intellectual property created through Pilot projects
FEND IP Warranty: FEND warrants that its Platform technology does not infringe third-party intellectual property rights
Mutual Indemnification: Users agree to indemnify FEND against IP claims arising from User content, and FEND agrees to indemnify Users against claims arising from Platform technology

9. CONFIDENTIALITY AND DATA PROTECTION

9.1 Confidentiality Obligations
All Users must maintain strict confidentiality regarding:
Non-public business information shared through Pilots
Proprietary technical requirements and specifications
Strategic information disclosed during Pilot execution
Financial information and business performance data
Any information marked as confidential by the disclosing party
Confidentiality Period: Confidentiality obligations remain in effect for 5 years following completion or termination of individual Pilots
Information Handling: Confidential information may only be used for authorized Platform activities and must be protected with same care as recipient's own confidential information
Return/Destruction: Upon Pilot completion or termination, receiving party must return or destroy all confidential materials and certify such destruction in writing
Permitted Disclosures: Confidential information may be disclosed only: (a) with prior written consent, (b) as required by law with advance notice to disclosing party, or (c) if independently developed without use of confidential information
Injunctive Relief: Breach of confidentiality may cause irreparable harm for which monetary damages are inadequate, therefore disclosing party shall be entitled to injunctive relief without posting bond

9.2 Data Protection and Privacy Compliance
FEND maintains GDPR, CCPA, and HIPAA-compliant infrastructure and practices
User Compliance Obligations: Users are responsible for maintaining compliance with applicable data protection laws in their own operations and Pilot work
HIPAA Compliance: Users handling healthcare-related Pilots must ensure their own HIPAA compliance and may be required to provide compliance certifications
Healthcare Data Restriction: Users must not share personal health information (PHI) through the Platform unless specifically authorized and compliant with HIPAA requirements
Cross-border data transfers comply with applicable international data protection frameworks
Our Privacy Policy details our comprehensive data handling practices

9.3 Security Measures
FEND implements industry-standard security measures to protect User data
Users are responsible for maintaining secure access to their accounts
Suspected security breaches must be reported to FEND immediately

10. QUALITY ASSURANCE AND PERFORMANCE

10.1 Completion Standards and Rating System
All Pilots must be completed according to the Definition of Done specified by the Pilot Creator
Upon completion, both Pilot Creators and Completers may provide 5-star ratings and feedback
Rating System: Users rate their experience on a 1-5 star scale with optional written feedback
FEND maintains performance statistics including completion rates, timeline adherence, and user satisfaction ratings
Performance data may be used for Platform improvement and User matching algorithms

10.2 Performance Metrics and User Reputation
FEND tracks and displays User performance metrics including:
Average star ratings received from other Users
Number of successful Pilot completions
Timeline adherence and communication quality
Professional reputation scores based on User feedback
Poor performance ratings may result in account restrictions or additional verification requirements

10.3 Quality Disputes and Resolution
Quality disputes should first be addressed directly between Pilot Creator and Completer through Platform messaging
If Creator does not approve completion within 60 days of deliverable submission, FEND will review the deliverables against the Definition of Done
FEND may provide mediation services and make final determinations on completion disputes
Disputed payments remain in payment holding account pending resolution through FEND's dispute resolution process

11. DISPUTE RESOLUTION

11.1 Internal Resolution Process
Users are encouraged to resolve disputes directly through Platform communication tools
FEND provides mediation services for performance and payment disputes
Platform messaging and project documentation serve as evidence for dispute resolution

11.2 Formal Dispute Resolution
For disputes that cannot be resolved through internal processes:
Step 1: Mandatory Mediation
All disputes must first be submitted to binding mediation
Mediation shall be conducted by a mutually agreed professional mediator
If parties cannot agree on a mediator, FEND will select a qualified neutral mediator
Mediation costs are shared equally between disputing parties
Step 2: Binding Arbitration
If mediation fails to resolve the dispute within 60 days, the matter proceeds to binding arbitration
Arbitration conducted under the Commercial Arbitration Rules of the American Arbitration Association
Arbitration shall take place in Delaware, USA, with proceedings conducted in English
The arbitrator's decision is final and binding on all parties

11.3 Limitations and Exceptions
Class Action Waiver: Users waive the right to participate in class action lawsuits or collective arbitrations
Small Claims Court: Disputes under $10,000 may be brought in small claims court
Injunctive Relief: FEND may seek injunctive relief in court for violations of confidentiality or intellectual property rights

12. LIMITATION OF LIABILITY AND WARRANTIES

12.1 Platform Availability and Performance
Platform Uptime: FEND commits to 99.5% Platform uptime availability, measured monthly excluding scheduled maintenance
Scheduled Maintenance: Maximum 4 hours monthly scheduled maintenance, with 48-hour advance notice to users
Support Response Times:
Critical issues (Platform unavailable): 2-hour response during business hours
High priority issues (payment processing): 4-hour response during business hours
Standard issues (general support): 24-hour response during business hours
Business Hours: Monday-Friday, 9 AM - 6 PM Eastern Time, excluding US federal holidays
Service Level Credits: If monthly uptime falls below 99.5%, affected users receive service credits:
99.0% - 99.49% uptime: 5% monthly subscription credit
98.0% - 98.99% uptime: 10% monthly subscription credit
Below 98.0% uptime: 25% monthly subscription credit
Credit Limitations: Service credits are sole remedy for SLA breaches and cannot exceed 50% of monthly subscription fees

12.2 Limitation of Damages
Liability Cap: FEND's total liability to any User shall not exceed the amount of fees paid by that User in the 12 months preceding the claim
Excluded Damages: FEND is not liable for indirect, incidental, consequential, punitive, or special damages
Data Loss: Users are responsible for backup and protection of their own data and content

12.3 Third-Party Interactions and Pilot Quality
FEND acts as a marketplace facilitator and is not responsible for:
The quality, accuracy, or completeness of Pilot work
Disputes between Pilot Creators and Completers
The conduct, qualifications, or representations of Platform Users
Legal compliance of individual Pilot projects
Users interact with each other at their own risk and discretion

13. INDEMNIFICATION

Users agree to indemnify, defend, and hold harmless FEND, its officers, directors, employees, agents, and affiliates from and against any and all claims, damages, losses, costs, and expenses (including reasonable attorneys' fees) arising from or relating to:
User's violation of these Terms or applicable laws
User's use of the Platform or participation in Pilot projects
User's interactions with other Platform Users
Content or information provided by User to the Platform
User's breach of confidentiality or intellectual property rights
Any negligent or wrongful conduct by User

14. ACCOUNT TERMINATION

14.1 Termination by User
Users may terminate their accounts at any time by providing 90 days' written notice
Termination does not relieve Users of obligations for active Pilots or outstanding fees
No refunds will be provided for unused subscription periods
Users may download their data within 30 days of termination

14.2 Termination by FEND
FEND may suspend or terminate User accounts immediately, with or without notice, for:
Material violation of these Terms
Fraudulent, deceptive, or illegal activity
Non-payment of fees or chargebacks
Breach of confidentiality obligations
Repeated poor performance or User complaints
Inactivity for more than 12 consecutive months

14.3 Effect of Termination
Upon termination, User's access to the Platform ceases immediately
Active Pilots may continue under existing terms until completion
Financial obligations and confidentiality commitments survive termination
FEND may retain User data as required by law or for legitimate business purposes

15. UPDATES TO TERMS OF SERVICE

15.1 Modification Rights and Process
FEND reserves the right to modify these Terms at any time to reflect changes in:
Platform features and functionality
Legal and regulatory requirements
Business model evolution
User feedback and market conditions

15.2 Notification of Changes
Material Changes: Users will receive 30 days' advance notice via email and Platform notifications
Minor Changes: Users will be notified through Platform announcements
Emergency Changes: Immediate changes may be made for legal compliance or security reasons

15.3 Version Control and Acceptance
All Terms versions are maintained with clear effective dates and version numbers
Previous versions are archived and available upon request
Continued use of the Platform after the effective date constitutes acceptance of updated Terms
Users who do not accept material changes may terminate their accounts without penalty

16. GENERAL PROVISIONS

16.1 Governing Law and Jurisdiction
United States Users: These Terms are governed by and construed in accordance with the laws of the State of Delaware, without regard to its conflict of law principles. Any legal actions not subject to arbitration shall be brought in the state or federal courts located in Delaware.
European Union Users: For EU users, these Terms are governed by Delaware law except where EU consumer protection laws provide greater rights, in which case EU law shall apply to those specific provisions. EU users may bring legal actions in their country of residence where permitted by EU law.
Cross-Border Compliance: All international transactions comply with applicable export control laws, sanctions regulations, and anti-money laundering requirements of both the United States and user's country of residence.

16.2 Severability and Enforcement
If any provision of these Terms is found to be unenforceable or invalid by a court of competent jurisdiction, the remaining provisions shall remain in full force and effect. FEND's failure to enforce any provision does not constitute a waiver of that provision.

16.3 Entire Agreement and Amendments
These Terms, together with the Privacy Policy, User Agreement, Payment Holding Service Agreement, Payment Terms, Product Listing and Commission Agreement, and any additional posted policies, constitute the entire agreement between Users and FEND. These Terms may only be amended through the process described in Section 15.

16.4 Assignment and Transfer
Users may not assign or transfer their rights or obligations under these Terms without FEND's prior written consent. FEND may assign these Terms in connection with a merger, acquisition, or sale of assets.

16.6 Force Majeure
Excused Performance: Neither FEND nor Users shall be liable for delays or failures in performance resulting from events beyond their reasonable control, including but not limited to natural disasters, pandemics, government actions, war, terrorism, labor disputes, cyber attacks, or infrastructure failures ("Force Majeure Events").
Notification Requirements: The affected party must promptly notify the other party in writing of any Force Majeure Event, including expected duration and mitigation efforts.
Mitigation Obligations: All parties must use commercially reasonable efforts to minimize the impact of Force Majeure Events and resume normal performance as soon as reasonably possible.
Payment Implications: Active Pilots affected by Force Majeure Events shall have extended deadlines proportional to the delay period. Payment holding periods may be extended accordingly with mutual agreement.
Termination Rights: If a Force Majeure Event continues for more than 90 days, either party may terminate affected Pilots with full refund of payment holding funds to Creator.

17. CONTACT INFORMATION

For questions, concerns, or notices regarding these Terms of Service, please contact us at:

FEND AI, Inc.
Email: legal@thefend.com
Address: 131 Continental Dr Suite 305, Newark, DE 19713, USA
Phone: (650) 735-2255

For general Platform support: support@thefend.com
For business inquiries: business@thefend.com

© 2025 FEND AI, Inc. All rights reserved.
Document Version: 1.40 • Effective Date: June 24, 2025"""

        elif document_type == 'user-agreement':
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
Provide accurate employee count and company documentation including EIN
Notify FEND when company reaches 500+ employees
Automatic upgrade to Enterprise Partner pricing at next renewal when exceeding 500 employees
Access to standard Platform features and Service Level Agreement commitments
Eligible for payment holding services with standard processing timeframes
May participate in Product Listing and Commission program subject to separate agreement

3.2 Enterprise Partner User Requirements
Provide corporate documentation including EIN and certificate of incorporation
Ensure authorized personnel conduct all Platform activities
Maintain corporate compliance standards for all Platform use
Receive enhanced Service Level Agreement commitments and priority support
Access to enterprise-grade payment holding services with expedited processing
Enhanced GDPR compliance support for EU-based Enterprise Partners
Priority access to Product Listing and Commission program features

4. PAYMENT HOLDING SERVICE INTEGRATION

4.1 Category-Specific Payment Requirements
Startup Users: Standard payment holding account funding requirements apply (105% of Pilot value)
Enterprise Partners: Access to enhanced payment holding features including expedited processing and higher transaction limits
Payment Methods: All categories may use ACH, wire transfers, and approved corporate payment methods per Payment Terms
International Users: Enhanced payment holding support for cross-border transactions

4.2 Service Level Commitments by Category
Startup Users: Standard SLA commitments per Terms of Service (99.5% uptime, 24-hour standard support response)
Enterprise Partners: Enhanced SLA commitments including 2-hour critical response time and priority payment processing
Payment Processing: Category-specific processing timeframes outlined in Payment Holding Service Agreement
Dispute Resolution: Enhanced dispute resolution procedures for Enterprise Partners

All users undergo FEND verification during registration
FEND may request additional documentation to verify category classification
False category classification may result in account termination and fee adjustments

5. BILLING AND CATEGORY CHANGES

Plan pricing displayed during registration based on selected category
Category upgrades take effect at next renewal cycle
Category downgrades require FEND approval and verification
No refunds for category-related pricing changes

6. ADDITIONAL PLATFORM SERVICES

6.1 Product Listing and Commission Program
Both Startup and Enterprise Partner users may participate in FEND's Product Listing and Commission program
Separate Product Listing and Commission Agreement required for participation
Enterprise Partners receive priority consideration for featured product listings
Enhanced commission negotiation available for Enterprise Partners

6.2 International Compliance Support
EU Users: Automatic Data Processing Agreement acceptance for GDPR compliance
Enhanced GDPR Support: Enterprise Partners receive dedicated privacy compliance assistance
Cross-Border Transactions: Category-appropriate support for international Pilot projects
Local Compliance: Assistance with local regulatory requirements based on company size and jurisdiction

Users handling healthcare-related Pilots must maintain HIPAA compliance
Compliance verification conducted case-by-case as needed
Users responsible for meeting industry-specific regulatory requirements

7. CONTACT AND SUPPORT

7.1 Category-Specific Support
Startup Users: Standard support channels during business hours
Enterprise Partners: Priority support with enhanced SLA response times and dedicated account management for high-volume users

7.2 Contact Information
For all support requests, contact:
Email: support@thefend.com
Phone: (650) 735-2255

For legal matters:
Email: legal@thefend.com
FEND AI, Inc.
131 Continental Dr Suite 305
Newark, DE 19713, USA

© 2025 FEND AI, Inc. All rights reserved.
Document Version: 1.20 • Effective Date: June 24, 2025"""

        elif document_type == 'payment-holding-agreement':
            return """FEND AI, INC. PAYMENT HOLDING SERVICE AGREEMENT
Effective Date: June 24, 2025
Version: 2.0

1. AGREEMENT SCOPE AND INTEGRATION

This Payment Holding Service Agreement ("Holding Agreement") governs FEND AI's payment holding services for Pilot project payments and is incorporated into the FEND AI Terms of Service. By creating Pilots or accepting Pilot work, you agree to these payment holding terms.

2. PAYMENT HOLDING SERVICE OVERVIEW

FEND AI acts as payment holding service provider for all Pilot payments, securely holding funds from Pilot Creators and releasing them to Pilot Completers upon successful project completion according to the Definition of Done.

3. PAYMENT FUNDING REQUIREMENTS

3.1 Creator Funding Obligation
Pilot Creators must fund payment holding account with 105% of stated Pilot value before Pilot goes live
Payment includes: 100% Pilot value + 5% Creator platform fee
Payment must be received via ACH transfer or other approved payment method
Pilots remain inactive until full payment funding is confirmed

3.2 Accepted Payment Methods
ACH bank transfers (preferred method)
Corporate checks (subject to clearing periods)
Wire transfers (for international transactions)
Other payment methods as approved by FEND

3.3 Payment Processing Timeframes
ACH transfers: 2-3 business days to clear
Corporate checks: 5-7 business days to clear
Wire transfers: 1-2 business days to clear
Pilots go live only after funds are fully cleared and available

4. PAYMENT RELEASE CONDITIONS

4.1 Completion Approval Process
Pilot Completer submits deliverables according to Definition of Done
Pilot Creator has 60 days to review and approve completion
Creator clicks "Pilot Completed" button to authorize payment release
Automatic dispute escalation if no approval within 60 days

4.2 Payment Release Calculation
Pilot Completer receives 95% of stated Pilot value
FEND retains 5% as Completer platform fee
Example: $100,000 Pilot = $95,000 to Completer, $5,000 to FEND
Creator's 5% platform fee was collected during payment funding

4.3 Milestone Payment Release
Available for Pilots structured with milestone-based payments
Each milestone requires separate Creator approval for payment release
Milestone payments follow same 95% payout structure
Remaining milestones held in payment account until individual approval

5. FUND SECURITY AND PROTECTION

5.1 Fund Security Measures
All held funds maintained in FDIC-insured business accounts
Segregated accounting maintains clear separation of held funds from FEND operating funds
Regular reconciliation and audit procedures for all payment holding accounts
Held funds invested only in FDIC-insured, highly liquid instruments

5.2 Dispute Protection
Disputed funds remain in holding account until resolution through FEND's dispute process
Neither party may claim disputed funds without proper resolution
FEND may require additional documentation before releasing disputed payments
Legal process required for any third-party claims against held funds

6. FAILED OR CANCELLED PILOTS

6.1 Pilot Cancellation Refunds
Full refund to Creator if no Completer successfully delivers according to Definition of Done
No fees retained by FEND for unsuccessful Pilots
Refund processing within 5-7 business days of determination
Creator cancellation of active Pilots subject to 1.5% cancellation fee

6.2 Partial Completion Scenarios
Milestone-based Pilots: Completed milestones paid out, remaining funds refunded
Abandoned projects: Full refund to Creator after 60-day non-response period
Disputed partial completion: Funds held pending dispute resolution

7. PAYMENT HOLDING SERVICE DUTIES AND LIMITATIONS

7.1 FEND's Role as Payment Holding Service Provider
Hold and safeguard payment funds according to this Agreement
Release funds only upon proper completion approval or dispute resolution
Maintain accurate records of all payment holding transactions
Provide periodic account statements upon request

7.2 Limitations of Payment Holding Service
FEND does not guarantee work quality or Creator satisfaction
FEND does not mediate disputes unless specifically requested
FEND is not responsible for delays in completion approval
Payment holding service limited to payment custody and release functions

7.3 Prohibited Actions
FEND will not release funds without proper authorization
No fund releases to unauthorized third parties
No commingling of held funds with FEND operating funds
No investment of held funds in non-FDIC insured instruments

8. DISPUTE RESOLUTION AND PAYMENT HOLDING

8.1 Dispute Payment Procedures
Disputed funds frozen in holding account until resolution
Both parties notified of dispute status and fund freeze
Dispute resolution follows Terms of Service procedures
Fund release only upon written dispute resolution agreement

8.2 Resolution Authority
Mutual agreement between Creator and Completer controls fund release
FEND dispute resolution determination binding if parties cannot agree
Court orders or arbitration awards will be honored for fund release
Legal process costs may be deducted from held funds if ordered by court

9. FEES AND COSTS

9.1 Payment Holding Service Fees
No separate holding fees beyond platform fees specified in Terms of Service
Platform fees cover all payment holding services and fund management
Payment processing fees absorbed by FEND for ACH transfers
Wire transfer fees may be passed through to users

9.2 Additional Cost Scenarios
Returned payment fees: $25 for insufficient funds or rejected payments
Legal process fees: Actual costs for responding to court orders or garnishments
International wire fees: Actual bank charges for international transactions
Expedited processing fees: $50 for rush payment processing requests

10. RECORD KEEPING AND REPORTING

10.1 Transaction Records
Complete records maintained for all payment holding transactions
Individual account statements available through Platform dashboard
Annual tax reporting documents provided as required
Records retained for minimum of 7 years per legal requirements

10.2 Audit and Compliance
Regular third-party audits of payment holding fund management
Compliance with applicable money services and payment processing regulations
User access to payment holding account information through Platform
Quarterly reconciliation reports available upon request

11. TERMINATION AND FUND DISTRIBUTION

11.1 Account Termination Procedures
Active held funds must be resolved before account termination
No new Pilots may be funded during termination process
Existing Pilots continue under payment holding protection until completion
Final fund distribution within 30 days of all Pilot resolution

11.2 Service Termination by FEND
30 days advance notice required for payment holding service termination
Alternative payment arrangements facilitated for active Pilots
Full fund return for any Pilots that cannot be transferred
Compliance with state payment services termination requirements

12. LIABILITY AND INSURANCE

12.1 Payment Holding Service Provider Liability
FEND liable only for gross negligence or willful misconduct in payment holding management
Not liable for delays outside FEND's control (bank processing, disputes, etc.)
Not liable for investment losses on FDIC-insured instruments
Maximum liability limited to amount of specific held funds at issue

12.2 Insurance and Bonding
FEND maintains appropriate insurance coverage for payment holding operations
Fidelity bonding for personnel with access to held funds
Errors and omissions insurance for payment holding service activities
Cyber liability insurance for protection of held fund data

13. LEGAL AND REGULATORY COMPLIANCE

13.1 Applicable Laws
Payment holding services comply with Delaware money services and payment processing laws
Anti-money laundering (AML) and Know Your Customer (KYC) compliance
Reporting requirements for large transactions as required by law
International compliance for cross-border Pilot payments

13.2 Regulatory Changes
Payment holding terms may be updated to maintain legal compliance
Users notified of any changes affecting payment holding fund handling
Continued Platform use constitutes acceptance of compliance updates
Alternative arrangements offered if regulatory changes materially affect service

14. CONTACT INFORMATION

For all payment holding service questions, disputes, or issues:
Email: support@thefend.com
Phone: (650) 735-2255

Legal and Compliance:
Email: legal@thefend.com
FEND AI, Inc.
131 Continental Dr Suite 305
Newark, DE 19713, USA

© 2025 FEND AI, Inc. All rights reserved.
Document Version: 2.0 • Effective Date: June 24, 2025"""

        elif document_type == 'payment-terms':
            return """FEND AI, INC. PAYMENT TERMS
Effective Date: June 24, 2025
Version: 1.12

1. SCOPE AND APPLICATION

These Payment Terms govern all financial transactions on the FEND AI Platform, including subscription fees, Pilot payments, and platform fees. These terms are incorporated into the FEND AI Terms of Service and Payment Holding Service Agreement.

2. SUBSCRIPTION PAYMENTS

2.1 Annual Subscription Structure
Startup Plans: Pricing displayed during account registration based on selected plan tier
Enterprise Partner Plans: Pricing displayed during account registration based on selected plan tier
All subscriptions billed annually in advance
Payment required before account activation

2.2 Subscription Payment Methods
ACH bank transfers (preferred)
Corporate credit cards
Corporate checks (subject to clearing periods)
Wire transfers for international users
Payment must be from company accounts matching registered business name

2.3 Auto-Renewal and Billing
Subscriptions automatically renew annually unless cancelled
Renewal payments charged to payment method on file
90 days advance notice required to cancel auto-renewal
Failed renewal payments result in account suspension after 15-day grace period

3. PILOT PAYMENT STRUCTURE

3.1 Creator Payment Obligations
Total Payment Required: 105% of stated Pilot value
Breakdown: 100% Pilot value + 5% Creator platform fee
Payment Due: Before Pilot goes live on marketplace
Method: ACH transfer, wire transfer, or approved corporate payment

3.2 Completer Payment Structure
Payment Received: 95% of stated Pilot value
Platform Fee: 5% deducted from payment to Completer
Payment Timing: Upon Creator approval of completed deliverables
Method: ACH transfer to registered business bank account

3.3 Payment Calculation Examples
Example 1 - $50,000 Pilot:
Creator pays: $52,500 ($50,000 + $2,500 fee)
Completer receives: $47,500 ($50,000 - $2,500 fee)
FEND retains: $5,000 total platform fees

Example 2 - $100,000 Pilot:
Creator pays: $105,000 ($100,000 + $5,000 fee)
Completer receives: $95,000 ($100,000 - $5,000 fee)
FEND retains: $10,000 total platform fees

4. PAYMENT PROCESSING AND TIMING

4.1 Processing Timeframes
ACH Transfers: 2-3 business days to clear
Wire Transfers: 1-2 business days to clear
Corporate Checks: 5-7 business days to clear
Credit Cards: Immediate authorization, 1-2 business days settlement

4.2 Payment Release Schedule
Lump Sum Pilots: Payment released within 2 business days of Creator approval
Milestone Pilots: Individual milestone payments released upon separate approvals
Disputed Payments: Held in payment holding account pending resolution
International Payments: Additional 1-2 business days for currency conversion

4.3 Business Day Definition and SLA Integration
Business Days: Monday through Friday, 9 AM - 6 PM Eastern Time, excluding US federal holidays
SLA Compliance: All payment processing timeframes are subject to Platform Service Level Agreement commitments
Payment Processing Guarantees: Critical payment issues receive 2-hour response time during business hours
International Considerations: International payments may be subject to destination country banking schedules but remain within SLA frameworks

5. ACCEPTED PAYMENT METHODS

5.1 Domestic Payments (US)
ACH Bank Transfers: Direct bank-to-bank transfers (preferred method)
Corporate Checks: Business checks drawn on US banks
Wire Transfers: Domestic wire transfers for large amounts
Corporate Credit Cards: Visa, MasterCard, American Express for subscription payments

5.2 International Payments
International Wire Transfers: Swift network transfers in USD
Multi-Currency Support: EUR, GBP, CAD accepted with conversion to USD
International ACH: Limited availability through banking partners
Foreign Exchange: Market rates applied at time of processing

5.3 Prohibited Payment Methods
Personal checks or personal bank accounts
Cash or money orders
Cryptocurrency or digital currencies
Third-party payment processors not approved by FEND

6. FEES AND CHARGES

6.1 Platform Fees
Creator Platform Fee: 5% of Pilot value, paid upfront with payment holding funding
Completer Platform Fee: 5% of Pilot value, deducted from payment
Subscription Fees: Annual fees based on selected plan tier
No Hidden Fees: All fees clearly disclosed during transaction process

6.2 Payment Processing Fees
ACH Transfers: No additional fees (absorbed by FEND)
Wire Transfers: Actual bank charges passed through to user
International Transfers: Currency conversion fees and correspondent bank charges
Returned Payments: $25 fee for insufficient funds or rejected payments

6.3 Additional Service Fees
Pilot Cancellation: 1.5% of Pilot value (paid by cancelling Creator)
Expedited Processing: $50 for rush payment requests
Paper Check Issuance: $10 fee if electronic payment not possible
Account Research: $25/hour for detailed transaction research requests

7. PAYMENT SECURITY AND COMPLIANCE

7.1 Security Measures
PCI DSS compliance for all credit card processing
Bank-level encryption for all financial data transmission
Multi-factor authentication required for payment changes
Regular security audits and vulnerability assessments

7.2 Anti-Money Laundering (AML) Compliance
Know Your Customer (KYC) verification for all accounts
Transaction monitoring for suspicious activity patterns
Reporting requirements for large transactions as required by law
Enhanced due diligence for high-risk transaction categories

7.3 Tax Compliance and Reporting
1099 Reporting: Annual 1099 forms issued to US Completers earning $600+ annually
International Reporting: Compliance with applicable international tax treaties
Tax ID Requirements: Valid taxpayer identification numbers required for all accounts
Backup Withholding: Applied when required by tax regulations

8. PAYMENT DISPUTES AND RESOLUTION

8.1 Payment Dispute Categories
Subscription Billing Disputes: Challenges to subscription charges or billing errors
Pilot Payment Disputes: Disagreements over completion and payment release
Fee Disputes: Challenges to platform fees or additional charges
Processing Errors: Bank errors, failed transfers, or system malfunctions

8.2 Dispute Resolution Process
Step 1: Direct resolution through Platform support within 5 business days
Step 2: Formal dispute filing with documentation review
Step 3: Mediation services if direct resolution fails
Step 4: Binding arbitration for unresolved disputes per Terms of Service

8.3 Chargeback and Reversal Procedures
Credit Card Chargebacks: Users must contact FEND before initiating chargebacks
ACH Reversals: Limited reversal rights per banking regulations
Fraudulent Activity: Immediate investigation and account protection measures
Documentation Requirements: Comprehensive records required for all dispute claims

9. FAILED PAYMENTS AND ACCOUNT SUSPENSION

9.1 Subscription Payment Failures
Grace Period: 15 days to resolve failed subscription payments
Account Suspension: Loss of Platform access during payment failure period
Reinstatement: Immediate access restoration upon successful payment
Account Termination: Permanent closure after 90 days of non-payment

9.2 Pilot Payment Failures
Payment Holding Funding Failures: Pilot remains inactive until successful payment
Multiple Failures: Account restrictions after 3 failed payment attempts
Alternative Payment: Support provided to arrange alternative payment methods
Creator Protection: Pilots do not go live without confirmed payment holding account funding

10. REFUNDS AND CANCELLATIONS

10.1 Subscription Refunds
No Refunds: Annual subscription fees are non-refundable except as required by law
Prorated Upgrades: Credit applied for plan upgrades during subscription period
Cancellation Process: 90-day advance notice required to prevent auto-renewal
Final Billing: All outstanding fees due upon cancellation

10.2 Pilot Payment Refunds
Unsuccessful Pilots: Full refund if no Completer successfully delivers
Creator Cancellation: Full refund minus 1.5% cancellation fee
Partial Completion: Milestone-based refunds for incomplete work
Dispute Resolution: Refund amounts determined through dispute process outlined in Terms of Service and Payment Holding Service Agreement

11. CURRENCY AND INTERNATIONAL CONSIDERATIONS

11.1 Base Currency
US Dollars (USD): All Platform pricing and payments processed in USD
Currency Conversion: Foreign currency converted to USD at prevailing market rates
Exchange Rate: Rates determined at time of payment processing
Rate Fluctuation: Users bear risk of currency exchange rate changes

11.2 International User Considerations
Tax Obligations: International users responsible for local tax compliance
Banking Regulations: Compliance with local banking and money transfer regulations
Sanctions Compliance: Screening against US and international sanctions lists
Documentation: Additional documentation may be required for international payments

12. CONTACT INFORMATION

For all payment-related questions, billing issues, or disputes:
Email: support@thefend.com
Phone: (650) 735-2255

Legal and Compliance:
Email: legal@thefend.com
FEND AI, Inc.
131 Continental Dr Suite 305
Newark, DE 19713, USA

© 2025 FEND AI, Inc. All rights reserved.
Document Version: 1.12 • Effective Date: June 24, 2025"""

        elif document_type == 'privacy-policy':
            return """FEND AI, INC. PRIVACY POLICY
Effective Date: June 24, 2025
Version: 1.7

1. INTRODUCTION

FEND AI, Inc. ("FEND," "we," "us," or "our") respects your privacy and is committed to protecting your personal information. This Privacy Policy explains how we collect, use, disclose, and safeguard your information when you use our Platform.

This Privacy Policy applies to all users of the FEND Platform and is incorporated into our Terms of Service.

2. INFORMATION WE COLLECT

2.1 Business Account Information
Company name, address, and business contact information
Employer Identification Number (EIN) and business registration details
Employee count and company size category for proper plan classification
Business bank account information for payment processing

2.2 Authorized User Information (Personal Data)
Names, titles, and business email addresses of employees authorized to manage company accounts
Business phone numbers and work-related contact information
Login credentials and account access information
Payment authorization and billing contact details

2.3 Platform Business Data
Pilot project specifications and business requirements (non-personal business data)
Company-to-company communications through Platform messaging
Business transaction records and payment data
Company performance ratings and business feedback
Business usage analytics and company activity logs

2.4 Automatically Collected Information
Browser type, operating system, and device identifiers
Platform navigation patterns and feature usage analytics
Time stamps of Platform activities and session duration
Geographic location based on IP address
Cookies and similar tracking technologies

3. HOW WE USE YOUR INFORMATION

3.1 Platform Operations
Facilitate account registration and user verification
Process Pilot creation, bidding, and completion activities
Manage payment holding services and payment processing
Provide customer support and technical assistance
Monitor Platform performance and security

3.2 Business Communications
Send transactional emails related to Platform activities
Provide account statements and payment confirmations
Deliver important Platform updates and policy changes
Respond to user inquiries and support requests
Conduct user satisfaction surveys and feedback collection

3.3 Compliance and Security
Verify user identity and prevent fraudulent activity
Comply with legal obligations and regulatory requirements
Maintain transaction records for tax reporting and auditing
Investigate suspected violations of our Terms of Service
Protect Platform security and user safety

4. INFORMATION SHARING AND DISCLOSURE

4.1 Business Information Sharing Between Platform Users
Company information and business capabilities visible to potential Pilot partners
Business project specifications shared with selected Pilot Completers
Company performance ratings and business feedback displayed in company profiles
Business communication history related to specific Pilot projects
Business transaction completion status and payment confirmations

4.2 Authorized User Personal Data Sharing
Names and business contact information of authorized company representatives
Business communication between authorized users for Pilot coordination
Account management and billing contact information as necessary for Platform operations

4.3 Service Providers and Partners
Payment processors for subscription and Pilot payment processing
Banking partners for payment holding and ACH transfer services
Cloud hosting providers for Platform infrastructure and data storage
Customer support tools and communication platforms
Compliance and verification service providers

4.4 Legal and Regulatory Requirements
Responses to valid legal process, court orders, and government requests
Compliance with tax reporting obligations and financial regulations
Anti-money laundering (AML) and Know Your Customer (KYC) reporting
Cooperation with law enforcement investigations
Protection of FEND's legal rights and interests

4.5 Business Transfers
Information may be transferred in connection with mergers, acquisitions, or asset sales
Users will be notified of any ownership changes affecting privacy practices
Successor entities bound by substantially similar privacy commitments
User consent required for material changes to information handling

5. DATA RETENTION

5.1 Account Information
Account data retained for duration of active subscription plus 7 years
Payment and tax records retained per legal requirements (minimum 7 years)
Communication records retained for 3 years after Pilot completion
Performance data retained indefinitely for Platform analytics

5.2 Deletion and Anonymization
Users may request account deletion subject to legal retention requirements
Personal identifiers removed from retained business records where possible
Aggregated and anonymized data may be retained indefinitely
Backup systems may retain deleted information for up to 90 days

6. INTERNATIONAL DATA TRANSFERS

6.1 Cross-Border Processing
Information may be transferred to and processed in the United States
Transfers comply with applicable international data protection frameworks
Appropriate safeguards implemented for international data transfers
Users consent to international processing by using the Platform

6.2 GDPR Compliance for EU Users
Legal Basis for Processing: Contract performance (account management), legitimate interests (platform operations), and consent (marketing communications)
Data Protection Officer: Available at privacy@thefend.com for all EU user inquiries
EU User Rights: Access, rectification, erasure, restriction of processing, data portability, and objection to processing
Right to Withdraw Consent: EU users may withdraw consent for marketing communications at any time without affecting other services
Data Protection Impact Assessments: Conducted for all new Platform features that may impact EU user privacy
Privacy by Design: Platform features designed with privacy protection as default setting
Breach Notification: EU users notified within 72 hours of any personal data breaches that may affect their rights
Supervisory Authority: EU users may file complaints with their local data protection authority
Data Transfer Safeguards: EU personal data transfers protected by Standard Contractual Clauses and adequacy decisions where applicable

7. DATA SECURITY

7.1 Technical Safeguards
Industry-standard encryption for data transmission and storage
Multi-factor authentication for account access
Regular security audits and vulnerability assessments
Secure data centers with physical and environmental controls
Access controls limiting employee access to personal information

7.2 Organizational Measures
Privacy and security training for all employees with data access
Data breach response procedures and incident management
Regular review and updating of security policies and procedures
Vendor management program for third-party service providers
Privacy impact assessments for new Platform features

8. COOKIES AND TRACKING TECHNOLOGIES

8.1 Types of Cookies Used
Essential Cookies: Required for Platform functionality and security
Analytics Cookies: Used to understand Platform usage and performance
Preference Cookies: Remember user settings and customizations
Communication Cookies: Enable Platform messaging and notifications

8.2 Cookie Management
Users may disable non-essential cookies through browser settings
Cookie preferences can be managed through Platform account settings
Disabling essential cookies may limit Platform functionality
Third-party analytics tools subject to their respective privacy policies

9. USER RIGHTS AND CHOICES

9.1 Access and Control
Users may access and update account information through Platform settings
Request copies of personal information held by FEND
Correct inaccurate or incomplete information
Request deletion of account and personal information (subject to legal requirements)

9.2 Communication Preferences
Opt out of non-essential marketing communications
Control frequency and type of Platform notifications
Manage email preferences through account settings
Essential transactional communications cannot be disabled

9.3 CCPA Rights (California Residents)
Right to know what personal information is collected and how it's used
Right to delete personal information (subject to legal exceptions)
Right to opt out of sale of personal information (FEND does not sell personal information)
Right to non-discrimination for exercising CCPA rights

10. CHILDREN'S PRIVACY

FEND Platform is designed for business use and is not intended for individuals under 18 years of age. We do not knowingly collect personal information from children under 18. If we learn that we have collected information from a child under 18, we will delete that information immediately.

11. THIRD-PARTY LINKS AND SERVICES

11.1 External Links
Platform may contain links to third-party websites and services
Third-party sites have their own privacy policies and practices
FEND is not responsible for third-party privacy practices
Users should review third-party privacy policies before providing information

11.2 Integrated Services
Payment processing services integrated into Platform
Cloud storage and infrastructure service providers
Customer support and communication tools
Analytics and performance monitoring services

12. CONTACT INFORMATION

12.1 Privacy Questions and Requests
For privacy-related questions, data access requests, or to exercise your privacy rights:
Email: support@thefend.com
Phone: (650) 735-2255

Legal and Compliance:
Email: legal@thefend.com

12.2 Data Protection Officer (EU Users)
Email: privacy@thefend.com

12.3 Company Information
FEND AI, Inc.
131 Continental Dr Suite 305
Newark, DE 19713, USA

This Privacy Policy is effective as of the date listed above and supersedes all previous versions.

© 2025 FEND AI, Inc. All rights reserved.
Document Version: 1.7 • Effective Date: June 24, 2025"""

        elif document_type == 'data-processing-agreement':
            return """FEND AI, INC. DATA PROCESSING AGREEMENT
Effective Date: June 24, 2025
Version: 1.5

1. AGREEMENT SCOPE AND APPLICATION

This Data Processing Agreement ("DPA") governs the processing of personal data by FEND AI, Inc. ("FEND," "Processor") on behalf of European Union business customers ("Controller," "Customer") in connection with the FEND AI Platform services. This DPA supplements and forms part of the FEND AI Terms of Service and Privacy Policy.

This DPA applies only to business customers subject to the European Union General Data Protection Regulation (GDPR) and governs personal data processing activities conducted by FEND on behalf of the Customer in the provision of Platform services.

2. DEFINITIONS

For purposes of this DPA, the following definitions apply in addition to those set forth in the GDPR:

"Affiliate" means any entity that directly or indirectly controls, is controlled by, or is under common control with another entity.

"Data Subject" means the identified or identifiable natural person to whom Personal Data relates.

"Personal Data" means any information relating to an identified or identifiable natural person as defined by GDPR Article 4(1).

"Processing" means any operation performed on Personal Data, including collection, recording, organization, structuring, storage, adaptation, retrieval, consultation, use, disclosure by transmission, dissemination, restriction, erasure, or destruction.

"Standard Contractual Clauses" means the standard contractual clauses for the transfer of personal data to third countries approved by the European Commission.

"Sub-processor" means any third-party processor engaged by FEND to assist in fulfilling its obligations under this DPA.

3. DATA PROCESSING INSTRUCTIONS

3.1 Processing Scope
FEND shall process Personal Data only on behalf of and in accordance with Customer's documented instructions as set forth in:
- This DPA and the incorporated Standard Contractual Clauses
- The FEND AI Terms of Service
- Additional written instructions provided by Customer through the Platform interface
- Customer's configuration of Platform privacy settings and data handling preferences

3.2 Processing Purposes
FEND will process Personal Data solely for the following purposes:
- Provision of Platform services as specified in the Terms of Service
- Technical support and customer service activities
- Platform security, fraud prevention, and system monitoring
- Compliance with applicable legal obligations
- Other processing activities explicitly requested by Customer through documented instructions

3.3 Processing Restrictions
FEND will not:
- Process Personal Data for its own commercial purposes beyond Platform provision
- Transfer Personal Data to third parties except as authorized by this DPA
- Retain Personal Data longer than necessary for the agreed processing purposes
- Use Personal Data for marketing, advertising, or profiling activities unless specifically instructed

4. CATEGORIES OF DATA SUBJECTS AND PERSONAL DATA

4.1 Data Subjects
Personal Data processed under this DPA may relate to the following categories of Data Subjects:
- Customer's employees, contractors, and authorized representatives
- Customer's business contacts and professional network members
- End users of products or services promoted through Customer's Platform activities
- Data Subjects whose information is incidentally processed in connection with business-to-business activities on the Platform

4.2 Personal Data Categories
FEND may process the following categories of Personal Data on behalf of Customer:
- Contact information: names, business email addresses, business telephone numbers
- Professional information: job titles, department, company affiliation
- Account credentials: usernames, hashed passwords, authentication tokens
- Communication data: messages sent through Platform communication tools
- Usage data: Platform activity logs, feature utilization, session information
- Transaction data: payment information, billing details, transaction history
- Technical data: IP addresses, device identifiers, browser information

5. SUBPROCESSING

5.1 Customer Consent to Subprocessing
Customer provides general written authorization for FEND to engage Sub-processors for Personal Data processing, subject to the requirements of this Section 5.

5.2 Sub-processor Requirements
FEND ensures that any Sub-processor:
- Provides sufficient guarantees regarding implementation of appropriate technical and organizational measures
- Is bound by written contract requiring data protection obligations substantially equivalent to this DPA
- Processes Personal Data only for purposes specified in the Sub-processor agreement
- Implements appropriate safeguards for international data transfers if applicable

5.3 Current Sub-processors
FEND maintains a current list of Sub-processors at: https://thefend.com/legal/subprocessors
This list includes Sub-processor names, processing activities, and locations.

5.4 Sub-processor Changes
FEND will provide at least 30 days' advance notice of additions or changes to Sub-processors via:
- Updates to the Sub-processors page with email notification to Customer administrative contacts
- In-Platform notifications for significant Sub-processor changes
Customer may object to Sub-processor changes within 30 days of notice by providing specific reasons related to GDPR compliance.

6. SECURITY MEASURES

6.1 Technical and Organizational Measures
FEND implements appropriate technical and organizational measures to ensure Personal Data security, including:

Access Controls:
- Multi-factor authentication for all administrative access
- Role-based access control limiting data access to authorized personnel
- Regular access reviews and prompt deprovisioning of departing employees
- Encrypted access channels for all data transmission and storage

Data Protection:
- Encryption at rest using AES-256 encryption for all stored Personal Data
- Encryption in transit using TLS 1.3 for all data communications
- Database encryption with separate key management systems
- Regular encryption key rotation and secure key storage

Infrastructure Security:
- ISO 27001-certified data centers with 24/7 physical security monitoring
- Network segregation and firewalls protecting Personal Data systems
- Intrusion detection and automated threat response systems
- Regular vulnerability assessments and penetration testing

Operational Security:
- Employee background checks and confidentiality agreements
- Mandatory privacy and security training for all personnel
- Incident response procedures with defined escalation and notification protocols
- Regular security audits and compliance assessments

6.2 Security Incident Response
FEND maintains documented procedures for detecting, responding to, and reporting security incidents affecting Personal Data:
- 24/7 monitoring and automated alert systems for potential security breaches
- Immediate containment and remediation procedures for confirmed incidents
- Notification to Customer within 72 hours of incident discovery
- Detailed incident reports including impact assessment and remediation measures

7. INTERNATIONAL DATA TRANSFERS

7.1 Transfer Mechanisms
When FEND transfers Personal Data outside the European Economic Area, such transfers are governed by:
- European Commission Standard Contractual Clauses (Module Two: Controller-to-Processor transfers)
- Additional safeguards as required by GDPR Chapter V
- Transfer impact assessments for countries without adequacy decisions

7.2 Standard Contractual Clauses
The Standard Contractual Clauses attached as Annex A form an integral part of this DPA and take precedence over any conflicting provisions in case of inconsistency.

7.3 Transfer Restrictions
FEND will not transfer Personal Data to countries or recipients not approved by Customer or not covered by appropriate transfer mechanisms under GDPR.

8. DATA SUBJECT RIGHTS

8.1 Data Subject Requests
FEND will assist Customer in fulfilling Data Subject rights under GDPR Chapter III, including:
- Right of access (Article 15)
- Right to rectification (Article 16)
- Right to erasure (Article 17)
- Right to restriction of processing (Article 18)
- Right to data portability (Article 20)

8.2 Request Processing
Upon receiving a Data Subject request directly, FEND will:
- Promptly forward the request to Customer (within 48 hours)
- Assist Customer in responding within required timeframes
- Provide necessary technical assistance for data retrieval, modification, or deletion
- Document all request handling for compliance audit purposes

8.3 Technical Assistance
FEND provides the following technical assistance for Data Subject rights:
- Data export functionality through Platform interface
- Automated data deletion capabilities upon Customer instruction
- Data subject identification and cross-referencing tools
- Audit trails for all data processing activities

9. DATA PROTECTION IMPACT ASSESSMENTS

9.1 Cooperation Requirement
FEND will cooperate with Customer in conducting Data Protection Impact Assessments (DPIAs) when required under GDPR Article 35.

9.2 Information Provision
FEND will provide Customer with:
- Detailed descriptions of Personal Data processing activities
- Technical and organizational measures documentation
- Sub-processor information and safeguards
- Security incident history and remediation measures
- Any other information reasonably necessary for DPIA completion

10. COOPERATION WITH SUPERVISORY AUTHORITIES

10.1 Authority Cooperation
FEND will cooperate with Customer and competent supervisory authorities in the exercise of their duties under GDPR, including:
- Providing requested information about processing activities
- Allowing on-site inspections of data processing facilities
- Implementing corrective measures as directed by supervisory authorities
- Participating in investigations and enforcement proceedings as required

10.2 Notification Requirements
FEND will promptly notify Customer of:
- Direct contact from supervisory authorities regarding Customer's Personal Data
- Formal investigations or enforcement actions involving Customer data
- Regulatory guidance or requirements affecting processing activities

11. AUDITS AND COMPLIANCE

11.1 Audit Rights
Customer may audit FEND's compliance with this DPA through:
- Annual compliance certifications provided by FEND
- Third-party audit reports (upon reasonable request and subject to confidentiality)
- On-site inspections (with 30 days' advance notice and reasonable limitations)

11.2 Audit Documentation
FEND maintains comprehensive documentation of:
- Technical and organizational measures implementation
- Sub-processor management and oversight
- Security incident logs and response measures
- Employee training records and access controls
- Regular compliance assessments and improvement initiatives

12. DATA RETENTION AND DELETION

12.1 Retention Periods
FEND retains Personal Data only as long as necessary for:
- Provision of Platform services to Customer
- Compliance with legal retention requirements
- Resolution of disputes or legal proceedings
- As specified in Customer's documented retention instructions

12.2 Data Deletion
Upon termination of Platform services or Customer instruction, FEND will:
- Securely delete all Personal Data within 90 days unless longer retention is required by law
- Provide certification of deletion upon Customer request
- Ensure Sub-processors also delete Personal Data according to the same timeline
- Maintain appropriate documentation of deletion activities

13. LIABILITY AND INDEMNIFICATION

13.1 GDPR Compliance Liability
Each party shall be liable for damages caused by its own violation of GDPR obligations as determined by competent supervisory authorities or courts.

13.2 Joint Liability
Where both parties are found jointly liable for GDPR violations involving the same processing activities, liability shall be allocated based on the degree of responsibility for the violation as determined by applicable law.

14. TERM AND TERMINATION

14.1 Agreement Term
This DPA remains in effect for the duration of the FEND AI Terms of Service and any period during which FEND processes Personal Data on behalf of Customer.

14.2 Termination Effects
Upon termination:
- FEND's authority to process Personal Data on Customer's behalf immediately ceases
- Data deletion obligations under Section 12 take effect
- Confidentiality and security obligations survive termination indefinitely
- Audit and documentation obligations survive for the period required by applicable law

15. CONTACT INFORMATION

For all DPA-related matters, including Data Subject requests, security incidents, and compliance inquiries:

FEND Data Protection Officer
Email: privacy@thefend.com
Phone: (650) 735-2255

FEND Legal Department
Email: legal@thefend.com
FEND AI, Inc.
131 Continental Dr Suite 305
Newark, DE 19713, USA

© 2025 FEND AI, Inc. All rights reserved.
Document Version: 1.5 • Effective Date: June 24, 2025"""

        elif document_type == 'product-listing-agreement':
            return """FEND AI, INC. PRODUCT LISTING AND COMMISSION AGREEMENT
Effective Date: June 24, 2025
Version: 1.0

1. AGREEMENT SCOPE AND INTEGRATION

This Product Listing and Commission Agreement ("Listing Agreement") governs the promotion and sale of User products and services through FEND's Deals page and is incorporated into the FEND AI Terms of Service. By participating in the Deals program, you agree to these additional terms.

This Agreement applies to all Users who choose to list products or services on FEND's Deals page for promotion to the Platform community. Participation in the Deals program is voluntary and subject to FEND's approval and quality standards.

2. DEALS PROGRAM OVERVIEW

2.1 Program Description
The FEND Deals program provides a marketplace where Platform Users can promote and sell their products, services, and solutions to the FEND community. Featured listings reach qualified business audiences actively engaged in pilot projects and business development.

2.2 Eligible Offerings
Users may promote the following through the Deals program:
- Software products and SaaS solutions
- Professional services and consulting offerings  
- Technology tools and business solutions
- Training programs and educational services
- Hardware products and equipment
- Subscription services and ongoing support packages

2.3 Prohibited Listings
The following are prohibited from the Deals program:
- Products or services unrelated to business or technology
- Illegal products or services in any applicable jurisdiction
- Offensive, harmful, or inappropriate content
- Products that compete directly with FEND's core Platform services
- Services that circumvent the Platform for direct User-to-User transactions

3. LISTING REQUIREMENTS AND APPROVAL

3.1 Application Process
To participate in the Deals program, Users must:
- Submit a complete Deals application through the Platform interface
- Provide detailed product or service descriptions with accurate pricing
- Upload professional-quality images and marketing materials
- Agree to all terms of this Listing Agreement
- Maintain an active Platform subscription in good standing

3.2 FEND Review and Approval
FEND reserves the right to review and approve all Deals submissions based on:
- Quality and relevance to the Platform community
- Accuracy and completeness of listing information  
- Compliance with Platform terms and applicable laws
- Strategic fit with FEND's community and values
- User's reputation and performance history on the Platform

3.3 Listing Standards
Approved listings must maintain the following standards:
- Accurate product descriptions and pricing information
- Professional presentation and appropriate marketing language
- Current availability and delivery timeframes
- Responsive customer service and support capabilities
- Compliance with all applicable consumer protection laws

4. COMMISSION STRUCTURE AND PAYMENT TERMS

4.1 Commission Rates
FEND charges the following commission rates on successful sales through the Deals program:
- Standard Commission: 15% of gross sale price for most products and services
- Premium Services: 20% commission for high-touch consulting and custom development services
- Volume Discounts: Reduced commission rates may apply for Users with high monthly sales volume (>$50,000)
- Negotiated Rates: Enterprise partners may negotiate custom commission structures based on strategic value

4.2 Commission Calculation
Commission is calculated as follows:
- Base Amount: Total purchase price paid by customer (excluding taxes and shipping)
- Commission Fee: Applicable percentage applied to base amount
- Net Payment: Base amount minus commission fee, paid to listing User
- Example: For a $10,000 service sale with 15% commission, User receives $8,500, FEND retains $1,500

4.3 Payment Processing and Timing
- Customer payments are processed through FEND's secure payment system
- FEND holds payments in trust pending delivery confirmation
- Net payments to Users are released within 14 days of confirmed delivery/completion
- Monthly payment statements provided through User dashboard
- Payments made via wire transfer for amounts over $1,000, ACH for smaller amounts

5. USER RESPONSIBILITIES AND OBLIGATIONS

5.1 Product/Service Delivery
Listed Users are responsible for:
- Delivering products or services exactly as described in the listing
- Meeting all promised delivery timelines and specifications
- Providing appropriate customer support and documentation  
- Honoring all warranties and guarantees offered in the listing
- Resolving customer issues and handling returns/refunds appropriately

5.2 Legal Compliance
Users must ensure their offerings comply with:
- All applicable federal, state, and local laws and regulations
- Consumer protection laws and truth-in-advertising requirements
- Data privacy laws (GDPR, CCPA, etc.) for any personal data processing
- Industry-specific regulations relevant to their products or services
- Export control laws for international sales

5.3 Customer Communication
Users agree to:
- Respond to customer inquiries within 24 hours during business days
- Provide clear communication about delivery timelines and expectations
- Maintain professional and courteous communication at all times
- Resolve disputes in good faith and in accordance with Platform policies
- Report any significant customer issues to FEND support

6. FEND'S ROLE AND RESPONSIBILITIES

6.1 Platform Services
FEND provides:
- Secure e-commerce platform for listing and payment processing
- Marketing exposure to the qualified Platform community
- Customer support for purchase-related inquiries
- Dispute resolution services for transaction conflicts
- Analytics and reporting tools for sales performance tracking

6.2 Marketing and Promotion
FEND may promote Deals listings through:
- Featured placement on the Platform Deals page
- Email marketing to relevant User segments
- Social media promotion and content marketing
- Integration with Platform notifications and recommendations
- Participation in FEND events and webinars

6.3 Quality Assurance
FEND monitors Deals program quality through:
- Regular review of customer feedback and ratings
- Periodic audits of listing accuracy and delivery performance
- Investigation of customer complaints and dispute patterns
- Assessment of User compliance with Platform terms and legal requirements

7. INTELLECTUAL PROPERTY AND CONTENT RIGHTS

7.1 User Content Licensing
By participating in the Deals program, Users grant FEND:
- Non-exclusive license to display, reproduce, and distribute listing content
- Right to use product images, descriptions, and marketing materials for promotion
- Permission to include User testimonials and success stories in FEND marketing
- Right to create derivative marketing content based on User-provided materials

7.2 User IP Warranties
Users represent and warrant that:
- They own or have sufficient rights to all content provided for listings
- Product listings do not infringe third-party intellectual property rights
- All marketing claims and product descriptions are truthful and substantiated
- They have authority to grant the licensing rights specified in this Agreement

7.3 Trademark and Branding
- Users retain ownership of their trademarks and brand identities
- FEND may use User trademarks solely for promotional purposes within the Platform
- Users may not use FEND trademarks without explicit written permission
- Co-branding opportunities may be available for strategic partners

8. CUSTOMER DATA AND PRIVACY

8.1 Customer Information Sharing
FEND will provide listing Users with:
- Customer contact information necessary for product/service delivery
- Purchase details and delivery requirements
- Customer communication preferences and relevant business information
- Payment confirmation and transaction records

8.2 Data Protection Obligations
Users must:
- Protect customer information with appropriate security measures
- Use customer data solely for delivery and support of purchased products/services
- Comply with applicable data protection laws (GDPR, CCPA, etc.)
- Not share customer information with third parties without explicit consent
- Delete customer data when no longer needed for legitimate business purposes

8.3 Privacy Policy Requirements
Users handling customer data must maintain privacy policies that:
- Clearly describe data collection, use, and sharing practices
- Provide appropriate notice and consent mechanisms
- Include contact information for privacy-related inquiries
- Comply with applicable privacy law requirements
- Are easily accessible to customers through User's website or documentation

9. PERFORMANCE STANDARDS AND METRICS

9.1 Quality Metrics
FEND tracks the following performance indicators for Deals participants:
- Customer satisfaction ratings (target: 4.5+ out of 5 stars)
- On-time delivery rate (target: 95% or higher)
- Customer support response time (target: <24 hours)
- Dispute resolution rate (target: <5% of transactions)
- Refund/return rate (target: <10% of transactions)

9.2 Performance Reviews
- Monthly performance reports provided through User dashboard
- Quarterly business reviews for high-volume participants
- Annual strategic planning sessions for key partners
- Regular feedback collection from customers and continuous improvement initiatives

9.3 Performance Improvement
Users with performance below targets may be required to:
- Develop improvement plans with specific timelines and milestones
- Participate in additional training or support programs
- Implement additional quality assurance measures
- Provide more frequent reporting and communication

10. DISPUTE RESOLUTION AND CUSTOMER SATISFACTION

10.1 Customer Complaint Process
Customer complaints are handled through the following process:
- Initial customer contact with User for direct resolution attempt
- FEND mediation services if direct resolution is unsuccessful
- Formal dispute resolution through Platform dispute process
- Final resolution with appropriate remedies including refunds if necessary

10.2 Refund and Return Policies
- Users must clearly state refund and return policies in their listings
- Policies must comply with applicable consumer protection laws
- FEND may require refunds for non-delivery or material misrepresentation
- Disputed refunds are subject to FEND's determination based on evidence and policies

10.3 Dispute Resolution
For disputes between Users and customers:
- Mandatory initial 30-day direct negotiation period
- FEND mediation services available upon request
- Binding arbitration for unresolved disputes over $5,000
- Small claims court jurisdiction for smaller disputes

11. SUSPENSION AND TERMINATION

11.1 Suspension of Listings
FEND may suspend User listings for:
- Violation of Platform terms or this Listing Agreement
- Customer complaints or quality issues
- Legal compliance concerns
- Non-payment of Platform fees or commissions
- Fraudulent or deceptive practices

11.2 Termination of Participation
FEND may terminate User participation in the Deals program for:
- Material breach of Agreement terms
- Repeated performance issues or customer complaints
- Legal violations or fraudulent activity
- Failure to maintain active Platform subscription
- Conduct harmful to FEND's reputation or community

11.3 Effect of Termination
Upon termination:
- All active listings are immediately removed from the Platform
- Users remain responsible for fulfilling existing customer orders
- Final commission reconciliation and payment processing
- Customer data must be handled according to applicable retention requirements

12. LEGAL COMPLIANCE AND REPRESENTATIONS

12.1 Regulatory Compliance
Users represent that their participation in the Deals program complies with:
- All applicable business licensing and registration requirements
- Industry-specific regulations and professional standards
- Consumer protection and truth-in-advertising laws
- Data protection and privacy regulations
- Export control and international trade regulations

12.2 Tax Obligations
- Users are responsible for all applicable taxes on their sales
- FEND may be required to collect and remit sales taxes in certain jurisdictions
- Users must provide appropriate tax documentation (W-9, etc.) as required
- International sales may be subject to additional tax obligations and reporting

12.3 Insurance and Liability
Users are encouraged to maintain:
- General liability insurance appropriate for their business activities
- Professional liability insurance for service-based offerings
- Product liability coverage for physical products
- Errors and omissions coverage for technology services

13. PROGRAM MODIFICATIONS AND UPDATES

13.1 Agreement Changes
FEND may modify this Listing Agreement with:
- 60 days' advance notice for material changes affecting commission rates or core terms
- 30 days' advance notice for operational changes and policy updates
- Immediate changes for legal compliance or security reasons
- Option for Users to terminate participation if they disagree with material changes

13.2 Program Evolution
The Deals program may evolve to include:
- New product categories and listing types
- Enhanced marketing and promotional opportunities
- Additional analytics and business intelligence tools
- Integration with emerging Platform features and capabilities

14. CONTACT INFORMATION AND SUPPORT

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

© 2025 FEND AI, Inc. All rights reserved.
Document Version: 1.0 • Effective Date: June 24, 2025"""
        
        else:
            return f"Full legal document content not available for {document_type}"