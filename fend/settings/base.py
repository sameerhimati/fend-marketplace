from pathlib import Path
import os
import sys
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent.parent

sys.path.append(str(BASE_DIR))

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = os.getenv('SECRET_KEY', 'django-insecure-development-key')

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = os.getenv('DEBUG', 'True') == 'True'

ALLOWED_HOSTS = []

# CSRF Settings
CSRF_COOKIE_NAME = 'csrftoken'
CSRF_HEADER_NAME = 'HTTP_X_CSRFTOKEN'
CSRF_COOKIE_HTTPONLY = False  # Allow JavaScript to read the cookie if needed
CSRF_USE_SESSIONS = False  # Use cookies instead of sessions for CSRF

# Custom user model
AUTH_USER_MODEL = 'users.User'

LOGIN_URL = 'organizations:login'
LOGIN_REDIRECT_URL = 'organizations:dashboard'
LOGOUT_URL = 'organizations:logout'
LOGOUT_REDIRECT_URL = 'landing'

SESSION_ENGINE = 'django.contrib.sessions.backends.db'
SESSION_COOKIE_AGE = 86400  # 24 hours in seconds
SESSION_EXPIRE_AT_BROWSER_CLOSE = True

STRIPE_PUBLISHABLE_KEY = os.getenv('STRIPE_PUBLISHABLE_KEY', '')
STRIPE_SECRET_KEY = os.getenv('STRIPE_SECRET_KEY', '')
STRIPE_WEBHOOK_SECRET = os.getenv('STRIPE_WEBHOOK_SECRET', '')

# Sentry Configuration
SENTRY_DSN = os.getenv('SENTRY_DSN', '')

# Application definition
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    
    # Third party apps
    'storages',
    
    # Local apps
    'apps.organizations',
    'apps.pilots',
    'apps.users',
    'apps.notifications',
    'apps.payments',
    'apps.recommendations',
    'apps.utils',
]

# These middleware classes are required for Django to work properly
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'fend.https_middleware.HttpsRedirectMiddleware',
    'apps.payments.middleware.SubscriptionRequiredMiddleware',
    'fend.middleware.AuthenticationFlowMiddleware',
]

ROOT_URLCONF = 'fend.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'apps.payments.context_processors.stripe_key',
                'django.contrib.messages.context_processors.messages',
                'apps.payments.context_processors.payment_stats',
                'apps.payments.context_processors.subscription_warnings',
                'apps.organizations.context_processors.onboarding_suggestions',
            ],
        },
    },
]

WSGI_APPLICATION = 'fend.wsgi.application'

# Database
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': os.getenv('DB_NAME', 'fend_db'),
        'USER': os.getenv('DB_USER', 'postgres'),
        'PASSWORD': os.getenv('DB_PASSWORD', 'postgres'),
        'HOST': os.getenv('DB_HOST', 'localhost'),
        'PORT': os.getenv('DB_PORT', '5432'),
    }
}

# Password validation - keeping basic validation
AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
        'OPTIONS': {
            'min_length': 8,
        }
    },
]

# Internationalization
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True

# Static files (CSS, JavaScript, Images)
STATIC_URL = 'static/'
STATICFILES_DIRS = [BASE_DIR / 'static']
STATIC_ROOT = BASE_DIR / 'staticfiles'

# Media files
MEDIA_URL = 'media/'
MEDIA_ROOT = BASE_DIR / 'media'

DEFAULT_FILE_STORAGE = 'django.core.files.storage.FileSystemStorage'

# File upload settings
FILE_UPLOAD_MAX_MEMORY_SIZE = 10 * 1024 * 1024  # 10 MB
DATA_UPLOAD_MAX_MEMORY_SIZE = 10 * 1024 * 1024  # 10 MB
MAX_UPLOAD_SIZE = 10 * 1024 * 1024  # 10 MB (used in forms)

# Default primary key field type
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Simple logging configuration
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
        },
    },
    'root': {
        'handlers': ['console'],
        'level': 'INFO',
    },
}

# Email configuration
# EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
# EMAIL_HOST = 'smtp.sendgrid.net'
# EMAIL_PORT = 587
# EMAIL_USE_TLS = True
# EMAIL_HOST_USER = 'apikey'  # This must always be 'apikey' for SendGrid
# EMAIL_HOST_PASSWORD = os.getenv('SENDGRID_API_KEY', '')
# DEFAULT_FROM_EMAIL = os.getenv('DEFAULT_FROM_EMAIL', 'noreply@thefend.com')
# ADMIN_EMAIL = os.getenv('ADMIN_EMAIL', 'admin@thefend.com')

# # For development, use console backend if no SendGrid key
# if not EMAIL_HOST_PASSWORD and DEBUG:
#     EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'

def ready():
    """Initialize admin customization after Django is fully loaded."""
    try:
        from fend.admin_customization import initialize_admin_customization
        initialize_admin_customization()
    except ImportError:
        pass

import django
from django.conf import settings
if settings.configured:
    ready()