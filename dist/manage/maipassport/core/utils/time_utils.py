import pytz
from datetime import datetime, timedelta
from dateutil import tz

from django.utils import timezone


def get_timestamp(datetime_obj=None, return_milliseconds=True):
    if not datetime_obj:
        datetime_obj = timezone.now()
    if return_milliseconds is True:
        uts = round(datetime_obj.timestamp() * 1000)
    else:
        uts = round(datetime_obj.timestamp())
    return uts


def to_iso8601_utc_string(datetime_obj):
    utc_datetime = datetime_obj.astimezone(pytz.utc)
    return utc_datetime.strftime('%Y-%m-%dT%H:%M:%SZ')


def utc_time_to_local_time(datetime_obj):
    # return datetime_obj.replace(tzinfo=tz.gettz("UTC")).astimezone(tz.gettz(datetime.now(tz.tzlocal()).tzname()))
    # return datetime_obj.astimezone(tz.gettz(datetime.now(tz.tzlocal()).tzname())).strftime('%Y-%m-%dT%H:%M:%SZ')
    return datetime_obj.astimezone(tz.gettz(datetime.now(tz.tzlocal()).tzname()))


def local_time_to_utc_time(datetime_obj):
    return datetime_obj.astimezone(pytz.utc)


def utc_time_to_local_time_str(datetime_obj):
    # return datetime_obj.replace(tzinfo=tz.gettz("UTC")).astimezone(tz.gettz(datetime.now(tz.tzlocal()).tzname()))
    return datetime_obj.astimezone(tz.gettz(datetime.now(tz.tzlocal()).tzname())).strftime('%Y-%m-%dT%H:%M:%SZ')


def get_effective_time(datetime_obj):
    str_date = datetime_obj.strftime('%Y-%m-%d')
    str_effective_time = '{} 00:00:00'.format(str_date)
    return datetime.strptime(str_effective_time, '%Y-%m-%d %H:%M:%S') + timedelta(days=1)


def get_utc_format_today():
    start_time = datetime.strptime('{} 00:00:00'.format(datetime.now().strftime('%Y-%m-%d')),
                                   '%Y-%m-%d %H:%M:%S').astimezone(pytz.utc)
    end_time = start_time + timedelta(days=1)
    return start_time, end_time


def get_utc_format_one_day(datetime_obj):
    start_time = datetime.strptime('{} 00:00:00'.format(datetime_obj.strftime('%Y-%m-%d')),
                                   '%Y-%m-%d %H:%M:%S').astimezone(pytz.utc)
    end_time = start_time + timedelta(days=1)
    return start_time, end_time
