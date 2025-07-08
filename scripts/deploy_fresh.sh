#!/bin/bash
# Enhanced fresh deployment script for Fend Marketplace
# This script pulls latest code and resets the database with safety checks

echo "🚀 Fend Marketplace Fresh Deployment"
echo "🚨 WARNING: This will delete ALL existing data!"
echo ""

# Exit on any error
set -e
# Show commands as they're executed (helpful for debugging)
set -x

# Pre-deployment checks
echo "📋 Running pre-deployment checks..."

# Check if we're in the right directory
if [ ! -f "manage.py" ] && [ ! -f "docker-compose.yml" ]; then
    echo "❌ Error: Not in the correct project directory"
    exit 1
fi

# Check if .env.prod exists
if [ ! -f ".env.prod" ]; then
    echo "❌ Error: .env.prod file not found"
    exit 1
fi

# Check git status
if ! git diff --quiet HEAD; then
    echo "⚠️  Warning: You have uncommitted changes"
    echo "Uncommitted files:"
    git status --porcelain
    read -p "Continue anyway? (y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "Deployment aborted"
        exit 1
    fi
fi

echo ""
echo "🚨 This will DELETE ALL DATA and start fresh!"
echo "Are you sure you want to deploy fresh? (y/N)"
read -r response

if [[ ! "$response" =~ ^[Yy]$ ]]; then
    echo "❌ Deployment cancelled."
    exit 1
fi

echo ""
echo "🔄 Starting fresh deployment process..."

# Quick backup of current database before wiping (just in case)
echo "💾 Creating final backup before fresh deployment..."
mkdir -p backups
docker-compose exec -T db pg_dump -U postgres fend_db > "backups/pre-fresh-deploy-$(date +%Y%m%d_%H%M%S).sql" || echo "⚠️  Backup failed (database might not exist), continuing..."

# Pull latest code
echo "📥 Pulling latest code from Git..."
git pull

if [[ $? -ne 0 ]]; then
    echo "❌ Git pull failed. Please resolve conflicts and try again."
    exit 1
fi

# Stop all services
echo "📦 Stopping Docker services..."
docker-compose down

# Clean up Docker resources to save space
echo "🧹 Cleaning up Docker resources..."
docker image prune -f || echo "No images to clean"
docker container prune -f || echo "No stopped containers to clean"

# Remove old static files to prevent conflicts
echo "🗑️  Removing old static files..."
docker-compose exec web rm -rf /app/staticfiles/* || echo "No static files to remove"

# Remove database volume - try common names
echo "🗑️  Removing database volume..."

# List volumes to identify the database volume
echo "📋 Current Docker volumes:"
docker volume ls | grep -E "(postgres|db|fend)"

# Try to remove common volume names
DB_VOLUME_NAMES=(
    "fend-marketplace_postgres_data"
    "fend_marketplace_postgres_data" 
    "fend-marketplace_db_data"
    "fend_db_data"
)

VOLUME_REMOVED=false

for volume_name in "${DB_VOLUME_NAMES[@]}"; do
    echo "Trying to remove volume: $volume_name"
    if docker volume rm "$volume_name" 2>/dev/null; then
        echo "✅ Successfully removed volume: $volume_name"
        VOLUME_REMOVED=true
        break
    fi
done

if [[ "$VOLUME_REMOVED" == false ]]; then
    echo "⚠️  Could not automatically remove database volume."
    echo "Please manually remove it:"
    echo "   docker volume ls"
    echo "   docker volume rm <your-postgres-volume-name>"
    echo ""
    echo "Press Enter after removing the volume manually..."
    read -r
fi

# Build all containers (including new cron service)
echo "🔨 Building all containers..."
docker-compose build

# Start all services
echo "🚀 Starting services..."
docker-compose up -d

# Wait for services to start properly
echo "⏳ Waiting for services to start..."
sleep 15

# Check if database is ready
echo "🔍 Checking database connectivity..."
MAX_RETRIES=10
RETRY_COUNT=0
while ! docker-compose exec -T db pg_isready -U postgres; do
    RETRY_COUNT=$((RETRY_COUNT + 1))
    if [ $RETRY_COUNT -ge $MAX_RETRIES ]; then
        echo "❌ Database failed to start after $MAX_RETRIES attempts"
        docker-compose logs db
        exit 1
    fi
    echo "Waiting for database... (attempt $RETRY_COUNT/$MAX_RETRIES)"
    sleep 2
done

# Generate new migrations if needed
echo "🔄 Checking for model changes and creating migrations..."
docker-compose exec web python manage.py makemigrations --dry-run --verbosity=1
echo "📝 Creating any needed migrations..."
docker-compose exec web python manage.py makemigrations

# Run migrations
echo "🔄 Running database migrations..."
docker-compose exec web python manage.py migrate

# Create default pricing plans
echo "💰 Creating default pricing plans..."
docker-compose exec web python manage.py create_default_plans

# Collect static files
echo "📁 Collecting static files..."
docker-compose exec web python manage.py collectstatic_s3 --noinput

# Configure Nginx based on storage settings
echo "⚙️  Configuring Nginx for static file serving..."
./scripts/setup_nginx.sh

# The collectstatic_s3 command above handles S3 uploads automatically

# Run Django system checks
echo "✅ Running Django system checks..."
docker-compose exec web python manage.py check

# Check service status
echo "📊 Current container status:"
docker-compose ps

# Health check
echo "🔍 Running health checks..."
sleep 5

# Check if web service responds
if curl -f -s https://marketplace.fend.ai > /dev/null; then
    echo "✅ HTTPS health check: PASSED"
elif curl -f -s http://marketplace.fend.ai > /dev/null; then
    echo "⚠️  HTTP health check: PASSED (HTTPS may not be configured)"
else
    echo "❌ Health check: FAILED"
    echo "📋 Web container logs:"
    docker-compose logs web | tail -10
fi

# Show final status
echo ""
echo "🎉 Fresh deployment complete!"
echo ""
echo "📊 Service Status:"
docker-compose ps
echo ""
echo "🌐 Your site should be accessible at:"
echo "   - https://marketplace.fend.ai"
echo "   - Admin: https://marketplace.fend.ai/admin/"
echo ""
echo "🔧 Useful post-deployment commands:"
echo "   - View logs: docker-compose logs -f"
echo "   - Check specific service: docker-compose logs [service_name]"
echo "   - Restart service: docker-compose restart [service_name]"
echo "   - Access Django shell: docker-compose exec web python manage.py shell"
echo "   - Check cron jobs: docker-compose logs cron"
echo "   - Test notifications: docker-compose exec cron python manage.py send_subscription_expiry_notifications"
echo ""
echo "📝 Next steps:"
echo "1. Create superuser:"
echo "   docker-compose exec web python manage.py createsuperuser"
echo ""
echo "2. Test your deployment:"
echo "   - Legal docs: https://marketplace.fend.ai/organizations/legal/terms-of-service/"
echo ""
echo "✅ Your Fend Marketplace is ready with fresh data!"
echo ""

# Optional: Show recent logs
echo "📋 Recent web container logs:"
docker-compose logs web | tail -20