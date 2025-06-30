#!/bin/bash

set -e

echo "🚀 Fend Marketplace - Staging Environment"
echo "=========================================="

# Function to show usage
show_usage() {
    echo "Usage: $0 [start|stop|restart|logs|shell|migrate|test]"
    echo ""
    echo "Commands:"
    echo "  start    - Start staging environment"
    echo "  stop     - Stop staging environment"
    echo "  restart  - Restart staging environment"
    echo "  logs     - View logs"
    echo "  shell    - Access Django shell"
    echo "  migrate  - Run database migrations"
    echo "  test     - Test staging setup"
    echo ""
}

# Check if .env.staging exists
if [ ! -f .env.staging ]; then
    echo "❌ .env.staging file not found!"
    echo "Please copy .env.staging template and configure it."
    exit 1
fi

# Docker Compose command (handle both old and new syntax)
if command -v docker-compose &> /dev/null; then
    DOCKER_COMPOSE="docker-compose"
else
    DOCKER_COMPOSE="docker compose"
fi

STAGING_CMD="$DOCKER_COMPOSE -f docker-compose.staging.yml --env-file .env.staging"

case "${1:-}" in
    "start")
        echo "🏗️  Starting staging environment..."
        $STAGING_CMD up -d --build
        
        echo "⏳ Waiting for services to start..."
        sleep 10
        
        echo "🗄️  Running migrations..."
        $STAGING_CMD exec web python manage.py migrate
        
        echo "📁 Collecting static files..."
        $STAGING_CMD exec web python manage.py collectstatic --noinput
        
        echo "💰 Creating default pricing plans..."
        $STAGING_CMD exec web python manage.py create_default_plans
        
        echo ""
        echo "✅ Staging environment started!"
        echo "🌐 Visit: http://localhost:8080"
        echo "🔍 Health: http://localhost:8080/health/"
        echo "👤 Admin: http://localhost:8080/admin/"
        echo ""
        ;;
        
    "stop")
        echo "🛑 Stopping staging environment..."
        $STAGING_CMD down
        echo "✅ Staging environment stopped"
        ;;
        
    "restart")
        echo "🔄 Restarting staging environment..."
        $STAGING_CMD down
        $STAGING_CMD up -d --build
        echo "✅ Staging environment restarted"
        ;;
        
    "logs")
        echo "📋 Viewing staging logs..."
        $STAGING_CMD logs -f
        ;;
        
    "shell")
        echo "🐍 Accessing Django shell..."
        $STAGING_CMD exec web python manage.py shell
        ;;
        
    "migrate")
        echo "🗄️  Running migrations..."
        $STAGING_CMD exec web python manage.py migrate
        echo "✅ Migrations complete"
        ;;
        
    "test")
        echo "🧪 Testing staging setup..."
        
        # Test health endpoint
        echo "Testing health endpoint..."
        curl -f http://localhost:8080/health/ || echo "❌ Health check failed"
        
        # Test main page
        echo "Testing main page..."
        curl -f -s http://localhost:8080/ > /dev/null && echo "✅ Main page accessible" || echo "❌ Main page failed"
        
        # Show container status
        echo "Container status:"
        $STAGING_CMD ps
        ;;
        
    *)
        show_usage
        exit 1
        ;;
esac