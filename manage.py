"""Django's command-line utility for administrative tasks."""
import os
import sys
from django.core.management import execute_from_command_line


def main():
    """Run administrative tasks."""
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "Couldn't import Django. Are you sure it's installed and "
            "available on your PYTHONPATH environment variable? Did you "
            "forget to activate a virtual environment?"
        ) from exc

    # Pre-startup for runserver
    if len(sys.argv) > 1 and sys.argv[1] == 'runserver':
        from django.conf import settings
        from django.core.management import call_command
        from django.db.utils import OperationalError

        print("Running pre-startup checks...")

        # Ensure data directory exists
        data_dir = os.path.join(settings.BASE_DIR, 'data')
        if not os.path.exists(data_dir):
            os.makedirs(data_dir)
            print(f"Created data directory at {data_dir}")

        # Apply all outstanding migrations
        try:
            print("Applying database migrations...")
            call_command('migrate', interactive=False)
        except Exception as e:
            print(f"Error applying migrations: {e}")

        # Populate sample data if command available
        try:
            print("Creating sample data...")
            call_command('populate_sample_data')
        except Exception:
            # If command not defined or errors, skip
            pass

        # Ensure ML models directory exists
        ml_models_dir = os.path.join(settings.BASE_DIR, 'data', 'ml_models')
        if not os.path.exists(ml_models_dir):
            os.makedirs(ml_models_dir)
            print(f"Created ML models directory at {ml_models_dir}")

        # Generate initial forecasts if none exist
        try:
            from core.models import DemandForecast
            exists = False
            try:
                exists = DemandForecast.objects.exists()
            except OperationalError:
                # Table doesn't exist yet
                exists = False
            if not exists:
                print("No forecasts found or table missing. Generating initial forecasts...")
                call_command('generate_forecasts')
        except Exception:
            # Skip if models not ready
            pass

    execute_from_command_line(sys.argv)


if __name__ == '__main__':
    main()
