# Staging Environment

Local staging environment that mirrors production for safe testing.

## Quick Start

```bash
# Start staging environment
./scripts/staging.sh start

# Visit staging site
open http://localhost:8080

# Stop when done
./scripts/staging.sh stop
```

## Features

- **Identical to Production**: Same Docker setup, same code
- **Separate Database**: `fend_staging_db` (won't affect production)
- **Different Ports**: Runs on 8080 (HTTP) and 8001 (Django)
- **Local Files**: No S3, everything stored locally
- **Console Email**: Email output goes to console logs

## Available Commands

```bash
./scripts/staging.sh start     # Start everything
./scripts/staging.sh stop      # Stop everything
./scripts/staging.sh restart   # Restart everything
./scripts/staging.sh logs      # View logs
./scripts/staging.sh shell     # Django shell
./scripts/staging.sh migrate   # Run migrations
./scripts/staging.sh test      # Test setup
```

## Configuration

Edit `.env.staging` for staging-specific settings:
- Database credentials
- Stripe test keys
- Debug settings
- Email backend

## Perfect For

- **Testing deployments** before production
- **Developing Fend Sentry** with real Django logs
- **Feature development** without breaking production
- **Database migrations** testing

## URLs

- **Main site**: http://localhost:8080
- **Health check**: http://localhost:8080/health/
- **Admin**: http://localhost:8080/admin/
- **Database**: localhost:5433 (postgres/postgres)

## Logs

Staging logs go to `/app/logs/staging_errors.log` in the container:

```bash
# View staging error logs
docker-compose -f docker-compose.staging.yml exec web cat /app/logs/staging_errors.log

# Monitor logs in real-time
./scripts/staging.sh logs
```

## Testing Fend Sentry

This staging environment is perfect for developing and testing Fend Sentry:

```bash
# Start staging
./scripts/staging.sh start

# Create test errors
./scripts/staging.sh shell
# In shell: logger.error("Test error for Fend Sentry")

# Test Fend Sentry against staging logs
cd ../fend-sentry
fend-sentry check --logs ../fend-marketplace/logs/staging_errors.log
```

## Cleanup

To completely reset staging:

```bash
./scripts/staging.sh stop
docker-compose -f docker-compose.staging.yml down -v  # Removes volumes
./scripts/staging.sh start
```

This removes all staging data and starts fresh.