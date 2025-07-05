from storages.backends.s3boto3 import S3Boto3Storage


class StaticStorage(S3Boto3Storage):
    """Storage backend for static files"""
    location = 'static'
    default_acl = 'public-read'
    file_overwrite = True
    custom_domain = False  # Use endpoint URL for static files


class PublicMediaStorage(S3Boto3Storage):
    """Storage backend for public media files"""
    location = 'media'
    default_acl = 'public-read'
    file_overwrite = False
    custom_domain = False  # Use endpoint URL for media files
    querystring_auth = False  # Don't require authentication for public files
    
    def get_object_parameters(self, name):
        """Set cache control headers for media files"""
        params = super().get_object_parameters(name)
        # Ensure ACL is set for each file
        params['ACL'] = 'public-read'
        
        # Different cache times for different file types
        if name.endswith(('.jpg', '.jpeg', '.png', '.gif', '.webp')):
            params['CacheControl'] = 'max-age=2592000'  # 30 days for images
        elif name.endswith('.pdf'):
            params['CacheControl'] = 'max-age=604800'  # 7 days for PDFs
        else:
            params['CacheControl'] = 'max-age=86400'  # 1 day for other files
        return params


class OrganizationLogoStorage(S3Boto3Storage):
    """Storage backend specifically for organization logos"""
    location = 'media/logos'
    default_acl = 'public-read'
    file_overwrite = False
    custom_domain = False
    querystring_auth = False  # Don't require authentication for public files
    
    def get_object_parameters(self, name):
        params = super().get_object_parameters(name)
        params['ACL'] = 'public-read'  # Ensure ACL is set for each file
        params['CacheControl'] = 'max-age=2592000'  # 30 days for logos
        return params


class PilotDocumentStorage(S3Boto3Storage):
    """Storage backend for pilot documents (PDFs, specs, etc.)"""
    location = 'media/documents'
    default_acl = 'public-read'
    file_overwrite = False
    custom_domain = False
    querystring_auth = False  # Don't require authentication for public files
    
    def get_object_parameters(self, name):
        params = super().get_object_parameters(name)
        params['ACL'] = 'public-read'  # Ensure ACL is set for each file
        params['CacheControl'] = 'max-age=604800'  # 7 days for documents
        return params


# Callable classes to replace lambda functions
class PilotDocumentStorageCallable:
    def __call__(self):
        return PilotDocumentStorage()


class OrganizationLogoStorageCallable:
    def __call__(self):
        return OrganizationLogoStorage()