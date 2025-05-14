from .base import *

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

# Allow CSRF protection to work with HTTPS
CSRF_TRUSTED_ORIGINS = ['https://marketplace.fend.ai']