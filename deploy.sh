#!/bin/bash
# Clean deployment script for Fend Marketplace

# Exit on any error
set -e

# Show commands as they're executed
set -x

# Pull latest changes
git pull

# Stop running containers
docker-compose down

# Build the web container
docker-compose build web

# Start all services
docker-compose up -d

# Wait for services to start
sleep 5

# Run migrations
docker-compose exec web python manage.py migrate

# Collect static files
docker-compose exec web python manage.py collectstatic --noinput

# Check if everything is running properly
docker-compose ps

echo "Deployment complete!"
echo "Your site should be accessible at https://marketplace.fend.ai"