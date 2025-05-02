#!/bin/bash
# Debug script for diagnosing SSL/HTTPS issues

# Define domain
DOMAIN="marketplace.fend.ai"
IP="209.38.145.163"

# Setup logging
exec > >(tee -i ssl-debug.log)
exec 2>&1

echo "=== SSL/HTTPS Debug Script ==="
echo "Domain: $DOMAIN"
echo "Server IP: $IP"
echo "Date: $(date)"
echo

# Check DNS resolution
echo "=== DNS Resolution ==="
echo "Checking DNS for $DOMAIN..."
dig +short $DOMAIN

echo "Checking DNS trace for $DOMAIN..."
dig +trace $DOMAIN

echo "Checking reverse DNS for $IP..."
dig +short -x $IP

echo

# Check HTTP accessibility
echo "=== HTTP Accessibility ==="
echo "Checking HTTP access to $DOMAIN..."
curl -IL http://$DOMAIN

echo "Checking access to Let's Encrypt challenge directory..."
curl -IL http://$DOMAIN/.well-known/acme-challenge/

echo

# Check certificates if they exist
echo "=== Certificate Check ==="
if [ -d "certbot/conf/live/$DOMAIN" ]; then
    echo "Found certificates for $DOMAIN"
    ls -la certbot/conf/live/$DOMAIN/
    
    # Check certificate details
    echo "Certificate details:"
    docker-compose run --rm --entrypoint "openssl x509 -text -noout -in /etc/letsencrypt/live/$DOMAIN/cert.pem" certbot
    
    # Check validity
    echo "Certificate validity:"
    docker-compose run --rm --entrypoint "openssl x509 -dates -noout -in /etc/letsencrypt/live/$DOMAIN/cert.pem" certbot
else
    echo "No certificates found for $DOMAIN"
fi

echo

# Check container status
echo "=== Container Status ==="
docker-compose ps

echo

# Check Nginx configuration
echo "=== Nginx Configuration Check ==="
docker-compose exec nginx nginx -t

echo

# Check Nginx logs
echo "=== Nginx Logs ==="
echo "Last 20 lines of Nginx error log:"
docker-compose exec nginx tail -n 20 /var/log/nginx/error.log

echo "Last 20 lines of Nginx access log:"
docker-compose exec nginx tail -n 20 /var/log/nginx/access.log

echo

# Check Certbot logs
echo "=== Certbot Logs ==="
if docker-compose logs certbot > /dev/null 2>&1; then
    echo "Last 20 lines of Certbot logs:"
    docker-compose logs certbot | tail -n 20
else
    echo "No Certbot logs available"
fi

echo

# Test SSL if available
echo "=== SSL Test ==="
if [ -d "certbot/conf/live/$DOMAIN" ]; then
    echo "Testing SSL connection to $DOMAIN..."
    echo | openssl s_client -connect $DOMAIN:443 -servername $DOMAIN
else
    echo "SSL not yet configured for $DOMAIN"
fi

echo "=== Debug Complete ==="
echo "Check ssl-debug.log for the full output"