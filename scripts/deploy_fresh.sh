#!/bin/bash

# Fend Marketplace Fresh Production Deployment Script
# This script pulls latest code and resets the database

echo "🚀 Fend Marketplace Fresh Deployment"
echo "🚨 WARNING: This will delete ALL existing data!"
echo ""

# Check if we're in the right directory
if [[ ! -f "docker-compose.yml" ]]; then
    echo "❌ Error: docker-compose.yml not found. Please run this script from the project root directory."
    exit 1
fi

echo "Are you sure you want to deploy fresh? (y/N)"
read -r response

if [[ ! "$response" =~ ^[Yy]$ ]]; then
    echo "❌ Deployment cancelled."
    exit 1
fi

echo ""
echo "🔄 Starting fresh deployment process..."

# Pull latest code
echo "📥 Pulling latest code from Git..."
git pull origin main

if [[ $? -ne 0 ]]; then
    echo "❌ Git pull failed. Please resolve conflicts and try again."
    exit 1
fi

# Stop all services
echo "📦 Stopping Docker services..."
docker-compose down

# Remove database volume - try common names
echo "🗑️  Removing database volume..."

# List volumes to identify the database volume
echo "📋 Current Docker volumes:"
docker volume ls | grep -E "(postgres|db|fend)"

# Try to remove common volume names
DB_VOLUME_NAMES=(
    "fend-marketplace_postgres_data"
    "fend_marketplace_postgres_data" 
    "fend-marketplace_db_data"
    "fend_db_data"
)

VOLUME_REMOVED=false

for volume_name in "${DB_VOLUME_NAMES[@]}"; do
    echo "Trying to remove volume: $volume_name"
    if docker volume rm "$volume_name" 2>/dev/null; then
        echo "✅ Successfully removed volume: $volume_name"
        VOLUME_REMOVED=true
        break
    fi
done

if [[ "$VOLUME_REMOVED" == false ]]; then
    echo "⚠️  Could not automatically remove database volume."
    echo "Please manually remove it:"
    echo "   docker volume ls"
    echo "   docker volume rm <your-postgres-volume-name>"
    echo ""
    echo "Press Enter after removing the volume manually..."
    read -r
fi

# Start services
echo "🚀 Starting services..."
docker-compose up -d

# Wait for database to be ready
echo "⏳ Waiting for database to initialize..."
sleep 15

# Run migrations
echo "🔄 Running database migrations..."
docker-compose exec web python manage.py migrate

# Create default pricing plans
echo "💰 Creating default pricing plans..."
docker-compose exec web python manage.py create_default_plans

# Collect static files
echo "📁 Collecting static files..."
docker-compose exec web python manage.py collectstatic --noinput

# Configure Nginx based on storage settings
echo "⚙️  Configuring Nginx for static file serving..."
./scripts/setup_nginx.sh

# If using S3/Spaces, sync static files
echo "☁️  Checking if S3/Spaces is enabled..."
USE_S3=$(docker-compose exec -T web python -c "
import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'fend.settings.production')
django.setup()
from django.conf import settings
print(getattr(settings, 'USE_S3', False))
")
if [ "$USE_S3" = "True" ]; then
    echo "📤 Uploading static files to DigitalOcean Spaces..."
    # Force upload to S3/Spaces using manage.py
    docker-compose exec web python manage.py collectstatic --noinput --verbosity=2
    echo "✅ Static files uploaded successfully to S3/Spaces!"
fi

# Check service status
echo "🔍 Checking service status..."
docker-compose ps

echo ""
echo "🎉 Fresh deployment complete!"
echo ""
echo "🔧 Final steps:"
echo "1. Create superuser:"
echo "   docker-compose exec web python manage.py createsuperuser"
echo ""
echo "2. Test your deployment:"
echo "   - Admin: https://your-domain/admin/"
echo "   - Site: https://your-domain/"
echo "   - Legal docs: https://your-domain/organizations/legal/terms-of-service/"
echo ""
echo "✅ Your Fend Marketplace is ready with all optimizations!"
echo ""