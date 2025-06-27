from .base import *
import os

# Add your domain to ALLOWED_HOSTS
ALLOWED_HOSTS = ['209.38.145.163', 'localhost', '127.0.0.1', 'marketplace.fend.ai']

# Make sure debug is off in production
DEBUG = False

# Security Settings for HTTPS
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
SECURE_SSL_REDIRECT = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = 'DENY'
SECURE_HSTS_SECONDS = 31536000  # 1 year
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True

# Production Email Settings
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_USE_SSL = False
EMAIL_USE_TLS = True

# Additional email security
EMAIL_TIMEOUT = 30

# Allow CSRF protection to work with HTTPS
CSRF_TRUSTED_ORIGINS = ['https://marketplace.fend.ai']

# Digital Ocean Spaces Configuration
USE_S3 = os.getenv('USE_S3', 'False') == 'True'

if USE_S3:
    # AWS/DO Spaces settings
    AWS_ACCESS_KEY_ID = os.getenv('AWS_ACCESS_KEY_ID')
    AWS_SECRET_ACCESS_KEY = os.getenv('AWS_SECRET_ACCESS_KEY')
    AWS_STORAGE_BUCKET_NAME = os.getenv('AWS_STORAGE_BUCKET_NAME')
    AWS_S3_ENDPOINT_URL = os.getenv('AWS_S3_ENDPOINT_URL')
    AWS_S3_REGION_NAME = os.getenv('AWS_S3_REGION_NAME', 'sfo3')
    AWS_S3_CUSTOM_DOMAIN = os.getenv('AWS_S3_CUSTOM_DOMAIN')
    AWS_DEFAULT_ACL = os.getenv('AWS_DEFAULT_ACL', 'public-read')
    AWS_S3_OBJECT_PARAMETERS = {
        'CacheControl': 'max-age=86400',
    }
    AWS_QUERYSTRING_AUTH = False  # Don't add auth to public URLs
    AWS_S3_FILE_OVERWRITE = True  # For static files
    AWS_S3_SIGNATURE_VERSION = 's3v4'
    
    # Static files configuration
    STATICFILES_STORAGE = 'fend.storage_backends.StaticStorage'
    STATIC_URL = f'{AWS_S3_ENDPOINT_URL}/{AWS_STORAGE_BUCKET_NAME}/static/'
    
    # Media files configuration
    DEFAULT_FILE_STORAGE = 'fend.storage_backends.PublicMediaStorage'
    MEDIA_URL = f'{AWS_S3_ENDPOINT_URL}/{AWS_STORAGE_BUCKET_NAME}/media/'
    
    # Use CDN domain if provided
    if AWS_S3_CUSTOM_DOMAIN:
        STATIC_URL = f'https://{AWS_S3_CUSTOM_DOMAIN}/static/'
        MEDIA_URL = f'https://{AWS_S3_CUSTOM_DOMAIN}/media/'