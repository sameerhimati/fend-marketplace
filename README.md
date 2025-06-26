# Fend Marketplace

A Django-based B2B platform connecting enterprises seeking innovative solutions with startups offering cutting-edge technology. The platform facilitates the entire pilot program lifecycle from discovery to completion, with an integrated Payment Holding Service and subscription model.

## Business Model & Pricing
- **Enterprise Plans**: $100/month (5 pilots) or $1000/year (unlimited pilots)  
- **Startup Plans**: $10/month or $100/year (unlimited bids)
- **Transaction Fees**: 10% total (5% from enterprise, 5% from startup) on completed pilots
- **Payment Method**: Wire transfers with Payment Holding Service protection

## Key Features

### 🎟️ Free Account Code System
- **Admin-generated promotional codes** for launch partners
- **Flexible plan assignment** (startup/enterprise, monthly/yearly)
- **Custom validity periods** and usage limits
- **Bulk management interface** with delete operations
- **Real-time validation** during registration

### 💰 Payment Holding Service
- **Secure wire transfer processing** with Mercury integration
- **3-stage admin workflow**: Invoice → Payment Confirmation → Fund Release
- **Automated fee calculations** (5% from each party)
- **Complete audit trail** and status tracking

### 🚀 Pilot Management
- **End-to-end pilot lifecycle** from posting to completion
- **Structured bidding system** with approval workflow
- **Document management** for specs, metrics, and compliance
- **Status tracking** with automated notifications

### 🏢 Organization Management
- **Separate enterprise and startup** registration flows
- **Admin approval workflow** for new organizations
- **Subscription enforcement** with plan limits
- **Legal document acceptance** tracking

## Technology Stack

- **Backend**: Django 5.2.1 with PostgreSQL
- **Frontend**: Server-side rendering with Tailwind CSS + HTMX
- **Payment Processing**: Stripe integration with wire transfer support
- **Infrastructure**: Docker containers on Digital Ocean
- **Security**: HTTPS with Let's Encrypt, secure file handling

## Development Setup

### Local Development
```bash
# Setup virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Setup environment
cp .env.example .env
# Edit .env with your local settings

# Run migrations
python manage.py migrate

# Create superuser
python manage.py createsuperuser

# Run development server
python manage.py runserver
```

### Docker Development
```bash
# Build and start all services
docker-compose up -d

# Run migrations in container
docker-compose exec web python manage.py migrate

# Access Django shell in container
docker-compose exec web python manage.py shell

# View logs
docker-compose logs -f web
```

## Project Architecture

### Django Apps Structure
- **`fend/`**: Main project configuration and custom middleware
- **`apps/organizations/`**: Organization management (enterprises & startups)
- **`apps/pilots/`**: Pilot project management and bidding system
- **`apps/payments/`**: Subscription management and Payment Holding Service
- **`apps/users/`**: Custom user model and authentication
- **`apps/notifications/`**: System notifications and messaging

### Key Models & Relationships
- **Organization**: Core entity with subscription and pilot limits
- **Pilot**: Projects with complex status workflow and document attachments
- **PilotBid**: Startup proposals with payment flow integration
- **Payment Holding Service**: Secure wire transfer processing
- **FreeAccountCode**: Promotional access system for partners

## Admin Features

### Payment Management Dashboard
- **Mercury integration** for wire transfer processing
- **3-stage workflow**: Generate Invoice → Check Payment → Release Funds
- **Real-time status tracking** and audit logs

### Free Account Code Management
- **Bulk code generation** with custom parameters
- **Advanced search and filtering** 
- **CSV export** with applied filters
- **Bulk delete operations** for cleanup

### Organization Approval
- **Streamlined approval workflow** for new registrations
- **Batch operations** for efficient processing
- **Business verification** and compliance tracking

## Production Deployment

### Environment Configuration
- **Local**: Uses `.env` file for development
- **Production**: Uses `.env.prod` file with production settings
- **Required variables**: Database, Stripe keys, secret keys

### Digital Ocean Deployment
```bash
# Deploy using provided script (on server via SSH)
./deploy.sh

# Manual deployment steps documented in deploy.sh
# Uses Docker Compose with Nginx reverse proxy and Let's Encrypt SSL
```

## Pre-Launch Roadmap

### ✅ **COMPLETED**
1. **Free Account Code System** - Complete implementation
   - Database model with plan associations
   - Custom admin interface with bulk operations
   - Frontend validation and redemption flow
   - Management commands and CSV export

2. **URL Infrastructure Fixes** - Comprehensive cleanup
   - Legal document URL standardization
   - Payment admin URL corrections
   - Registration form link repairs
   - Admin navigation fixes

3. **Payment System Integration**
   - Mercury wire transfer workflow
   - Stripe subscription management
   - Fee calculation automation
   - Audit trail implementation

4. **Admin Interface Enhancements**
   - Custom payment management dashboard
   - Organization approval workflow
   - Free code bulk management
   - Real-time statistics and reporting

### 🚧 **NEXT STEPS**
1. **Landing Page Content Updates**
   - Section reordering and layout improvements
   - Visual separators between sections
   - Content updates for key sections

2. **Production Deployment**
   - Update Stripe to production keys
   - Final testing of payment workflows
   - Launch partner onboarding

## Security & Compliance

- **Data Protection**: Secure handling of business and financial data
- **Legal Framework**: Terms of Service, Privacy Policy, User Agreements
- **Payment Security**: PCI-compliant payment processing
- **File Security**: Secure document upload and storage

## Support & Documentation

- **Development Commands**: See `CLAUDE.md` for detailed development workflows
- **API Documentation**: Available in Django admin interface
- **Legal Documents**: Available at `/legal/` endpoints
- **Admin Guides**: Built-in help text and tooltips

---

**Built with Django for scalable B2B marketplace operations**