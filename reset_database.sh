#!/bin/bash

# Fend Marketplace Database Reset Script
# WARNING: This will delete ALL database data!

echo "🚨 WARNING: This will delete ALL database data!"
echo "Are you sure you want to continue? (y/N)"
read -r response

if [[ ! "$response" =~ ^[Yy]$ ]]; then
    echo "❌ Database reset cancelled."
    exit 1
fi

echo "🔄 Starting database reset process..."

# Stop all services
echo "📦 Stopping Docker services..."
docker-compose down

# List all volumes to help identify the correct one
echo "📋 Available Docker volumes:"
docker volume ls

# Database volume name from docker-compose.yml
DB_VOLUME_NAME="$(basename $(pwd))_postgres_data"

echo "🔍 Expected database volume name: $DB_VOLUME_NAME"

echo "🗑️  Removing database volume..."

if docker volume rm "$DB_VOLUME_NAME" 2>/dev/null; then
    echo "✅ Successfully removed volume: $DB_VOLUME_NAME"
else
    echo "⚠️  Could not remove volume: $DB_VOLUME_NAME"
    echo "📋 Available volumes:"
    docker volume ls | grep postgres
    echo ""
    echo "💡 You may need to manually remove the correct volume:"
    echo "   docker volume rm <volume-name>"
fi

# If no specific volume found, show manual command
echo ""
echo "💡 If the automatic removal didn't work, manually check volumes:"
echo "   docker volume ls"
echo "   docker volume rm <your-postgres-volume-name>"
echo ""

# Start services with fresh database
echo "🚀 Starting services with fresh database..."
docker-compose up -d

# Wait for database to be ready
echo "⏳ Waiting for database to be ready..."
sleep 10

# Run migrations
echo "🔄 Running database migrations..."
docker-compose exec web python manage.py migrate

# Collect static files
echo "📁 Collecting static files..."
docker-compose exec web python manage.py collectstatic --noinput

# Show next steps
echo ""
echo "✅ Database reset complete!"
echo ""
echo "🔧 Next steps:"
echo "1. Create superuser: docker-compose exec web python manage.py createsuperuser"
echo "2. Access admin: http://your-domain/admin/"
echo "3. Access site: http://your-domain/"
echo ""
echo "🎯 Your fresh Fend Marketplace is ready with:"
echo "   ✅ Payment Holding Service terminology"
echo "   ✅ Optimized database schema"
echo "   ✅ Public legal document access"
echo "   ✅ Clean codebase"
echo ""