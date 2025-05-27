#!/bin/bash
# Enhanced deployment script for Fend Marketplace
# Updated version with safety checks and better error handling

echo "🚀 Starting Fend Marketplace deployment..."

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

# Pull latest changes
echo "📥 Pulling latest changes from git..."
git pull

# Quick backup of current database (just in case)
echo "💾 Creating quick database backup..."
mkdir -p backups
docker-compose exec -T db pg_dump -U postgres fend_db > "backups/pre-deploy-$(date +%Y%m%d_%H%M%S).sql" || echo "⚠️  Backup failed, continuing..."

# Stop running containers
echo "🛑 Stopping current containers..."
docker-compose down

# Clean up old images to save space (optional)
echo "🧹 Cleaning up old Docker images..."
docker image prune -f || echo "No images to clean"

# Build the web container
echo "🔨 Building web container..."
docker-compose build web

# Start all services
echo "▶️  Starting all services..."
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

# Run migrations
echo "🗄️  Running database migrations..."
docker-compose exec web python manage.py migrate

# Collect static files
echo "📁 Collecting static files..."
docker-compose exec web python manage.py collectstatic --noinput

# Run Django system checks
echo "✅ Running Django system checks..."
docker-compose exec web python manage.py check

# Check if everything is running properly
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
echo "🎉 Deployment complete!"
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
echo ""

# Optional: Show recent logs
echo "📋 Recent web container logs:"
docker-compose logs web | tail -20