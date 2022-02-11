from .base import *  # noqa
import logging, os
from datetime import datetime
import environ


os.environ["DJANGO_SETTINGS_MODULE"] = "config.settings.local"
env = environ.Env()
DOT_ENV_PATH = 'envs/.dockernized'
env.read_env(str(ROOT_DIR.path(DOT_ENV_PATH)))


NGROK_URL = env('NGROK_URL')

# GENERAL
# ------------------------------------------------------------------------------
# https://docs.djangoproject.com/en/dev/ref/settings/#debug
DEBUG = env.bool('DJANGO_DEBUG', True)
# https://docs.djangoproject.com/en/dev/ref/settings/#site-id
SITE_ID = env.int('DJANGO_SITE_ID', 1)
# https://docs.djangoproject.com/en/dev/ref/settings/#secret-key
SECRET_KEY = env('DJANGO_SECRET_KEY', default='HqgXFsaF3KcpjcSLDboeLWHsD6wHMaKyAmK1f8vjNWZRgFE2w7681SvStldvoXSH')
# https://docs.djangoproject.com/en/dev/ref/settings/#allowed-hosts
ALLOWED_HOSTS = [
    "localhost",
    "0.0.0.0",
    "127.0.0.1",
    "192.168.100.101",
    NGROK_URL
]

# DATABASES
# ------------------------------------------------------------------------------
# https://docs.djangoproject.com/en/dev/ref/settings/#databases

DATABASES = {
    # 'default': env.db('DATABASE_URL_DEFAULT', default='postgres:///aniappserver')
    'default': env.db('DATABASE_URL_DEFAULT', default='postgres:///' + USE_DB_IDS[USE_DB_ID]['DBNAME'])
}

DATABASES['default']['NAME'] = USE_DB_IDS[USE_DB_ID]['DBNAME']
DATABASES['default']['PORT'] = USE_DB_IDS[USE_DB_ID]['PORT']
# DATABASES['default']['ATOMIC_REQUESTS'] = True  # Atomic requests increases database loading

# CACHES
# ------------------------------------------------------------------------------
# https://docs.djangoproject.com/en/dev/ref/settings/#caches
CACHES = {
    'default': env.cache(),
    # TODO: use redis cluster as production environment
    'cluster': env.cache('CLUSTER_CACHE_URL')
}

# Celery
# ------------------------------------------------------------------------------
INSTALLED_APPS += ['maipassport.taskapp.celery.CeleryAppConfig']
if USE_TZ:
    # http://docs.celeryproject.org/en/latest/userguide/configuration.html#std:setting-timezone
    CELERY_TIMEZONE = TIME_ZONE
# http://docs.celeryproject.org/en/latest/userguide/configuration.html#std:setting-broker_url
CELERY_BROKER_URL = env('BROKER_URL')
# http://docs.celeryproject.org/en/latest/userguide/configuration.html#std:setting-result_backend
# CELERY_RESULT_BACKEND = CELERY_BROKER_URL  # note that CELERY_RESULT_BACKEND not support python 3.7
# http://docs.celeryproject.org/en/latest/userguide/configuration.html#std:setting-accept_content
CELERY_ACCEPT_CONTENT = ['json']
# http://docs.celeryproject.org/en/latest/userguide/configuration.html#std:setting-task_serializer
CELERY_TASK_SERIALIZER = 'json'
# http://docs.celeryproject.org/en/latest/userguide/configuration.html#std:setting-result_serializer
CELERY_RESULT_SERIALIZER = 'json'
# http://docs.celeryproject.org/en/latest/userguide/configuration.html#task-time-limit
# TODO: set to whatever value is adequate in your circumstances
CELERYD_TASK_TIME_LIMIT = 5 * 60
# http://docs.celeryproject.org/en/latest/userguide/configuration.html#task-soft-time-limit
# TODO: set to whatever value is adequate in your circumstances
CELERYD_TASK_SOFT_TIME_LIMIT = 60
# ------------------------------------------------------------------------------
# http://docs.celeryproject.org/en/latest/userguide/configuration.html#task-always-eager
CELERY_TASK_ALWAYS_EAGER = True
# http://docs.celeryproject.org/en/latest/userguide/configuration.html#task-eager-propagates
CELERY_TASK_EAGER_PROPAGATES = True

# dynamo db table
# DYNAMODB_APPS_TABLE = env('DYNAMODB_APPS_TABLE')
# DYNAMODB_PRETRANS_TABLE = env('DYNAMODB_PRETRANS_TABLE')
# DYNAMODB_USER_ACTION_LOG_TABLE = env('DYNAMODB_USER_ACTION_LOG_TABLE')
# DYNAMODB_ADMIN_AUDIT_LOG_TABLE = env('DYNAMODB_ADMIN_AUDIT_LOG_TABLE')

# elasticsearch endpoints
# ELASTICSEARCH_URL = env('ELASTICSEARCH_URL', default='http://localhost:9200/')

# TEMPLATES
# ------------------------------------------------------------------------------
# https://docs.djangoproject.com/en/dev/ref/settings/#templates
TEMPLATES[0]['OPTIONS']['debug'] = DEBUG  # noqa F405

# EMAIL
# ------------------------------------------------------------------------------
# https://docs.djangoproject.com/en/dev/ref/settings/#email-backend
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'  # we do not use SES for local development right now
# EMAIL_BACKEND = 'django_smtp_ssl.SSLEmailBackend'

# for local SES testing
# EMAIL_BACKEND = env('DJANGO_EMAIL_BACKEND', default='django.core.mail.backends.console.EmailBackend')
# AWS_SES_REGION_NAME = env('DJANGO_AWS_SES_REGION_NAME', default='us-west-2')
# AWS_SES_REGION_ENDPOINT = env('DJANGO_AWS_SES_REGION_ENDPOINT', default='email.us-west-2.amazonaws.com')

EMAIL_USE_TLS = True
# EMAIL_USE_SSL = True
#gmail
# TODO: Gmail need to allow less secure apps to access your account
#EMAIL_HOST = 'smtp.gmail.com'
#EMAIL_HOST_USER = 'youraccount@gmail.com'
#EMAIL_HOST_PASSWORD = 'yourpassword'
#office365
#EMAIL_HOST = 'lhr-efz.ms-acdc.office.com'

EMAIL_HOST = 'smtp.office365.com'
# EMAIL_HOST = 'sg2plcpnl0120.prod.sin2.secureserver.net'
# EMAIL_HOST = 'mail.maipocket.com'
EMAIL_HOST_USER = 'service@passcode.com.tw'
EMAIL_HOST_PASSWORD = 'Mx6617@@'
EMAIL_PORT = 587
# EMAIL_PORT = 465

DEFAULT_FROM_EMAIL = EMAIL_HOST_USER

# TODO: Office365 can't use this default from email
# DEFAULT_FROM_EMAIL = env(
#     'DJANGO_DEFAULT_FROM_EMAIL',
#     default=f'{PROJECT_NAME} <blake@maideax.com>'
# )

# https://django-debug-toolbar.readthedocs.io/en/latest/installation.html#internal-ips
INTERNAL_IPS = ['127.0.0.1', '10.0.2.2']

# asgi
CHANNEL_LAYERS = {
    'default': {
        'BACKEND': 'channels_redis.core.RedisChannelLayer',
        'CONFIG': {
            'hosts': [('127.0.0.1', 6379)],
        },
    }
}

# django-extensions
# ------------------------------------------------------------------------------
# https://django-extensions.readthedocs.io/en/latest/installation_instructions.html#configuration
# INSTALLED_APPS += ['django_extensions']  # noqa F405


# STORAGES
# ------------------------------------------------------------------------------
# https://django-storages.readthedocs.io/en/latest/#installation
INSTALLED_APPS += ['storages']  # noqa F405
# https://django-storages.readthedocs.io/en/latest/backends/amazon-S3.html#settings
AWS_ACCESS_KEY_ID = env('DJANGO_AWS_ACCESS_KEY_ID')
# https://django-storages.readthedocs.io/en/latest/backends/amazon-S3.html#settings
AWS_SECRET_ACCESS_KEY = env('DJANGO_AWS_SECRET_ACCESS_KEY')
# https://django-storages.readthedocs.io/en/latest/backends/amazon-S3.html#settings
# AWS_STORAGE_BUCKET_NAME = env('DJANGO_AWS_STORAGE_BUCKET_NAME')
# https://django-storages.readthedocs.io/en/latest/backends/amazon-S3.html#settings
# AWS_QUERYSTRING_AUTH = True
# DO NOT change these unless you know what you're doing.
# _AWS_EXPIRY = 60 * 60 * 24 * 7
# https://django-storages.readthedocs.io/en/latest/backends/amazon-S3.html#settings
# AWS_S3_OBJECT_PARAMETERS = {
#     'CacheControl': f'max-age={_AWS_EXPIRY}, s-maxage={_AWS_EXPIRY}, must-revalidate',
# }
# AWS_DEFAULT_ACL = 'private'

# AWS global settings
AWS_REGION = env('DJANGO_AWS_REGION')

# MEDIA
# ------------------------------------------------------------------------------
# region http://stackoverflow.com/questions/10390244/
# from storages.backends.s3boto3 import S3Boto3Storage  # noqa E402
# MediaRootS3BotoStorage = lambda: S3Boto3Storage(location='media')  # noqa

# endregion
DEFAULT_FILE_STORAGE = 'maipassport.core.boto3'
# MEDIA_URL = f'https://s3.amazonaws.com/{AWS_STORAGE_BUCKET_NAME}/media/'

# APP KEYS
# ------------------------------------------------------------------------------
# RSA_KEYS_DIR = ROOT_DIR.path('config/rsa_keys')
# RSA_PRIVATE_KEY_PEM = RSA_KEYS_DIR.path(env('PRIVATE_CRYPT_KEY_FILE', default='aniappserver_private_key.pem'))  # use generate_rsa_pem_files to create
# RSA_PUBLIC_KEY_PEM = RSA_KEYS_DIR.path(env('PUBLIC_CRYPT_KEY_FILE', default='aniappserver_public_key.pem'))
# RSA_SIGN_KEY_PEM = RSA_KEYS_DIR.path(env('PRIVATE_SIGN_KEY_FILE', default='aniappserver_sign_private_key.pem'))
# RSA_DATA_KEY_PEM = RSA_KEYS_DIR.path(env('DATA_KEY_FILE', default='data_public_key.pem'))
# RSA_CARD_DATA_PUB_KEY_PEM = RSA_KEYS_DIR.path(env('RSA_CARD_DATA_PUB_KEY_FILE', default='card_data_public_key.pem'))
# RSA_CARD_DATA_PRIV_KEY_PEM = RSA_KEYS_DIR.path(env('RSA_CARD_DATA_PRIV_KEY_FILE', default='card_data_private_key.pem'))


# LOGGER
# ------------------------------------------------------------------------------
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'filters': {
        'require_debug_false': {
            '()': 'django.utils.log.RequireDebugFalse'
        }
    },
    'formatters': {
        'verbose': {
            'format': '%(levelname)s %(asctime)s %(module)s '
                      '%(process)d %(thread)d %(message)s'
        },
        'local_log_format': {
            'format': '[%(asctime)s][%(levelname)s]%(message)s',
            'datefmt': "%Y-%m-%d %H:%M:%S"
        },
    },
    'handlers': {
        # 'mail_admins': {
        #     'level': 'ERROR',
        #     'filters': ['require_debug_false'],
        #     'class': 'django.utils.log.AdminEmailHandler'
        # },
        'db_log': {
            'level': 'DEBUG',
            'class': 'django_db_logger.db_log_handler.DatabaseLogHandler'
        },
        'console': {
            'level': 'DEBUG',
            'class': 'logging.StreamHandler',
        },
        # 'audit_log_file': {
        #     'level': 'DEBUG',
        #     'class': 'logging.FileHandler',
        #     #'filename': f'log/{os.getpid()}-django.log' #
        #     'filename': ROOT_DIR.path('log/audit_log_%s.log' % datetime.now().strftime("%Y%m%d")),
        #     'formatter': 'local_log_format',
        # },
        'system_log_file': {
            'level': 'DEBUG',
            'class': 'logging.FileHandler',
            #'filename': f'log/{os.getpid()}-django.log' #
            'filename': ROOT_DIR.path('log/system_log.log'),
            'formatter': 'local_log_format',
        },
    },
    'loggers': {
        'django': {
            'handlers': ['console', 'db_log'],
            'level': 'INFO',
            'propagate': True,
        },
        # 'aniappserver': {
        #     'handlers': ['console', 'db_log'],
        #     'level': 'DEBUG',
        #     'propagate': True,
        # },
        # 'audit_log': {
        #     'handlers': ['audit_log_file', 'db_log'],
        #     'level': 'DEBUG',
        #     'propagate': True,
        # },
        'system_log': {
            'handlers': ['system_log_file', 'db_log'],
            'level': 'DEBUG',
            'propagate': True,
        },
        'qinspect': {
            'handlers': ['console', 'db_log'],
            'level': 'DEBUG',
            'propagate': True,
        },
    }
}

# Django query inspect (https://github.com/dobarkod/django-queryinspect)
# ------------------------------------------------------------------------------
# Whether the Query Inspector should do anything (default: False)
QUERY_INSPECT_ENABLED = True
# Whether to log the stats via Django logging (default: True)
QUERY_INSPECT_LOG_STATS = True
# Whether to add stats headers (default: True)
QUERY_INSPECT_HEADER_STATS = False
# Whether to log duplicate queries (default: False)
QUERY_INSPECT_LOG_QUERIES = True
# Whether to log queries that are above an absolute limit (default: None - disabled)
QUERY_INSPECT_ABSOLUTE_LIMIT = 0  # in milliseconds
# Whether to log queries that are more than X standard deviations above the mean query time (default: None - disabled)
# QUERY_INSPECT_STANDARD_DEVIATION_LIMIT = 2
# Whether to include tracebacks in the logs (default: False)
QUERY_INSPECT_LOG_TRACEBACKS = True
# Project root (a list of directories, see below - default empty)
QUERY_INSPECT_TRACEBACK_ROOTS = [ROOT_DIR.root]

# add django-queryinspect in local for DB performance tuning
MIDDLEWARE += [
    'qinspect.middleware.QueryInspectMiddleware',
    # 'aniappserver.core.middlewares.ElasticLogMiddleware'
]
# remove DigitalSignatureVerifyMiddleware to use API client like PostMan to test
# MIDDLEWARE.remove('aniappserver.core.middlewares.DigitalSignatureVerifyMiddleware')


# DMYPAY
# DMYPAY_BUSINESS_ID = env('DMYPAY_BUSINESS_ID')
# DMYPAY_KEY = env('DMYPAY_KEY')
# DMYPAY_CASH_IN_ENDPOINT = env('DMYPAY_CASH_IN_ENDPOINT')
# DMYPAY_CASH_OUT_ENDPOINT = env('DMYPAY_CASH_OUT_ENDPOINT')

MITAKE_SMS_URL = env('MITAKE_SMS_URL')
MITAKE_SMS_USERNAME = env('MITAKE_SMS_USERNAME')
MITAKE_SMS_PASSWORD = env('MITAKE_SMS_PASSWORD')

SYSTEM_LOG = logging.getLogger('system_log')

GOOGLE_MAP_API_KEY = env('GOOGLE_MAP_API_KEY')
GOOGLE_MAP_URL = env('GOOGLE_MAP_URL')

III_ENC_TOKEN_KEY = env('III_ENC_TOKEN_KEY')
III_ENC_IV = env('III_ENC_IV')
III_URL = env('III_TEST_URL')


LIFF_REDIRECT_URL = env('NGROK_URL')
LIFF_ID_QR_SHOW = env('LIFF_ID_QR_SHOW')
LIFF_ID_QR_SCAN = env('LIFF_ID_QR_SCAN')
LIFF_ID_HISTORY = env('LIFF_ID_HISTORY')
LIFF_ID_BIND = env('LIFF_ID_BIND')
LIFF_ID_DECLARATION = env('LIFF_ID_DECLARATION')
LIFF_ID_CLOCK_IN = env('LIFF_ID_CLOCK_IN')
LIFF_ID_USER_FILE = env('LIFF_ID_USER_FILE')
LIFF_ID_COM_REG = env('LIFF_ID_COM_REG')
LIFF_ID_QR_SHOW_ENG = env('LIFF_ID_QR_SHOW_ENG')
LIFF_ID_QR_SCAN_ENG = env('LIFF_ID_QR_SCAN_ENG')
LIFF_ID_HISTORY_ENG = env('LIFF_ID_HISTORY_ENG')
LIFF_ID_BIND_ENG = env('LIFF_ID_BIND_ENG')
LIFF_ID_DECLARATION_ENG = env('LIFF_ID_DECLARATION_ENG')
LIFF_ID_CLOCK_IN_ENG = env('LIFF_ID_CLOCK_IN_ENG')
LIFF_ID_USER_FILE_ENG = env('LIFF_ID_USER_FILE_ENG')
LIFF_ID_COM_REG_ENG = env('LIFF_ID_COM_REG_ENG')

MSG_API_CHANNEL_SEC = env('MSG_API_CHANNEL_SEC')
MSG_API_CHANNEL_TOKEN = env('MSG_API_CHANNEL_TOKEN')

RH_DEFAULT_MENU = env('RH_DEFAULT_MENU')
RH_DEFAULT_MENU_ENG = env('RH_DEFAULT_MENU_ENG')
RH_OTHER = env('RH_OTHER')
RH_OTHER_NO_COM = env('RH_OTHER_NO_COM')
RH_OTHER_NO_COM_ENG = env('RH_OTHER_NO_COM_ENG')
QR_IMAGE_PATH = env('QR_IMAGE_PATH')
