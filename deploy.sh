#!/bin/bash
# Deployment script for Fend Marketplace with SSL support

# Show commands as they're executed
set -x

# Stop running containers
docker-compose down

# Pull latest changes
git pull

# Build the web container without cache
docker-compose build --no-cache web

# Check if SSL certificates need renewal
docker-compose run --rm certbot renew

# Start all services in detached mode
docker-compose up -d

# Sleep to ensure services are up and running
echo "Waiting for services to start..."
sleep 5

# Run migrations
docker-compose exec web python manage.py migrate

# Update pricing plans and token packages
docker-compose exec web python create_plans.py

# Fix startup subscriptions
# docker-compose exec web python create_startup_subscriptions.py

# Fix startup display issues
docker-compose exec web python fix_startup_display.py

# Show logs to check for errors
docker-compose logs -f web