#!/bin/bash

# Create required directories
mkdir -p certbot/conf certbot/www

# Stop any running containers
docker-compose down

# Delete any existing certificates (use with caution if you already have valid certificates)
# rm -rf certbot/conf/*

# Start nginx container for domain validation
docker-compose up -d nginx

# Wait for nginx to start
echo "Waiting for nginx to start..."
sleep 5

# Get the certificate
docker-compose run --rm certbot certonly \
  --webroot \
  --webroot-path=/var/www/certbot \
  --email sameer@thefend.com \
  --agree-tos \
  --no-eff-email \
  -d 209.38.145.163

# Restart all services
docker-compose down
docker-compose up -d

echo "SSL certificate has been obtained. Check if https://209.38.145.163 is accessible."