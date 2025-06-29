#!/bin/bash
# Generate Nginx configuration based on USE_S3 setting

echo "⚙️  Setting up Nginx configuration based on storage settings..."

# Read USE_S3 from Django settings
USE_S3=$(docker-compose exec -T web python -c "
import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'fend.settings.production')
django.setup()
from django.conf import settings
print(getattr(settings, 'USE_S3', False))
")

echo "USE_S3 detected as: $USE_S3"

# Copy the template to the nginx config location
docker-compose exec nginx cp /app/nginx/app.conf.template /etc/nginx/conf.d/default.conf

if [ "$USE_S3" = "True" ]; then
    echo "📦 Configuring Nginx for S3/Spaces static file serving..."
    # Remove static file handling blocks from nginx config
    docker-compose exec nginx sed -i '/# Static file handling start/,/# Static file handling end/d' /etc/nginx/conf.d/default.conf
    echo "✅ Static files will be served from S3/Spaces"
else
    echo "📁 Configuring Nginx for local static file serving..."
    # Keep static file handling blocks (just remove the markers)
    docker-compose exec nginx sed -i '/# Static file handling start/d; /# Static file handling end/d' /etc/nginx/conf.d/default.conf
    echo "✅ Static files will be served locally by Nginx"
fi

# Reload nginx configuration
echo "🔄 Reloading Nginx configuration..."
docker-compose exec nginx nginx -s reload

echo "✅ Nginx configuration setup complete!"