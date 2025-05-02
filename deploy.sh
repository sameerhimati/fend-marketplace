#!/bin/bash
# Deployment script for Fend Marketplace with SSL support

# Exit on any error
set -e

# Show commands as they're executed
set -x

# Create logs directory if it doesn't exist
mkdir -p logs/nginx

# Check if we need to initialize SSL
if [ ! -d "certbot/conf/live/marketplace.fend.ai" ]; then
    echo "SSL certificates not found. Running initial SSL setup..."
    ./init-letsencrypt.sh
    # If the script fails, continue with HTTP for now
    if [ $? -ne 0 ]; then
        echo "SSL setup failed. Continuing with HTTP for now."
    fi
else
    echo "SSL certificates found. Proceeding with HTTPS deployment."
fi

# Stop running containers
docker-compose down

# Pull latest changes
git pull

# Build the web container without cache
docker-compose build --no-cache web

# Check if SSL certificates need renewal
if [ -d "certbot/conf/live/marketplace.fend.ai" ]; then
    docker-compose run --rm certbot renew
fi

# Start all services in detached mode
docker-compose up -d

# Sleep to ensure services are up and running
echo "Waiting for services to start..."
sleep 5

# Run migrations
docker-compose exec web python manage.py migrate

# Update pricing plans and token packages
docker-compose exec web python create_plans.py

# Fix startup display issues
docker-compose exec web python fix_startup_display.py

# Show logs to check for errors
docker-compose logs -f web