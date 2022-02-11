"""
Base settings to build other settings files upon.
"""
from django.utils.translation import gettext_lazy as _
import environ

ROOT_DIR = environ.Path(__file__) - 3  # (aniappserver/config/settings/base.py - 3 = aniappserver/)
APPS_DIR = ROOT_DIR.path('maipassport')


# choose: base, otc, meco
USE_DB_IDS = {
    'base': {'DBNAME': 'maipassport2', 'PORT': '5412'},
    # 'production': {'DBNAME': 'maipassport', 'PORT': '5432'},
}

USE_DB_ID = 'base'

# 是否不驗證KYC
# IS_BY_PASS_KYC = True
# IS_BY_PASS_KYC = False

# GENERAL
# ------------------------------------------------------------------------------
# Local time zone. Choices are
# http://en.wikipedia.org/wiki/List_of_tz_zones_by_name
# though not all of them may be available with every OS.
# In Windows, this must be set to your system time zone.
TIME_ZONE = 'Asia/Taipei'
# https://docs.djangoproject.com/en/dev/ref/settings/#language-code
LANGUAGE_CODE = 'zh-Hant'
# LANGUAGE_CODE = 'en-us'
# https://docs.djangoproject.com/en/dev/ref/settings/#use-i18n
USE_I18N = True
# https://docs.djangoproject.com/en/dev/ref/settings/#use-l10n
USE_L10N = True
# https://docs.djangoproject.com/en/dev/ref/settings/#use-tz
USE_TZ = True

LANGUAGES = (
    ('en-us', _('English')),
    ('zh-Hant', _('Traditional Chinese')),
)
# LOCALE_PATHS = (
#     os.path.join(ROOT_DIR, 'locale'),
# )
LOCALE_PATHS = [str(ROOT_DIR('locale'))]


# URLS
# ------------------------------------------------------------------------------
# https://docs.djangoproject.com/en/dev/ref/settings/#root-urlconf
ROOT_URLCONF = 'config.urls'
# https://docs.djangoproject.com/en/dev/ref/settings/#wsgi-application
WSGI_APPLICATION = 'config.wsgi.application'


# async
# ASGI_APPLICATION = "maipassport.core.routing.application"
# CHANNEL_LAYERS = {
#     'default': {
#         'BACKEND': 'channels_redis.core.RedisChannelLayer',
#         'CONFIG': {
#             'hosts': [('redis', 6379)],
#         },
#     }
# }


# APPS
# ------------------------------------------------------------------------------
DJANGO_APPS = [
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.sites',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.admin',
]
THIRD_PARTY_APPS = [
    'rest_framework',
    'django_extensions',
    'memoize',
    'qrcode',
    'django_db_logger',
]
LOCAL_APPS = [
    'maipassport.citadel',
    'maipassport.companies',
    'maipassport.contracts',
    'maipassport.core',
    'maipassport.records',
    'maipassport.transfers',
    'maipassport.users',
]
# https://docs.djangoproject.com/en/dev/ref/settings/#installed-apps
INSTALLED_APPS = DJANGO_APPS + THIRD_PARTY_APPS + LOCAL_APPS

# MIGRATIONS
# ------------------------------------------------------------------------------
# https://docs.djangoproject.com/en/dev/ref/settings/#migration-modules
# MIGRATION_MODULES = {
#     'sites': 'aniappserver.contrib.sites.migrations'
# }

# AUTHENTICATION
# ------------------------------------------------------------------------------
# https://docs.djangoproject.com/en/dev/ref/settings/#authentication-backends
AUTHENTICATION_BACKENDS = [
    'django.contrib.auth.backends.ModelBackend',
]
# https://docs.djangoproject.com/en/dev/ref/settings/#auth-user-model
AUTH_USER_MODEL = 'auth.User'
# https://docs.djangoproject.com/en/dev/ref/settings/#login-redirect-url
LOGIN_REDIRECT_URL = 'app_index'
# https://docs.djangoproject.com/en/dev/ref/settings/#login-url
LOGIN_URL = 'app_login'

# PASSWORDS
# ------------------------------------------------------------------------------
# https://docs.djangoproject.com/en/dev/ref/settings/#password-hashers
PASSWORD_HASHERS = [
    # https://docs.djangoproject.com/en/dev/topics/auth/passwords/#using-argon2-with-django
    'django.contrib.auth.hashers.Argon2PasswordHasher',
    'django.contrib.auth.hashers.PBKDF2PasswordHasher',
    'django.contrib.auth.hashers.PBKDF2SHA1PasswordHasher',
    'django.contrib.auth.hashers.BCryptSHA256PasswordHasher',
    'django.contrib.auth.hashers.BCryptPasswordHasher',
]
# https://docs.djangoproject.com/en/dev/ref/settings/#auth-password-validators
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

# MIDDLEWARE
# ------------------------------------------------------------------------------
# https://docs.djangoproject.com/en/dev/ref/settings/#middleware
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',  # for Django admin system
    'django.middleware.locale.LocaleMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',  # for Django admin system
    'maipassport.core.middlewares.VersionCheckMiddleware',
    'maipassport.core.middlewares.TokenParseMiddleware',
    'maipassport.core.middlewares.UtsCheckMiddleware',
    'maipassport.core.middlewares.LanguageCheckMiddleware',
    # 'aniappserver.core.middlewares.DigitalSignatureVerifyMiddleware',
    'maipassport.core.middlewares.CookieSettingMiddleware',
    'maipassport.core.middlewares.DigitalSignatureSignMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',  # for Django admin system
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

# STATIC
# ------------------------------------------------------------------------------
# https://docs.djangoproject.com/en/dev/ref/settings/#static-root
STATIC_ROOT = str(ROOT_DIR('staticfiles'))
# https://docs.djangoproject.com/en/dev/ref/settings/#static-url
STATIC_URL = '/static/'
# https://docs.djangoproject.com/en/dev/ref/contrib/staticfiles/#std:setting-STATICFILES_DIRS
STATICFILES_DIRS = [
    str(APPS_DIR.path('static')),
]
# https://docs.djangoproject.com/en/dev/ref/contrib/staticfiles/#staticfiles-finders
STATICFILES_FINDERS = [
    'django.contrib.staticfiles.finders.FileSystemFinder',
    'django.contrib.staticfiles.finders.AppDirectoriesFinder',
]

# MEDIA
# ------------------------------------------------------------------------------
# https://docs.djangoproject.com/en/dev/ref/settings/#media-root
MEDIA_ROOT = str(APPS_DIR('media'))
# https://docs.djangoproject.com/en/dev/ref/settings/#media-url
MEDIA_URL = '/media/'

# TEMPLATES
# ------------------------------------------------------------------------------
# https://docs.djangoproject.com/en/dev/ref/settings/#templates
TEMPLATES = [
    {
        # https://docs.djangoproject.com/en/dev/ref/settings/#std:setting-TEMPLATES-BACKEND
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        # https://docs.djangoproject.com/en/dev/ref/settings/#template-dirs
        'DIRS': [
            str(APPS_DIR.path('templates')),
        ],
        'OPTIONS': {
            # https://docs.djangoproject.com/en/dev/ref/settings/#template-debug
            'debug': False,
            # https://docs.djangoproject.com/en/dev/ref/settings/#template-loaders
            # https://docs.djangoproject.com/en/dev/ref/templates/api/#loader-types
            'loaders': [
                'django.template.loaders.filesystem.Loader',
                'django.template.loaders.app_directories.Loader',
            ],
            # https://docs.djangoproject.com/en/dev/ref/settings/#template-context-processors
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.template.context_processors.i18n',
                'django.template.context_processors.media',
                'django.template.context_processors.static',
                'django.template.context_processors.tz',
                'django.contrib.messages.context_processors.messages',
                # 'aniappserver.citadel.context_processors.side_bar',
                # 'aniappserver.citadel.context_processors.permission',
                # 'aniappserver.citadel.context_processors.base_currency'
            ],
        },
    },
]

# SESSION_ENGINE
# ------------------------------------------------------------------------------
# https://docs.djangoproject.com/en/dev/ref/settings/#session-engine
SESSION_ENGINE = 'django.contrib.sessions.backends.cache'

# http://django-crispy-forms.readthedocs.io/en/latest/install.html#template-packs
CRISPY_TEMPLATE_PACK = 'bootstrap4'

# FIXTURES
# ------------------------------------------------------------------------------
# https://docs.djangoproject.com/en/dev/ref/settings/#fixture-dirs
FIXTURE_DIRS = (
    str(APPS_DIR.path('fixtures')),
)

# ADMIN
# ------------------------------------------------------------------------------
# Django Admin URL.
ADMIN_URL = 'mai_secret_garden/'
# https://docs.djangoproject.com/en/dev/ref/settings/#admins
ADMINS = [
    ("""Daniel Roy Greenfeld""", 'daniel-roy-greenfeld@example.com'),
]
# https://docs.djangoproject.com/en/dev/ref/settings/#managers
MANAGERS = ADMINS


# Your stuff...
# ------------------------------------------------------------------------------
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': (),
    # 'DEFAULT_VERSIONING_CLASS': 'aniappserver.core.versioning.ANIAcceptHeaderVersioning',
    'DEFAULT_RENDERER_CLASSES': (
        # 'aniappserver.core.renderers.ANIV1Renderer',
        # 'aniappserver.core.renderers.ANIV2Renderer',
        'rest_framework.renderers.JSONRenderer',
    ),
    'DEFAULT_PARSER_CLASSES': (
        'rest_framework.parsers.JSONParser',
    ),
    'ALLOWED_VERSIONS': ('v1', ),
    'DEFAULT_VERSION': 'v1',  # have no usage in custom ANIAcceptHeaderVersioning
    'EXCEPTION_HANDLER': 'maipassport.core.exceptions.ani_exception_handler',
    'TEST_REQUEST_DEFAULT_FORMAT': 'json'
}

# do not append slash
APPEND_SLASH = False


# Base Currency for the whole system
BASE_CURRENCY = 'PHP'

# Project Name
PROJECT_NAME = 'MaiPassport'

LOCAL_LOGGER = None
