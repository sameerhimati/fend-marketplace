# Digital Ocean Spaces Deployment Guide

This guide walks through deploying your Django Fend Marketplace app with Digital Ocean Spaces for static and media file storage.

## ✅ Completed Configuration

The following has been configured in your project:

### 1. Package Dependencies
- ✅ Added `boto3==1.34.23` and `django-storages==1.14.2` to `requirements.txt`
- ✅ Added `storages` to `INSTALLED_APPS` in base settings

### 2. Storage Backends
- ✅ Created `fend/storage_backends.py` with specialized storage classes:
  - `StaticStorage`: For CSS/JS files
  - `PublicMediaStorage`: For general media files
  - `OrganizationLogoStorage`: For company logos
  - `PilotDocumentStorage`: For pilot documents and PDFs

### 3. Production Settings
- ✅ Updated `fend/settings/production.py` with DO Spaces configuration
- ✅ Configured separate handling for static vs media files
- ✅ Set up CDN URL support

### 4. File Organization
- ✅ Updated file upload paths for better organization:
  - Logos: `media/logos/`
  - Pilot documents: `media/documents/pilots/{org}/{pilot_id}/{type}/`
  - Bid documents: `media/documents/bids/{startup}/{pilot}/`

### 5. Testing Tools
- ✅ Created `test_spaces_config.py` for configuration testing
- ✅ Created Django management command `test_storage`
- ✅ Created `migrate_to_spaces.py` for file migration

## 🔧 Environment Configuration Required

Update your `.env.prod` file with the correct Digital Ocean Spaces credentials:

```bash
# DigitalOcean Spaces Configuration
AWS_ACCESS_KEY_ID="YOUR_FULL_ACCESS_KEY_HERE"
AWS_SECRET_ACCESS_KEY="YOUR_FULL_SECRET_KEY_HERE"
AWS_STORAGE_BUCKET_NAME="fend-marketplace-media"
AWS_S3_ENDPOINT_URL="https://fend-marketplace-media.sfo3.digitaloceanspaces.com"
AWS_S3_REGION_NAME="sfo3"
AWS_S3_CUSTOM_DOMAIN="fend-marketplace-media.sfo3.cdn.digitaloceanspaces.com"
AWS_DEFAULT_ACL="public-read"
AWS_S3_OBJECT_PARAMETERS="{'CacheControl': 'max-age=86400'}"

# Enable S3/Spaces in production
USE_S3="True"
```

## 🚀 Deployment Steps

### Step 1: Verify Digital Ocean Spaces Setup
1. Ensure your DO Space `fend-marketplace-media` exists
2. Verify CDN is enabled
3. Check that your API keys have full access to the Space
4. Set proper CORS configuration if needed

### Step 2: Test Configuration Locally
```bash
# Test the connection (run from project root)
python test_spaces_config.py
```

### Step 3: Deploy to Production
```bash
# On your Digital Ocean server
git pull origin main

# Rebuild containers with new dependencies
docker-compose build web

# Start services
docker-compose up -d

# Run migrations if needed
docker-compose exec web python manage.py migrate

# Collect static files to DO Spaces
docker-compose exec web python manage.py collectstatic --noinput

# Test storage in production
docker-compose exec web python manage.py test_storage
```

### Step 4: Migrate Existing Files (Optional)
If you have existing media files, run the migration script:
```bash
docker-compose exec web python /app/migrate_to_spaces.py
```

## 📁 File Organization in DO Spaces

Your files will be organized as follows:

```
fend-marketplace-media/
├── static/
│   ├── admin/
│   ├── css/
│   └── js/
└── media/
    ├── logos/
    │   └── company-name.png
    └── documents/
        ├── pilots/
        │   └── {org-slug}/
        │       └── {pilot-id}/
        │           ├── technical/
        │           ├── performance/
        │           └── compliance/
        └── bids/
            └── {startup-slug}/
                └── {pilot-slug}/
                    └── proposal.pdf
```

## 🔗 URL Structure

- **Static files**: `https://fend-marketplace-media.sfo3.cdn.digitaloceanspaces.com/static/`
- **Media files**: `https://fend-marketplace-media.sfo3.cdn.digitaloceanspaces.com/media/`
- **Direct access**: `https://fend-marketplace-media.sfo3.digitaloceanspaces.com/`

## 🛠 Troubleshooting

### Access Denied Error
- Verify your DO Spaces API keys are complete and correct
- Check that the keys have full permissions to the Space
- Ensure the Space name matches exactly

### Files Not Loading
- Verify CDN is properly configured
- Check CORS settings in DO Spaces
- Ensure `AWS_S3_CUSTOM_DOMAIN` is set correctly

### Static Files Not Collecting
- Run `docker-compose exec web python manage.py check` first
- Verify `USE_S3=True` in production environment
- Check that all static file paths are correct

## 🔍 Testing Commands

```bash
# Test basic storage
docker-compose exec web python manage.py test_storage

# Collect static files
docker-compose exec web python manage.py collectstatic --noinput

# Django shell for manual testing
docker-compose exec web python manage.py shell
```

### Manual Testing in Django Shell
```python
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile

# Test file upload
test_file = ContentFile(b'Test content')
path = default_storage.save('test/manual_test.txt', test_file)
print(f"File saved: {path}")
print(f"File URL: {default_storage.url(path)}")

# Clean up
default_storage.delete(path)
```

## 📋 Post-Deployment Checklist

- [ ] Static files load correctly from CDN
- [ ] Media files upload and display properly
- [ ] Organization logos work in admin and frontend
- [ ] Pilot document uploads function correctly
- [ ] CDN caching headers are set appropriately
- [ ] All existing files migrated (if applicable)
- [ ] Local media files cleaned up (after verification)

## 🔄 Rollback Plan

If issues occur, you can quickly rollback by:

1. Set `USE_S3=False` in `.env.prod`
2. Restart containers: `docker-compose restart web`
3. Ensure local media directories exist
4. Restore local files from backup if needed

## 📝 Notes

- Files are set to `public-read` by default for CDN delivery
- Cache headers are optimized: 30 days for images/logos, 7 days for PDFs, 1 day for other files
- Static files have cache-busting via Django's file versioning
- The configuration maintains backward compatibility with local development