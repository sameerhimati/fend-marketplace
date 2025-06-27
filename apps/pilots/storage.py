from django.conf import settings
from django.core.files.storage import default_storage


def get_pilot_document_storage():
    """Returns the appropriate storage backend for pilot documents"""
    if hasattr(settings, 'USE_S3') and settings.USE_S3:
        from fend.storage_backends import PilotDocumentStorage
        return PilotDocumentStorage()
    return default_storage