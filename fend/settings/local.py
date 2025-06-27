# fend/settings/local.py
from .base import *

DEBUG = True

# Add reverse HTTPS redirect for local development
MIDDLEWARE = [
    'fend.local_http_middleware.LocalHttpRedirectMiddleware',  # Redirect HTTPS to HTTP
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    # 'fend.https_middleware.HttpsRedirectMiddleware',  # Disabled for local dev
    'apps.payments.middleware.SubscriptionRequiredMiddleware',
    'fend.middleware.AuthenticationFlowMiddleware',
]

# Add django-debug-toolbar settings (commented out to disable sidebar)
# INSTALLED_APPS += ['debug_toolbar']
# MIDDLEWARE += ['debug_toolbar.middleware.DebugToolbarMiddleware']
# INTERNAL_IPS = ['127.0.0.1']

# Email settings for development
EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'