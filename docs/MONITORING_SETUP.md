# Production Monitoring Setup Guide

This guide covers setting up comprehensive monitoring for the Fend Marketplace platform running on DigitalOcean.

## 1. Uptime Monitoring with UptimeRobot

### Setup Steps:

1. **Sign up for UptimeRobot** at https://uptimerobot.com (free tier includes 50 monitors)

2. **Create monitors for your platform:**
   - **Main Marketplace Monitor:**
     - Monitor Type: HTTP(s)
     - Friendly Name: "Fend Marketplace"
     - URL: `https://marketplace.fend.ai`
     - Monitoring Interval: 5 minutes (free tier)
     - Expected Status: 200 (OK)

   - **Health Check Monitor (Recommended):**
     - Monitor Type: HTTP(s)
     - Friendly Name: "Fend Marketplace Health Check"
     - URL: `https://marketplace.fend.ai/health/`
     - Monitoring Interval: 5 minutes
     - Expected Status: 200 (OK)
     - Advanced Settings: Check for keyword "healthy"

3. **Configure Alert Contacts:**
   - Add email notifications for downtime alerts
   - Consider SMS alerts for critical issues (paid feature)
   - Set up Slack/Discord webhooks if using team channels

4. **Alert Settings:**
   - Send alerts when monitor goes down
   - Send recovery notifications when monitor comes back up
   - Recommended: Alert after 2 consecutive failed checks

### Health Check Endpoint

The platform now includes a `/health/` endpoint that:
- Tests database connectivity
- Returns JSON status with timestamp
- Returns HTTP 503 if database is unreachable
- Provides more reliable monitoring than homepage checks

## 2. Error Tracking with Sentry

### Setup Steps:

1. **Create Sentry Account** at https://sentry.io (free tier includes 5,000 errors/month)

2. **Create New Django Project:**
   - Choose Django as the platform
   - Copy the DSN (Data Source Name) provided

3. **Add Sentry DSN to Environment:**
   Add to your `.env.prod` file:
   ```bash
   SENTRY_DSN=https://your-dsn-here@sentry.io/project-id
   ```

4. **Deploy Updated Code:**
   ```bash
   # On your DigitalOcean server
   ./deploy.sh
   ```

### Sentry Configuration Features:

- **Error Tracking:** Automatically captures Django exceptions
- **Performance Monitoring:** Tracks 10% of transactions for performance insights
- **Breadcrumbs:** Captures logs leading up to errors
- **Release Tracking:** Can be configured to track code deployments
- **User Context:** Configured to NOT send personal information (GDPR compliant)

### Testing Sentry Setup:

1. **Create a test error** by adding this to your Django shell:
   ```python
   # In Django shell: python manage.py shell
   import logging
   logger = logging.getLogger(__name__)
   logger.error("Test error for Sentry monitoring")
   
   # Or create an exception
   raise Exception("Test exception for Sentry")
   ```

2. **Check Sentry dashboard** to confirm errors are being captured

## 3. Basic Server Resource Monitoring

### Option A: DigitalOcean Built-in Monitoring

1. **Enable in DigitalOcean Dashboard:**
   - Go to your Droplet dashboard
   - Click "Monitoring" tab
   - Enable built-in monitoring for:
     - CPU usage
     - Memory usage
     - Disk usage
     - Network I/O

2. **Set up alerts:**
   - CPU usage > 80% for 10 minutes
   - Memory usage > 90% for 5 minutes
   - Disk usage > 85%

### Option B: Simple Script-based Monitoring

Create a monitoring script that checks system resources:

```bash
#!/bin/bash
# Save as scripts/check_resources.sh

# Set thresholds
CPU_THRESHOLD=80
MEMORY_THRESHOLD=85
DISK_THRESHOLD=85

# Check CPU usage
CPU_USAGE=$(top -bn1 | grep "Cpu(s)" | awk '{print $2}' | cut -d'%' -f1)

# Check memory usage
MEMORY_USAGE=$(free | grep Mem | awk '{printf("%.0f", $3/$2 * 100.0)}')

# Check disk usage
DISK_USAGE=$(df -h / | awk 'NR==2{print $5}' | cut -d'%' -f1)

echo "CPU: ${CPU_USAGE}%, Memory: ${MEMORY_USAGE}%, Disk: ${DISK_USAGE}%"

# Add alerting logic here (send to webhook, email, etc.)
```

## 4. Alert Configuration

### UptimeRobot Alerts:
- **Downtime Alert:** Immediate notification when site is unreachable
- **Recovery Alert:** Notification when site comes back online
- **Performance Alert:** If response time exceeds threshold (premium feature)

### Sentry Alerts:
1. **Go to Project Settings > Alerts**
2. **Create alert rules:**
   - **High Error Rate:** When error rate exceeds 10 errors in 1 minute
   - **New Error Types:** When a new type of error occurs
   - **Performance Issues:** When response time degrades significantly

### Recommended Alert Channels:
- **Email:** Primary contact for all alerts
- **Slack/Discord:** For team notifications
- **SMS:** For critical downtime only (to avoid spam)

## 5. Environment Variables Summary

Add these to your `.env.prod` file:

```bash
# Sentry Error Tracking
SENTRY_DSN=https://your-dsn-here@sentry.io/project-id

# Optional: Additional monitoring configurations
MONITORING_EMAIL=admin@yourdomain.com
```

## 6. Testing Your Monitoring Setup

### Test Uptime Monitoring:
1. Temporarily stop your Docker containers: `docker-compose down`
2. Verify UptimeRobot sends downtime alert
3. Restart containers: `docker-compose up -d`
4. Verify UptimeRobot sends recovery alert

### Test Error Tracking:
1. Access Django shell: `docker-compose exec web python manage.py shell`
2. Create test error: `raise Exception("Test error")`
3. Check Sentry dashboard for the error

### Test Health Check:
```bash
curl https://marketplace.fend.ai/health/
# Should return: {"status": "healthy", "database": "connected", "timestamp": "..."}
```

## 7. Ongoing Maintenance

### Weekly Tasks:
- Review Sentry error reports for trends
- Check UptimeRobot uptime statistics
- Monitor server resource usage

### Monthly Tasks:
- Review and update alert thresholds
- Clean up resolved Sentry issues
- Check monitoring service quotas

### Emergency Procedures:
1. **Site Down:** Check DigitalOcean droplet status, Docker containers, and logs
2. **High Error Rate:** Check Sentry for error details and recent deployments
3. **Resource Issues:** Check server resources and consider scaling

## 8. Costs

- **UptimeRobot:** Free tier (50 monitors, 5-minute intervals)
- **Sentry:** Free tier (5,000 errors/month, 14-day retention)
- **DigitalOcean Monitoring:** Free with droplet

This setup provides comprehensive monitoring without additional costs for small to medium traffic levels.