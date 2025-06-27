from django.conf import settings
from django.core.files.storage import default_storage


def get_logo_storage():
    """Returns the appropriate storage backend for organization logos"""
    if hasattr(settings, 'USE_S3') and settings.USE_S3:
        from fend.storage_backends import OrganizationLogoStorage
        return OrganizationLogoStorage()
    return default_storage