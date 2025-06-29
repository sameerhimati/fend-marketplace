#!/bin/bash
# Final File Structure Cleanup - Run Locally
# Cleans up duplicates, moves files, consolidates documentation

echo "🗂️ Final Fend Marketplace Cleanup"
echo "================================="

set -e

echo "📋 Step 1: Remove duplicates and empty directories..."

# Remove clear duplicates
rm -rf cloudflare-deploy/  # duplicate of static-site
rm -rf docker/            # empty directory
rm -rf config/            # duplicate crontab
rm -f crontab            # duplicate

echo "📋 Step 2: Move Python utilities to scripts/..."
mv migrate_to_spaces.py scripts/ 2>/dev/null || true
mv test_spaces_config.py scripts/ 2>/dev/null || true

echo "📋 Step 3: Clean up documentation files..."

# Remove redundant MD files
rm -f CLEANUP_PLAN.md
rm -f cleanup.sh
rm -f cleanup_safe.sh
rm -f CLOUDFLARE_AUTO_DEPLOY.md
rm -f DEPLOYMENT_GUIDE.md  # Info is in CLAUDE.md already
rm -f ROADMAP.md           # Outdated

# Move CLAUDE.md to docs/ and keep README.md at root
mkdir -p docs
mv CLAUDE.md docs/

echo "📋 Step 4: Update .gitignore..."
cat >> .gitignore << 'EOF'

# Django auto-generated
staticfiles/

# Python cache  
*.py[cod]
__pycache__/

# Logs
logs/
*.log
EOF

echo "📋 Step 5: Update README.md with essential commands..."
cat > README.md << 'EOF'
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
EOF

echo "✅ Cleanup complete!"
echo ""
echo "📋 Summary of changes:"
echo "✅ Removed cloudflare-deploy/, docker/, config/ (duplicates/empty)"
echo "✅ Moved Python utilities to scripts/"
echo "✅ Cleaned up documentation (kept README + docs/CLAUDE.md)"
echo "✅ Updated .gitignore"
echo "✅ Created concise README with essential commands"
echo ""
echo "🎯 Next steps:"
echo "1. Review the new README.md"
echo "2. Check that scripts/ has all your tools"
echo "3. Commit: git add . && git commit -m 'Clean up file structure'"
echo "4. Push: git push"