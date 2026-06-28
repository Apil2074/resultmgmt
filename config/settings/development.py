from .base import *

DEBUG = True

# Development-specific settings
INTERNAL_IPS = ['127.0.0.1']

# Use SQLite for local development — no PostgreSQL server needed
# Switch to PostgreSQL by commenting this out and configuring DB_* env vars
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}

EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'

CORS_ALLOW_ALL_ORIGINS = True
