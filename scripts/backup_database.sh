#!/bin/bash
# Automated database backup script for Fend Marketplace

# Configuration
BACKUP_DIR="/root/fend-marketplace/backups/postgres"
CONTAINER_NAME="fend-marketplace-db-1"
DB_NAME="fend_db"
DB_USER="postgres"
RETENTION_DAYS=7

# Create backup directory if it doesn't exist
mkdir -p "$BACKUP_DIR"

# Generate timestamp
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="$BACKUP_DIR/fend_db_backup_$TIMESTAMP.sql"

# Create backup
echo "[$(date)] Starting database backup..."
docker exec -t "$CONTAINER_NAME" pg_dump -U "$DB_USER" "$DB_NAME" > "$BACKUP_FILE"

# Check if backup was successful
if [ $? -eq 0 ]; then
    # Compress the backup
    gzip "$BACKUP_FILE"
    echo "[$(date)] Backup successful: ${BACKUP_FILE}.gz"
    
    # Calculate size
    SIZE=$(ls -lh "${BACKUP_FILE}.gz" | awk '{print $5}')
    echo "[$(date)] Backup size: $SIZE"
    
    # Remove old backups
    echo "[$(date)] Cleaning up old backups..."
    find "$BACKUP_DIR" -name "fend_db_backup_*.gz" -mtime +$RETENTION_DAYS -delete
    
    # List remaining backups
    echo "[$(date)] Current backups:"
    ls -lh "$BACKUP_DIR"/*.gz 2>/dev/null | tail -5
else
    echo "[$(date)] ERROR: Backup failed!"
    exit 1
fi

echo "[$(date)] Backup process completed"