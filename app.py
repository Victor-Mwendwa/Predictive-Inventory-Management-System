#!/usr/bin/env python
"""
WSGI config for Kyosk Inventory Management System.

It exposes the WSGI callable as a module-level variable named ``application``.
"""

import os
from django.core.wsgi import get_wsgi_application
from whitenoise import WhiteNoise
from pathlib import Path

# Set the default Django settings module
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

# Get the WSGI application
django_app = get_wsgi_application()

# Initialize WhiteNoise for static files
BASE_DIR = Path(__file__).resolve().parent.parent
application = WhiteNoise(
    django_app,
    root=os.path.join(BASE_DIR, 'static'),
    prefix='static/',
)

# Optional: Add additional directories for WhiteNoise to serve
application.add_files(os.path.join(BASE_DIR, 'media'), prefix='media/')

# Initialize Celery
from config.celery import app as celery_app
__all__ = ['celery_app']

def initialize_application():
    """Perform application initialization tasks."""
    from django.conf import settings
    from django.core.management import call_command
    
    # Run startup checks in production
    if not settings.DEBUG:
        print("Running production startup checks...")
        
        # Ensure database is migrated
        call_command('migrate', interactive=False)
        
        # Collect static files
        if not os.path.exists(os.path.join(settings.STATIC_ROOT)):
            call_command('collectstatic', interactive=False)
        
        # Generate initial forecasts if none exist
        from core.models import DemandForecast
        if not DemandForecast.objects.exists():
            print("Generating initial demand forecasts...")
            call_command('generate_forecasts')

# Run initialization when the app starts
initialize_application()