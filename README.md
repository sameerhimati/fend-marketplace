# Fend Marketplace

A Django-based B2B platform connecting enterprises with startups through secure pilot programs.

## 🚀 Quick Start

### Local Development
```bash
# Start development
python manage.py runserver

# Database operations
python manage.py migrate
python manage.py makemigrations
python manage.py shell
```

### Production (Docker)
```bash
# Deploy to production
docker-compose up -d

# Database operations
docker-compose exec web python manage.py migrate
docker-compose exec web python manage.py collectstatic --noinput

# View logs
docker-compose logs -f web
```

### Staging (Local)
```bash
# Start local staging environment
./scripts/staging.sh start

# Visit staging: http://localhost:8080
# Stop staging
./scripts/staging.sh stop
```

## 🔧 Useful Scripts

All scripts are in the `scripts/` directory:

- **`backup_database.sh`** - Creates compressed database backup
- **`deploy.sh`** - Full production deployment with checks  
- **`deploy_fresh.sh`** - Fresh deployment (rebuilds everything)
- **`reset_database.sh`** - Resets database (⚠️ destructive)
- **`setup_notifications.sh`** - Sets up notification cron jobs
- **`migrate_to_spaces.py`** - Utility for migrating to DO Spaces
- **`test_spaces_config.py`** - Tests DO Spaces configuration

## 📊 Architecture

- **Frontend**: Django templates + Tailwind CSS + HTMX
- **Backend**: Django 5.x + PostgreSQL + Gunicorn
- **Storage**: DigitalOcean Spaces (S3-compatible)
- **Deployment**: Docker + Nginx + Let's Encrypt SSL
- **Infrastructure**: DigitalOcean Droplet + Cloudflare DNS

## 🔒 Security Features

- UFW firewall (ports 22, 80, 443 only)
- Fail2ban for brute force protection  
- Security headers (CSP, HSTS, XSS protection)
- Automated daily database backups
- Environment variable-based secrets

## 📄 Documentation

Detailed documentation is in `docs/CLAUDE.md` including:
- Business model & pricing
- Development commands
- Deployment instructions
- Security configuration

## 🌐 Live Sites

- **Landing Page**: https://fend.ai (auto-deploys from `static-site/`)
- **Marketplace**: https://marketplace.fend.ai

## ⚡ Environment

- **Production**: `.env.prod` (server only)
- **Development**: `.env` (local only)

Never commit environment files to Git!
