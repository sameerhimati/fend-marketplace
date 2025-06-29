# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview
Fend Marketplace is a Django-based B2B platform connecting enterprises seeking innovative solutions with startups offering cutting-edge technology. The platform facilitates the entire pilot program lifecycle from discovery to completion, with an integrated Payment Holding Service and subscription model.

## Business Model & Pricing
- **Enterprise Plans**: $100/month (5 pilots) or $1000/year (unlimited pilots)  
- **Startup Plans**: $10/month or $100/year (unlimited bids)
- **Transaction Fees**: 10% total (5% from enterprise, 5% from startup) on completed pilots
- **Payment Method**: Wire transfers with Payment Holding Service protection

## Development Commands

### Local Development
```bash
# Run development server
python manage.py runserver

# Run migrations
python manage.py migrate

# Create migrations
python manage.py makemigrations

# Collect static files
python manage.py collectstatic --noinput

# Access Django shell
python manage.py shell

# Run system checks
python manage.py check
```

### Docker Development
```bash
# Build and start all services
docker-compose up -d

# Build only web container
docker-compose build web

# Run migrations in container
docker-compose exec web python manage.py migrate

# Collect static files in container
docker-compose exec web python manage.py collectstatic --noinput

# Access Django shell in container
docker-compose exec web python manage.py shell

# View logs
docker-compose logs -f web

# Stop all services
docker-compose down
```

### Database Operations
```bash
# Create database backup
docker-compose exec -T db pg_dump -U postgres fend_db > backup_$(date +%Y%m%d_%H%M%S).sql

# Restore database backup
docker-compose exec -T db psql -U postgres fend_db < backup_file.sql
```

### Production Deployment (Digital Ocean)
```bash
# Deploy using provided script (on Digital Ocean server via SSH)
./deploy.sh

# Manual deployment steps are documented in deploy.sh
# Uses Docker Compose with Nginx reverse proxy and Let's Encrypt SSL
```

## Project Architecture

### Django Apps Structure
- **fend/**: Main Django project configuration
  - `settings/`: Environment-specific settings (base, local, production)
  - Custom middleware for HTTPS redirect and authentication flow
- **apps/organizations/**: Organization management (enterprises & startups)
- **apps/pilots/**: Pilot project management and bidding system
- **apps/payments/**: Subscription management and Payment Holding Service
- **apps/users/**: Custom user model and authentication
- **apps/notifications/**: System notifications and messaging

### Key Models & Relationships
- **Organization**: Core entity for both enterprises and startups
  - Has subscription relationship for payment tracking
  - Tracks published pilot count against plan limits
  - Enterprise vs startup roles with different permissions
- **Pilot**: Project posted by enterprises
  - Links to PilotBid for startup proposals
  - Complex status workflow (draft → published → in_progress → completed)
  - Document attachments for technical specs, performance metrics, compliance
- **PilotBid**: Startup proposals for pilots
  - Manages entire bid lifecycle with status tracking
  - Calculates fees and payment splits automatically (5% each party)
  - Workflow: pending → approved → live → completion_pending → completed
- **Payment Holding Service**: Handles secure wire transfer processing
- **Subscription**: Manages organization payment plans and pilot limits

### Payment Flow Architecture
1. Enterprise approves startup bid → Payment Holding Service created
2. Enterprise receives wire transfer instructions
3. Enterprise initiates payment → Admin verifies receipt
4. Payment verified → Bid status moves to 'live'
5. Work completed → Enterprise verifies → Payment released to startup

### Authentication & Authorization
- Custom User model in `apps.users`
- Organization-based permissions (enterprise vs startup roles)  
- Subscription middleware enforces active subscriptions
- LOGIN_URL: `organizations:login`
- LOGIN_REDIRECT_URL: `organizations:dashboard`

### Business Logic Patterns
- **Pilot Publishing**: Validates organization subscription and pilot limits
- **Bid Workflow**: Complex state machine with automatic notification triggers
- **Fee Calculations**: Centralized in PilotBid model (5% from each party)
- **Subscription Validation**: Middleware enforces active subscriptions for platform access

### Frontend Architecture
- Server-side rendering with Django Templates
- Tailwind CSS for styling
- HTMX for interactive elements
- Responsive design for enterprise and startup dashboards

### Database Configuration
- PostgreSQL primary database
- Environment-based configuration (.env for local, .env.prod for production)
- Migrations managed through Django's standard system

### File Storage & Uploads
- Organization logos: `media/organization_logos/`
- Pilot specifications: `media/pilot_specs/` (organized by org/pilot/type)
- File storage: Local filesystem on Digital Ocean server
- Document types: technical specs, performance metrics, compliance requirements

### Infrastructure (Digital Ocean)
- Docker containers with Docker Compose
- Nginx reverse proxy with SSL/HTTPS
- Let's Encrypt automatic certificate renewal
- PostgreSQL database container
- Static/media file serving via Nginx

### Environment Configuration
- **Local**: Uses `.env` file for development settings
- **Production**: Uses `.env.prod` file for production settings
- Required environment variables:
  - `SECRET_KEY`: Django secret key
  - `DEBUG`: Boolean for debug mode
  - `DB_*`: Database connection parameters (NAME, USER, PASSWORD, HOST, PORT)
  - `STRIPE_*`: Stripe API keys and webhook secrets

### Key Settings
- Custom user model: `AUTH_USER_MODEL = 'users.User'`
- Session timeout: 24 hours with browser close expiration
- Static files: Collected to `staticfiles/` for production serving
- Media files: Stored in `media/` directory

### URL Structure
- `/admin/`: Django admin interface with payment management
- `/organizations/`: Organization dashboards and management
- `/pilots/`: Pilot creation, listing, and bidding
- `/payments/`: Subscription and Payment Holding Service management  
- `/notifications/`: User notifications and status updates

### Known Areas for Enhancement
- **Admin Interface**: Payment management workflow needs improvement
- **Input Validation**: Requires strengthening across platform
- **User Flow**: Some complex processes need simplification

### Development Dependencies
- `django-debug-toolbar` for local development
- `django-crispy-forms` with Tailwind CSS integration
- `phonenumbers` library for phone validation
- `stripe` for payment processing
- `psycopg2-binary` for PostgreSQL connection