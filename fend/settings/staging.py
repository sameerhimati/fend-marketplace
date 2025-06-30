from .base import *
import os

# Staging environment - mirrors production but runs locally
DEBUG = False  # Keep False to test production-like behavior

# Local staging hosts
ALLOWED_HOSTS = ['localhost', '127.0.0.1', '0.0.0.0']

# Staging Database
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': 'fend_staging_db',
        'USER': 'postgres',
        'PASSWORD': 'postgres',
        'HOST': 'db',  # Docker service name
        'PORT': '5432',
    }
}

# Static/Media files (local filesystem for staging)
STATIC_URL = '/static/'
STATIC_ROOT = '/app/staticfiles'

MEDIA_URL = '/media/'
MEDIA_ROOT = '/app/media'

# Don't use S3 in staging
USE_S3 = False
DEFAULT_FILE_STORAGE = 'django.core.files.storage.FileSystemStorage'
STATICFILES_STORAGE = 'django.contrib.staticfiles.storage.StaticFilesStorage'

# Staging-specific logging
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'file': {
            'level': 'ERROR',
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': '/app/logs/staging_errors.log',
            'maxBytes': 1024 * 1024 * 5,  # 5MB
            'backupCount': 3,
            'formatter': 'verbose',
        },
        'console': {
            'level': 'INFO',
            'class': 'logging.StreamHandler',
            'formatter': 'verbose',
        },
    },
    'root': {
        'handlers': ['console', 'file'],
        'level': 'INFO',
    },
    'loggers': {
        'django': {
            'handlers': ['console', 'file'],
            'level': 'INFO',
            'propagate': False,
        },
    },
}

# Security settings (relaxed for staging)
SECURE_SSL_REDIRECT = False
SESSION_COOKIE_SECURE = False
CSRF_COOKIE_SECURE = False

# Email backend for staging (console output)
EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'

# Stripe test keys (same as development)
STRIPE_PUBLISHABLE_KEY = os.getenv('STRIPE_TEST_PUBLISHABLE_KEY', '')
STRIPE_SECRET_KEY = os.getenv('STRIPE_TEST_SECRET_KEY', '')
STRIPE_WEBHOOK_SECRET = os.getenv('STRIPE_TEST_WEBHOOK_SECRET', '')

print("🚀 Running in STAGING mode")
print(f"📊 Database: {DATABASES['default']['NAME']}")
print(f"🔧 Debug: {DEBUG}")
print(f"📁 Static files: {STATIC_URL}")
print(f"📧 Email backend: {EMAIL_BACKEND}")