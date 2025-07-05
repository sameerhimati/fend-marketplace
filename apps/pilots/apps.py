from django.apps import AppConfig


class PilotsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.pilots'
    verbose_name = 'Pilots'
    
    def ready(self):
        import apps.pilots.signals
