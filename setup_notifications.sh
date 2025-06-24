#!/bin/bash

# Setup script for notification cron jobs
echo "Setting up notification cron jobs..."

# Create logs directory if it doesn't exist
mkdir -p logs/cron

# Build and start the cron service
echo "Building cron service..."
docker-compose build cron

echo "Starting cron service..."
docker-compose up -d cron

# Show status
echo "Checking cron service status..."
docker-compose ps cron

echo ""
echo "✅ Notification cron jobs setup complete!"
echo ""
echo "To check cron logs:"
echo "  docker-compose logs -f cron"
echo ""
echo "To view cron log file:"
echo "  tail -f logs/cron/cron.log"
echo ""
echo "To test commands manually:"
echo "  docker-compose exec cron python manage.py send_subscription_expiry_notifications"
echo "  docker-compose exec cron python manage.py send_monthly_deals_digest"
echo "  docker-compose exec cron python manage.py send_deal_expiry_notifications"