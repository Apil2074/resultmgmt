from .base import *

DEBUG = True

# Development-specific settings
INTERNAL_IPS = ['127.0.0.1']

# Use SQLite for local development — no PostgreSQL server needed
# Switch to PostgreSQL by commenting this out and configuring DB_* env vars
# DATABASES = {
#     'default': {
#         'ENGINE': 'django.db.backends.sqlite3',
#         'NAME': BASE_DIR / 'db.sqlite3',
#         'OPTIONS': {
#             'timeout': 20,
#         }
#     }
# }

if config('EMAIL_HOST_USER', default=''):
    EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
else:
    EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'

# SECURITY: CORS is explicitly restricted even in dev.
# Add localhost origins to CORS_ALLOWED_ORIGINS in base.py; do NOT use CORS_ALLOW_ALL_ORIGINS.
CORS_ALLOWED_ORIGINS = [
    'http://localhost:8000',
    'http://127.0.0.1:8000',
    'http://localhost:3000',   # React/Vite dev server if applicable
]

CSRF_TRUSTED_ORIGINS = [
    'http://localhost:8000',
    'http://127.0.0.1:8000',
]
