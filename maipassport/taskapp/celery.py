import os
from celery import Celery
from celery.schedules import crontab
from django.apps import apps, AppConfig
from django.conf import settings
import datetime, requests

if not settings.configured:
    # set the default Django settings module for the 'celery' program.
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.local')  # pragma: no cover


app = Celery('maipassport')


class CeleryAppConfig(AppConfig):
    name = 'maipassport.taskapp'
    verbose_name = 'Celery Config'

    def ready(self):
        # Using a string here means the worker will not have to
        # pickle the object when using Windows.
        # - namespace='CELERY' means all celery-related configuration keys
        #   should have a `CELERY_` prefix.
        app.config_from_object('django.conf:settings', namespace='CELERY')
        installed_apps = [app_config.name for app_config in apps.get_app_configs()]
        app.autodiscover_tasks(lambda: installed_apps, force=True)
        app.conf.broker_transport_options = {'visibility_timeout': 86700}
        app.conf.ONCE = {
            'backend': 'celery_once.backends.Redis',
            'settings': {
                # 'url': 'redis://localhost:6379/0',
                'url': settings.CELERY_BROKER_URL,
                'default_timeout': 60 * 60
            }
        }


# example periodic task which execute every minutes between 9 to 19 hour
app.conf.beat_schedule = {
    # 'crontab-test-every-minute': {
    #     'task': 'aniappserver.taskapp.celery.debug_task',
    #     'schedule': crontab(hour='9-19', minute='*')
    # },
    'reset_user_health_code_every_day': {
        'task': 'maipassport.taskapp.celery.reset_user_health_code',
        'schedule': crontab(hour=0, minute=1)
    },
    # 'check_expired_rate_every_hour': {
    #     'task': 'aniappserver.taskapp.celery.check_expired',
    #     'schedule': crontab(hour='*/1', minute='0')
    # },
    # Alan_TODO: call 104 checkin api every hour(not open)
    # 'checkin_api_maideax': {
    #     'task': 'maipassport.taskapp.celery.checkin_api_maideax',
    #     'schedule': crontab(hour='*/1', minute='0')
    # },
    'send_daily_start_work_notify': {
        'task': 'maipassport.taskapp.celery.send_daily_start_work_notify',
        'schedule': crontab(hour=9, minute=30)
    },
    # 'send_daily_end_work_notify': {
    #     'task': 'maipassport.taskapp.celery.send_daily_end_work_notify',
    #     'schedule': crontab(hour=18, minute=30)
    # },
    # 'send_gift_card_daily_report': {
    #     'task': 'aniappserver.taskapp.celery.send_gift_card_daily_report',
    #     'schedule': crontab(hour=0, minute=0)
    # },
}


# @app.task(bind=True)
# def debug_task(self):
#     print(f'Request: {self.request!r}')  # pragma: no cover

@app.task(bind=True)
def reset_user_health_code(self):
    print(f'reset_user_health_code: {self.request!r}')
    from maipassport.users.services import AppUserServices
    from maipassport.citadel.services import logger_writer
    AppUserServices.reset_health_code()
    logger_writer('SYSTEM', 'info', 'RESET_HEALTH_CODE_TASK', 'Reset all user health code.')


@app.task(bind=True)
def send_daily_start_work_notify(self):
    from maipassport.records.services import checkinmsg
    checkinmsg()


@app.task(bind=True)
def checkin_api_maideax(self):
    from maipassport.records.services import checkin_api_maideax
    checkin_api_maideax()

# @app.task(bind=True)
# def send_daily_end_work_notify(self):
#     from maipassport.records.services import checkoutmsg
#     checkoutmsg()


# @app.task(bind=True)
# def check_expired(self):
#     print(f'check_expired: {self.request!r}')
#     from aniappserver.citadel.services import logger_writer
#     from aniappserver.transfers.services import TransferService
#     update_time = TransferService.update_status_to_expired()
#     logger_writer('SYSTEM', 'info', 'CHECK_EXPIRED',
#                   f'{update_time} of transfer has been expired by check function celery.')
#
#
# @app.task(bind=True)
# def send_daily_report(self):
#     print(f'send_daily_report: {self.request!r}')
#     from aniappserver.citadel.services import logger_writer
#     from aniappserver.activity.services import ActivityService
#     ActivityService.send_daily_report()
#     logger_writer('SYSTEM', 'info', 'SEND_DAILY_REPORT', 'Send Daily Report to Store.')
#
#
# @app.task(bind=True)
# def send_gift_card_daily_report(self):
#     print(f'send_gift_card_daily_report: {self.request!r}')
#     from aniappserver.citadel.services import logger_writer
#     from aniappserver.ecplatform.services import EcPlatformService
#     EcPlatformService.send_daily_report()
#     logger_writer('SYSTEM', 'info', 'SEND_GIFT_CARD_DAILY_REPORT', 'Send Gift Card Daily Report to Store.')
