# Django settings for ca project.

import json
import os
import sys

import packaging.version

import cryptography
from cryptography import x509

import django
from django.core.exceptions import ImproperlyConfigured

# Build paths inside the project like this: os.path.join(BASE_DIR, ...)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ROOT_DIR = os.path.dirname(BASE_DIR)

DEBUG = False

ADMINS = (
    # ('Your Name', 'your_email@example.com'),
)


DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': ':memory:',
    },
}

# Hosts/domain names that are valid for this site; required if DEBUG is False
# See https://docs.djangoproject.com/en/1.5/ref/settings/#allowed-hosts
ALLOWED_HOSTS = []

# Local time zone for this installation. Choices can be found here:
# http://en.wikipedia.org/wiki/List_of_tz_zones_by_name
# although not all choices may be available on all operating systems.
# In a Windows environment this must be set to your system time zone.
TIME_ZONE = 'Etc/UTC'

# Language code for this installation. All choices can be found here:
# http://www.i18nguy.com/unicode/language-identifiers.html
LANGUAGE_CODE = 'en-us'

# If you set this to False, Django will make some optimizations so as not
# to load the internationalization machinery.
USE_I18N = True

# If you set this to False, Django will not format dates, numbers and
# calendars according to the current locale.
USE_L10N = True

# If you set this to False, Django will not use timezone-aware datetimes.
USE_TZ = False

# Absolute filesystem path to the directory that will hold user-uploaded files.
# Example: "/var/www/example.com/media/"
MEDIA_ROOT = ''

# URL that handles the media served from MEDIA_ROOT. Make sure to use a
# trailing slash.
# Examples: "http://example.com/media/", "http://media.example.com/"
MEDIA_URL = ''

# Absolute path to the directory static files should be collected to.
# Don't put anything in this directory yourself; store your static files
# in apps' "static/" subdirectories and in STATICFILES_DIRS.
# Example: "/var/www/example.com/static/"
STATIC_ROOT = ''

# URL prefix for static files.
# Example: "http://example.com/static/", "http://static.example.com/"
STATIC_URL = '/static/'

# Additional locations of static files
STATICFILES_DIRS = (
    # Put strings here, like "/home/html/static" or "C:/www/django/static".
    # Always use forward slashes, even on Windows.
    # Don't forget to use absolute paths, not relative paths.
)

# List of finder classes that know how to find static files in
# various locations.
STATICFILES_FINDERS = (
    'django.contrib.staticfiles.finders.FileSystemFinder',
    'django.contrib.staticfiles.finders.AppDirectoriesFinder',
    # 'django.contrib.staticfiles.finders.DefaultStorageFinder',
)

# Speeds up tests that create a Django user
PASSWORD_HASHERS = [
    'django.contrib.auth.hashers.MD5PasswordHasher',
]

# Make this unique, and don't share it with anybody.
SECRET_KEY = 'fake-key'
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
]

ROOT_URLCONF = 'ca.urls'

# Python dotted path to the WSGI application used by Django's runserver.
WSGI_APPLICATION = 'ca.wsgi.application'

INSTALLED_APPS = (
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.admin',
    # Uncomment the next line to enable admin documentation:
    # 'django.contrib.admindocs',
    'django_object_actions',

    'django_ca',
)

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'debug': True,
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

# A sample logging configuration. The only tangible logging
# performed by this configuration is to send an email to
# the site admins on every HTTP 500 error when DEBUG=False.
# See http://docs.djangoproject.com/en/dev/topics/logging for
# more details on how to customize your logging configuration.
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'filters': {
        'require_debug_false': {
            '()': 'django.utils.log.RequireDebugFalse'
        }
    },
    'handlers': {
        'console': {
            'class': 'logging.NullHandler',
            #'class': 'logging.StreamHandler',
        },
        'mail_admins': {
            'level': 'ERROR',
            'filters': ['require_debug_false'],
            'class': 'django.utils.log.AdminEmailHandler'
        }
    },
    'loggers': {
        'django.request': {
            'handlers': ['mail_admins'],
            'level': 'ERROR',
            'propagate': True,
        },
        'django_ca': {
            'handlers': ['console'],
            'level': 'INFO',
        },
    }
}

# Fixture data used by test cases
FIXTURES_DIR = os.path.join(BASE_DIR, 'django_ca', 'tests', 'fixtures')
with open(os.path.join(FIXTURES_DIR, 'cert-data.json')) as stream:
    _fixture_data = json.load(stream)

# Custom settings
CA_DEFAULT_SUBJECT = {
    'C': 'AT',
    'ST': 'Vienna',
    'L': 'Vienna',
    'O': 'Django CA',
    'OU': 'Django CA Testsuite',
}
CA_MIN_KEY_SIZE = 1024
CA_DEFAULT_KEY_SIZE = 1024

# Default expiry is 100 days, note that pre-generated CAs have lifetime of only 365 days
CA_DEFAULT_EXPIRES = 100

# should be something that doesn't exist, so make sure we use a decorator everywhere
CA_DIR = '/non/existent'

# WARNING: do not set to testserver, as URLValidator does not consider it a valid hostname
CA_DEFAULT_HOSTNAME = 'localhost:8000'

# TODO: get serial and paths from fixture data
CA_OCSP_URLS = {
    'root': {
        'ca': _fixture_data['certs']['root']['serial'],
        'responder_key': _fixture_data['certs']['profile-ocsp']['key_filename'],
        'responder_cert': _fixture_data['certs']['profile-ocsp']['pub_filename'],
    },
    'child': {
        'ca': _fixture_data['certs']['child']['serial'],
        'responder_key': _fixture_data['certs']['profile-ocsp']['key_filename'],
        'responder_cert': _fixture_data['certs']['profile-ocsp']['pub_filename'],
    },
    'ecc': {
        'ca': _fixture_data['certs']['ecc']['serial'],
        'responder_key': _fixture_data['certs']['profile-ocsp']['key_filename'],
        'responder_cert': _fixture_data['certs']['profile-ocsp']['pub_filename'],
    },
    'dsa': {
        'ca': _fixture_data['certs']['dsa']['serial'],
        'responder_key': _fixture_data['certs']['profile-ocsp']['key_filename'],
        'responder_cert': _fixture_data['certs']['profile-ocsp']['pub_filename'],
    },
    'pwd': {
        'ca': _fixture_data['certs']['pwd']['serial'],
        'responder_key': _fixture_data['certs']['profile-ocsp']['key_filename'],
        'responder_cert': _fixture_data['certs']['profile-ocsp']['pub_filename'],
    },
}

CRYPTOGRAPHY_VERSION = packaging.version.parse(cryptography.__version__).release[:2]
NEWEST_PYTHON = sys.version_info[0:2] == (3, 7)
NEWEST_CRYPTOGRAPHY = CRYPTOGRAPHY_VERSION == (2, 7)
NEWEST_DJANGO = django.VERSION[:2] == (2, 2)
NEWEST_VERSIONS = NEWEST_PYTHON and NEWEST_CRYPTOGRAPHY and NEWEST_DJANGO

# PrecertPoison does not compare as equal until cryptography 2.7:
#   https://github.com/pyca/cryptography/issues/4818
SKIP_PRECERT_POISON = not (
    hasattr(x509, 'PrecertPoison') and x509.PrecertPoison() == x509.PrecertPoison()
)  # pragma: only cryptography<2.7

# OCSPNoCheck does not compare as equal until cryptography 2.7:
#   https://github.com/pyca/cryptography/issues/4818
SKIP_OCSP_NOCHECK = x509.OCSPNoCheck() != x509.OCSPNoCheck()  # pragma: only cryptography<2.7

# For Selenium test cases
SKIP_SELENIUM_TESTS = os.environ.get(
    'SKIP_SELENIUM_TESTS',
    'n' if (NEWEST_PYTHON and NEWEST_CRYPTOGRAPHY) else 'y'
).lower().strip() == 'y'

VIRTUAL_DISPLAY = os.environ.get('VIRTUAL_DISPLAY', 'y').lower().strip() == 'y'
GECKODRIVER_PATH = os.path.join(ROOT_DIR, 'contrib', 'selenium', 'geckodriver')

if not os.path.exists(GECKODRIVER_PATH):
    raise ImproperlyConfigured(
        'Please download geckodriver to %s: '
        'https://selenium-python.readthedocs.io/installation.html#drivers' % GECKODRIVER_PATH)
