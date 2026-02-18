import os
from pathlib import Path
from django.core.exceptions import ImproperlyConfigured

BASE_DIR = Path(__file__).resolve().parent.parent

def get_env_var(name, default=None, required=False):
    val = os.environ.get(name, default)
    if required and not val:
        raise ImproperlyConfigured(f"Set the {name} environment variable")
    return val

# SECURITY
SECRET_KEY = get_env_var('DJANGO_SECRET_KEY', 'replace-me-with-a-secure-key')

# DEBUG should be False in production
DEBUG = get_env_var('DJANGO_DEBUG', 'True') == 'True'

ALLOWED_HOSTS = get_env_var('DJANGO_ALLOWED_HOSTS', '').split(',') if get_env_var('DJANGO_ALLOWED_HOSTS') else []

# If running behind a reverse proxy (nginx) that terminates TLS, tell Django
# to trust the X-Forwarded-Proto header so request.is_secure() works.
# Configure trusted CSRF origins (must include scheme, e.g. https://quiz.nvolkv.ru)
# and cookie/security flags via environment variables when deploying to prod.
CSRF_TRUSTED_ORIGINS = [s.strip() for s in get_env_var('DJANGO_CSRF_TRUSTED_ORIGINS', 'https://quiz.nvolkv.ru').split(',') if s.strip()]
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')

# Ensure secure cookies under HTTPS (can be overridden via env vars)
CSRF_COOKIE_SECURE = get_env_var('DJANGO_CSRF_COOKIE_SECURE', 'True') == 'True'
SESSION_COOKIE_SECURE = get_env_var('DJANGO_SESSION_COOKIE_SECURE', 'True') == 'True'


INSTALLED_APPS = [
    'channels',
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'quiz',
    'admin_panel',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'quiz_platform.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
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

WSGI_APPLICATION = 'quiz_platform.wsgi.application'

ASGI_APPLICATION = 'quiz_platform.asgi.application'

# CHANNEL_LAYERS - use Redis in production if REDIS_URL provided, otherwise in-memory
REDIS_URL = get_env_var('REDIS_URL', '')
if REDIS_URL:
    CHANNEL_LAYERS = {
        'default': {
            'BACKEND': 'channels_redis.core.RedisChannelLayer',
            'CONFIG': {'hosts': [REDIS_URL]},
        },
    }
else:
    CHANNEL_LAYERS = {
        'default': {'BACKEND': 'channels.layers.InMemoryChannelLayer'},
    }

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}

AUTH_PASSWORD_VALIDATORS = []

LANGUAGE_CODE = 'ru-ru'

TIME_ZONE = 'UTC'

USE_I18N = True
USE_L10N = True
USE_TZ = True

STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'

# Additional static files dirs (optional)
STATICFILES_DIRS = [
    BASE_DIR / 'static',
]

# Use WhiteNoise storage in production for compressed files
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'
