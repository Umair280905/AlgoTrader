from decouple import config
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = config('SECRET_KEY', default='django-insecure-change-me-in-production')
DEBUG = config('DEBUG', default=True, cast=bool)
ALLOWED_HOSTS = config('ALLOWED_HOSTS', default='localhost,127.0.0.1').split(',')

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'rest_framework',
    'corsheaders',
    'django_celery_beat',
    'trading',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'corsheaders.middleware.CorsMiddleware',
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
        'DIRS': [BASE_DIR / 'dashboard' / 'templates'],
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

WSGI_APPLICATION = 'config.wsgi.application'

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': config('DB_NAME', default='algo_trader'),
        'USER': config('DB_USER', default='postgres'),
        'PASSWORD': config('DB_PASSWORD', default=''),
        'HOST': config('DB_HOST', default='localhost'),
        'PORT': config('DB_PORT', default='5432'),
    }
}

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'Asia/Kolkata'
USE_I18N = True
USE_TZ = True

STATIC_URL = '/static/'
STATICFILES_DIRS = [BASE_DIR / 'dashboard' / 'static']
STATIC_ROOT = BASE_DIR / 'staticfiles'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# ── Celery ────────────────────────────────────────────────────────────────────
CELERY_BROKER_URL = config('CELERY_BROKER_URL', default='redis://localhost:6379/0')
CELERY_RESULT_BACKEND = config('CELERY_RESULT_BACKEND', default='redis://localhost:6379/0')
CELERY_TIMEZONE = 'Asia/Kolkata'
CELERY_BEAT_SCHEDULER = 'django_celery_beat.schedulers:DatabaseScheduler'

# ── Kotak Neo Broker API (v2) ─────────────────────────────────────────────────
KOTAK_CONSUMER_KEY = config('KOTAK_CONSUMER_KEY', default='')
KOTAK_NEO_FIN_KEY  = config('KOTAK_NEO_FIN_KEY', default='')
KOTAK_ACCESS_TOKEN = config('KOTAK_ACCESS_TOKEN', default='')
KOTAK_MOBILE       = config('KOTAK_MOBILE', default='')
KOTAK_UCC          = config('KOTAK_UCC', default='')
KOTAK_MPIN         = config('KOTAK_MPIN', default='')

# ── Telegram ──────────────────────────────────────────────────────────────────
TELEGRAM_BOT_TOKEN = config('TELEGRAM_BOT_TOKEN', default='')
TELEGRAM_CHAT_ID = config('TELEGRAM_CHAT_ID', default='')

# ── Trading Engine ────────────────────────────────────────────────────────────
PAPER_TRADING = config('PAPER_TRADING', default=True, cast=bool)
PHASE = config('PHASE', default=1, cast=int)
MAX_DAILY_LOSS_INR = config('MAX_DAILY_LOSS_INR', default=500, cast=int)
MAX_OPEN_POSITIONS = config('MAX_OPEN_POSITIONS', default=3, cast=int)
MAX_PER_STRATEGY = config('MAX_PER_STRATEGY', default=1, cast=int)
RISK_PER_TRADE_PCT = config('RISK_PER_TRADE_PCT', default=0.01, cast=float)
MINIMUM_CASH_BUFFER = config('MINIMUM_CASH_BUFFER', default=10000, cast=int)

CORS_ALLOWED_ORIGINS = [
    'http://localhost:8000',
    'http://127.0.0.1:8000',
]

REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework.authentication.SessionAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
}

# import os
# ANTHROPIC_API_KEY = os.environ.get('ANTHROPIC_API_KEY', '')
# AI_MIN_CONFIDENCE = config('AI_MIN_CONFIDENCE', default=60, cast=int)
# AI_ENABLED = config('AI_ENABLED', default=False, cast=bool)

# from decouple import config as decouple_config
# ANTHROPIC_API_KEY = decouple_config('ANTHROPIC_API_KEY', default='')
# AI_MIN_CONFIDENCE = decouple_config('AI_MIN_CONFIDENCE', default=60, cast=int)
# AI_ENABLED = decouple_config('AI_ENABLED', default=False, cast=bool)


# ── Agentic AI ────────────────────────────────────────────────────────────────
# ANTHROPIC_API_KEY = config('ANTHROPIC_API_KEY', default='')
# AI_MIN_CONFIDENCE = config('AI_MIN_CONFIDENCE', default=60, cast=int)
# AI_ENABLED = config('AI_ENABLED', default=False, cast=bool)





# # ── Agentic AI ────────────────────────────────────────────────────────────────
# import os
# ANTHROPIC_API_KEY = os.environ.get('ANTHROPIC_API_KEY', '')
# AI_MIN_CONFIDENCE = config('AI_MIN_CONFIDENCE', default=60, cast=int)
# AI_ENABLED = config('AI_ENABLED', default=False, cast=bool)

# ── Agentic AI ────────────────────────────────────────────────────────────────
ANTHROPIC_API_KEY = config('ANTHROPIC_API_KEY', default='')
AI_MIN_CONFIDENCE = config('AI_MIN_CONFIDENCE', default=60, cast=int)
AI_ENABLED = config('AI_ENABLED', default=False, cast=bool)