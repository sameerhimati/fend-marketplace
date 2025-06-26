# Notification Cron Jobs Setup - Docker Version

This file contains the setup instructions for notification cron jobs in your Docker environment.

## Quick Setup (Recommended)

1. **SSH into your server and navigate to your project:**
   ```bash
   ssh your-server
   cd /path/to/fend-marketplace
   ```

2. **Run the setup script:**
   ```bash
   ./setup_notifications.sh
   ```

That's it! The cron jobs will now run automatically.

## Manual Setup (Alternative)

If you prefer to set it up manually:

1. **Update your deployment:**
   ```bash
   ./deploy.sh
   ```

2. **The new cron service will start automatically with these schedules:**
   - **Daily at 9 AM UTC**: Subscription expiry warnings (7 days advance)
   - **1st of month at 10 AM UTC**: Monthly deals digest
   - **15th of month at 9 AM UTC**: Deal refresh reminders

## Testing Commands

Test the commands manually in your Docker environment:

```bash
# Test subscription expiry notifications
docker-compose exec cron python manage.py send_subscription_expiry_notifications

# Test monthly deals digest
docker-compose exec cron python manage.py send_monthly_deals_digest

# Test deal refresh notifications  
docker-compose exec cron python manage.py send_deal_expiry_notifications
```

## Monitoring

**View cron logs:**
```bash
# Live logs from cron service
docker-compose logs -f cron

# View cron log file
tail -f logs/cron/cron.log
```

**Check cron service status:**
```bash
docker-compose ps cron
```

## What Each Command Does

1. **send_subscription_expiry_notifications**
   - Finds subscriptions expiring in exactly 7 days
   - Sends warning notifications to organization users
   - Helps prevent service interruptions

2. **send_monthly_deals_digest**
   - Sends top 5 partner deals to all active organizations
   - Excludes organizations' own deals
   - Encourages partnership discovery

3. **send_deal_expiry_notifications**
   - Finds promotions that haven't been updated in 30 days
   - Encourages organizations to refresh their deals
   - Keeps partner content fresh and engaging

## Production Notes

- Ensure the cron job runs as a user with access to your Django environment
- Update `/path/to/fend-marketplace` with your actual project path
- Consider using virtual environment activation if needed:
  ```bash
  0 9 * * * cd /path/to/fend-marketplace && source venv/bin/activate && python manage.py send_subscription_expiry_notifications
  ```