import os
from pathlib import Path
from celery.schedules import crontab
from pymongo import MongoClient

CELERY_BEAT_SCHEDULE = {
    'daily-maintenance': {
        'task': 'tasks.daily_maintenance',
        'schedule': crontab(hour=2, minute=0),  # Runs at 2am daily
    },
}

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = 'your-secret-key-here'

DEBUG = True

ALLOWED_HOSTS = ['127.0.0.1']

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'core',
    'rest_framework',
    'rest_framework.authtoken',
    'api',
    'config',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'config.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [
            os.path.join(BASE_DIR, 'templates'),  # If you have a global templates directory
            os.path.join(BASE_DIR, 'core', 'templates'),  # Path to core app's templates
        ],
        'APP_DIRS': True,  # This is important for Django to look in each app's 'templates' folder
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'

# MongoDB Settings
# MONGO_URI = 'mongodb://localhost:27017/'
# MONGO_DB_NAME = 'kyoskdata'
# DATABASES = {
#     'default': {
#         'ENGINE': 'djongo',
#         'NAME': 'kyoskdata',
#         'CLIENT': {
#             'host': 'mongodb+srv://viktormwendwan:92yQv8ufd5oVCOrK@cluster0.kipgroq.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0',
#             'username': 'viktormwendwan',
#             'password': '92yQv8ufd5oVCOrK',
#         }
#     }
# }

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',  # Django's own tables go here: users, sessions, admin...
    }
}

# MongoDB Settings
# MongoDB Settings
MONGO_USERNAME = 'root'
MONGO_PASSWORD = 'password'
MONGO_HOST = 'localhost'
MONGO_PORT = 27017

MONGO_DB_NAME = 'kyosk'

# Build the full URI
MONGO_URI = f"mongodb://{MONGO_USERNAME}:{MONGO_PASSWORD}@{MONGO_HOST}:{MONGO_PORT}/"



AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]

LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True

# Celery Configuration
CELERY_BROKER_URL = 'redis://localhost:6379/0'
CELERY_RESULT_BACKEND = 'redis://localhost:6379/0'
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_TIMEZONE = 'Africa/Nairobi'

STATIC_URL = 'static/'
STATICFILES_DIRS = [os.path.join(BASE_DIR, 'static')]

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

LOGIN_REDIRECT_URL = 'dashboard'
LOGOUT_REDIRECT_URL = 'login'

# Create data directory if it doesn't exist
DATA_DIR = os.path.join(BASE_DIR, 'data')
os.makedirs(DATA_DIR, exist_ok=True)

# Redirect users here if they try to hit a login_required view
LOGIN_URL = '/login/'

# After successful login send them here
LOGIN_REDIRECT_URL = '/'

# After logout send them here
LOGOUT_REDIRECT_URL = '/login/'

STATIC_URL = '/static/'

# Tell Django where your “source” static files live:
STATICFILES_DIRS = [
    BASE_DIR / 'static',      # PROJECT_ROOT/static/css/…
]

# Tell Django where to “collect” them for deployment/serving:
STATIC_ROOT = BASE_DIR / 'staticfiles'