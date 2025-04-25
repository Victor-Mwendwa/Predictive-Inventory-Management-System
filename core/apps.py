from django.apps import AppConfig

class CoreConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'core'
    
    def ready(self):
        """
        Method called when the app is ready, used for signal registration
        and other startup code.
        """
        # Import signals to ensure they're registered
        from . import signals  # noqa
        
        # Import and register admin customizations
        from .admin import admin  # noqa
        
        # Import tasks if using Celery or other task queues
        try:
            from . import tasks  # noqa
        except ImportError:
            pass