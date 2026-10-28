"""
Django settings for smartcare_project project.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# Load .env if present
load_dotenv(BASE_DIR / '.env')

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = os.getenv('DJANGO_SECRET_KEY', 'django-insecure-smartcare-healthcare-app-key-2026')

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = os.getenv('DJANGO_DEBUG', 'True') == 'True'

ALLOWED_HOSTS = ['*']


# Application definition

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',

    # SmartCare Apps
    'core.apps.CoreConfig',
    'appointments.apps.AppointmentsConfig',
    'emergency.apps.EmergencyConfig',
    'routing.apps.RoutingConfig',
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

ROOT_URLCONF = 'smartcare_project.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'core.context_processors.smartcare_global_context',
            ],
        },
    },
]

WSGI_APPLICATION = 'smartcare_project.wsgi.application'


# Database
# https://docs.djangoproject.com/en/6.1/ref/settings/#databases

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}

# Custom User Model
AUTH_USER_MODEL = 'core.User'

# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
        'OPTIONS': {
            'min_length': 6,
        }
    },
]


# Internationalization
LANGUAGE_CODE = 'en-us'
TIME_ZONE = os.getenv('HOSPITAL_TIMEZONE', 'Asia/Kolkata')
USE_I18N = True
USE_TZ = True


# Static files (CSS, JavaScript, Images)
STATIC_URL = '/static/'
STATICFILES_DIRS = [
    BASE_DIR / 'static',
]
STATIC_ROOT = BASE_DIR / 'staticfiles'

# Authentication URLs
LOGIN_URL = 'login'
LOGIN_REDIRECT_URL = 'dashboard_redirect'
LOGOUT_REDIRECT_URL = 'home'

# Default primary key field type
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# SmartCare Routing & Geo Configuration
ROUTING_PROVIDER = os.getenv('ROUTING_PROVIDER', 'simulation')  # 'simulation', 'google', 'mapbox'
GOOGLE_MAPS_API_KEY = os.getenv('GOOGLE_MAPS_API_KEY', '')
MAPBOX_API_KEY = os.getenv('MAPBOX_API_KEY', '')
DEFAULT_SAFETY_BUFFER_MINUTES = int(os.getenv('DEFAULT_SAFETY_BUFFER_MINUTES', '15'))
DEFAULT_HOSPITAL_NAME = os.getenv('DEFAULT_HOSPITAL_NAME', 'SmartCare Central Hospital')
DEFAULT_HOSPITAL_ADDRESS = os.getenv('DEFAULT_HOSPITAL_ADDRESS', '100 Healthcare Blvd, Metro City')
DEFAULT_HOSPITAL_LAT = float(os.getenv('DEFAULT_HOSPITAL_LAT', '12.971598'))
DEFAULT_HOSPITAL_LNG = float(os.getenv('DEFAULT_HOSPITAL_LNG', '77.594562'))
HOSPITAL_EMERGENCY_PHONE = os.getenv('HOSPITAL_EMERGENCY_PHONE', '+1 (555) 911-CARE')
HOSPITAL_EMERGENCY_DEPARTMENT = os.getenv('HOSPITAL_EMERGENCY_DEPARTMENT', 'SmartCare Emergency & Trauma Pavilion, Gate 2')
