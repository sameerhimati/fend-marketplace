#!/bin/bash

# Exit on any error
set -e

# Display commands as they're executed
set -x

# Define domain
DOMAIN="marketplace.fend.ai"
EMAIL="sameer@thefend.com"

# Create required directories
mkdir -p certbot/conf certbot/www

# Create a test file in the webroot to verify it's accessible
echo "Let's Encrypt verification test file" > certbot/www/test.txt

# Stop any running containers
docker-compose down

# Ensure nginx container is configured for the challenge
cat > nginx/app.conf.tmp << EOL
server {
    listen 80;
    server_name ${DOMAIN};
    
    # Detailed logging for Let's Encrypt challenges
    access_log /var/log/nginx/acme_access.log;
    error_log /var/log/nginx/acme_error.log debug;
    
    location /.well-known/acme-challenge/ {
        root /var/www/certbot;
        try_files \$uri =404;
        allow all;
    }
    
    location / {
        return 200 'Let\'s Encrypt verification is in progress!';
        add_header Content-Type text/plain;
    }
}
EOL

# Backup original config and use temporary config
cp nginx/app.conf nginx/app.conf.backup
mv nginx/app.conf.tmp nginx/app.conf

# Start nginx container for domain validation
docker-compose up -d nginx

# Wait for nginx to start
echo "Waiting for nginx to start..."
sleep 10

# Test if ACME challenge directory is accessible
echo "Testing if ACME challenge directory is accessible..."
curl -v http://${DOMAIN}/.well-known/acme-challenge/test.txt

# Get the certificate with verbose output
echo "Requesting certificate from Let's Encrypt..."
docker-compose run --rm --entrypoint "\
  certbot certonly --webroot \
    --webroot-path=/var/www/certbot \
    --email ${EMAIL} \
    --agree-tos \
    --no-eff-email \
    --force-renewal \
    --preferred-challenges http-01 \
    -v \
    -d ${DOMAIN}" certbot

# Restore original nginx config
mv nginx/app.conf.backup nginx/app.conf

# Update nginx config to use the certificates
cat > nginx/app.conf << EOL
server {
    listen 80;
    server_name ${DOMAIN};
    
    # Allow Let's Encrypt domain verification
    location /.well-known/acme-challenge/ {
        root /var/www/certbot;
    }
    
    # Redirect all HTTP requests to HTTPS
    location / {
        return 301 https://\$host\$request_uri;
    }
}

server {
    listen 443 ssl;
    server_name ${DOMAIN};
    
    # SSL certificates from Let's Encrypt
    ssl_certificate /etc/letsencrypt/live/${DOMAIN}/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/${DOMAIN}/privkey.pem;
    
    # SSL parameters for security
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_prefer_server_ciphers on;
    ssl_ciphers "EECDH+AESGCM:EDH+AESGCM:AES256+EECDH:AES256+EDH";
    ssl_session_cache shared:SSL:10m;
    ssl_session_timeout 1d;
    ssl_stapling on;
    ssl_stapling_verify on;
    
    # Add security headers
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
    add_header X-Content-Type-Options nosniff;
    add_header X-Frame-Options SAMEORIGIN;
    add_header X-XSS-Protection "1; mode=block";
    
    # Static and media files
    location /static/ {
        alias /app/staticfiles/;
    }
    
    location /media/ {
        alias /app/media/;
    }
    
    # Proxy requests to the Django app
    location / {
        proxy_pass http://web:8000;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
    }
}
EOL

# Restart all services
docker-compose down
docker-compose up -d

echo "SSL certificate has been obtained. Check if https://${DOMAIN} is accessible."
echo "To troubleshoot, check the logs: docker-compose logs nginx certbot"