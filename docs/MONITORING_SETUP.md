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

## 2. Error Tracking (Self-Hosted)

We use self-hosted error logging to avoid external dependencies and costs.

### How It Works:

- Errors are logged to `/app/logs/errors.log` with rotation (10MB max, 5 backups)
- Console output shows all INFO+ level messages
- No external services or API keys required

### Viewing Errors:

1. **Real-time logs:**
   ```bash
   # View all container logs
   docker-compose logs -f web
   
   # View only error logs
   docker-compose exec web tail -f /app/logs/errors.log
   ```

2. **Search for specific errors:**
   ```bash
   # Find database errors
   docker-compose exec web grep -i "database" /app/logs/errors.log
   
   # Find errors from last hour
   docker-compose exec web grep "$(date -d '1 hour ago' '+%Y-%m-%d %H')" /app/logs/errors.log
   ```

3. **Quick monitoring script:**
   ```bash
   # Run the monitoring check
   docker-compose exec web python scripts/quick_log_check.py
   ```

### Testing Error Logging:

1. **Create a test error:**
   ```python
   # In Django shell: docker-compose exec web python manage.py shell
   import logging
   logger = logging.getLogger(__name__)
   logger.error("Test error for monitoring")
   
   # Or create an exception
   raise Exception("Test exception for logging")
   ```

2. **Check the logs:**
   ```bash
   docker-compose exec web tail -n 20 /app/logs/errors.log
   ```

### Future: AI-Powered Monitoring (Fend Labs Project)

We're building an AI monitoring tool that will:
- Analyze error patterns using Gemini AI
- Send intelligent alerts for critical issues
- Provide weekly health reports
- Suggest fixes based on error context

This will be the first Fend Labs pilot project!

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

No additional environment variables needed for self-hosted monitoring!

Optional configurations you might add later:

```bash
# Optional: Email notifications (when AI monitoring is added)
MONITORING_EMAIL=admin@yourdomain.com
GEMINI_API_KEY=your-key-here  # For future AI monitoring
```

## 6. Testing Your Monitoring Setup

### Test Uptime Monitoring:
1. Temporarily stop your Docker containers: `docker-compose down`
2. Verify UptimeRobot sends downtime alert
3. Restart containers: `docker-compose up -d`
4. Verify UptimeRobot sends recovery alert

### Test Error Logging:
1. Access Django shell: `docker-compose exec web python manage.py shell`
2. Create test error: `raise Exception("Test error")`
3. Check logs: `docker-compose exec web tail -20 /app/logs/errors.log`

### Test Health Check:
```bash
curl https://marketplace.fend.ai/health/
# Should return: {"status": "healthy", "database": "connected", "timestamp": "..."}
```

## 7. Ongoing Maintenance

### Weekly Tasks:
- Review error logs for patterns
- Check UptimeRobot uptime statistics
- Monitor server resource usage

### Monthly Tasks:
- Review and update alert thresholds
- Rotate old log files if needed
- Check disk space usage

### Emergency Procedures:
1. **Site Down:** Check DigitalOcean droplet status, Docker containers, and logs
2. **High Error Rate:** Check error logs: `docker-compose exec web tail -100 /app/logs/errors.log`
3. **Resource Issues:** Check server resources and consider scaling

## 8. Costs

- **UptimeRobot:** Free tier (50 monitors, 5-minute intervals)
- **Error Logging:** $0 (self-hosted)
- **DigitalOcean Monitoring:** Free with droplet
- **Future AI Monitoring:** Gemini free tier (60 requests/minute)

This setup provides comprehensive monitoring with zero ongoing costs!