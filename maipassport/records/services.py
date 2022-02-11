import json
import requests
from datetime import datetime, timedelta
from base64 import b64decode, b64encode, urlsafe_b64decode
from celery_once import QueueOnce

from django.db import transaction
from django.utils import timezone
from django.db.models import Max, Min
from django.conf import settings

from maipassport import celery_app
from maipassport.citadel.services import logger_writer
from maipassport.companies.models import Company, Place
from maipassport.core.exceptions import (UserNotExists, CreateGpsRecordFailed, HealthCodeNotExists, PlaceNotExists,
                                         CreateHealthRecordFailed, AttendanceStatusNotExists, CompanyNotExists,
                                         UserAttendanceStatusNotExists, CreateUserCompanyRecordFailed,
                                         CreatePlaceEntryRecordFailed, RequestFail)
from maipassport.core.utils import time_utils
from maipassport.records.models import PlaceEntryRecord, HealthRecord, AttendanceRecord, FlexContent, NTPCCalender
from maipassport.users.models import AppUser, HealthCode, AttendanceStatus


class RecordService:

    @staticmethod
    # @celery_app.task(base=QueueOnce, once={'graceful': True})
    def create_place_record(user_id, location=None, place_id=None):
        app_user = AppUser.objects.filter(pub_id=user_id)
        if app_user.exists():
            with transaction.atomic():
                try:
                    place_record = PlaceEntryRecord.objects.create(app_user=app_user.first())
                    if location:
                        place_record.location = location
                    if place_id:
                        place = Place.objects.filter(pub_id=place_id)
                        if not place.exists():
                            raise PlaceNotExists
                        else:
                            place_record.place_entry = place
                    place_record.save()
                except Exception as e:
                    logger_writer('SYSTEM', 'error', 'CREATE_GPS_RECORD', f'Create gps record got error: {str(e)}')
                    raise CreateGpsRecordFailed
                else:
                    return place_record
        else:
            raise UserNotExists


class GpsService:
    @staticmethod
    def get_gps_location(longitude, latitude):
        api_url = settings.GOOGLE_MAP_URL + '/geocode/json'
        api_url += '?latlng=' + longitude + ',' + latitude + '&language=zh-TW' + '&key=' + settings.GOOGLE_MAP_API_KEY
        response = requests.get(
            api_url,
            headers={'Content-Type': 'application/json'},
        )
        if response.status_code != 200:
            raise RequestFail
        else:
            result = response.json()
            if 'results' in result and len(result['results']) > 1 and 'formatted_address' in result['results'][0]:
                return result['results'][0]['formatted_address']
            else:
                return False


def get_flex_content(flex_name):
    flex_content = FlexContent.objects.filter(name=flex_name)
    if flex_content.exists():
        flex_content = flex_content.first()
        flex_msg = flex_content.content


def checkinmsg():
    today = datetime.today()
    check_holiday = NTPCCalender.objects.filter(date=datetime.strftime(today, '%Y-%m-%d'))
    # test
    # headers = {
    #     "Authorization": "Bearer pwrAwFD7gamSkpqqAChOuL6tALQDpEBMMHCOzbwUym7",
    #     "Content-Type": "application/x-www-form-urlencoded"
    # }
    # production
    headers = {
        "Authorization": "Bearer A6SxQbHoirAUcFNxOZXILcDfRhxh5nmXqwCc6uvKTQf",
        "Content-Type": "application/x-www-form-urlencoded"
    }
    payload = {'message': '早上09:30上班打卡提醒\n' + 'https://line.me/R/ti/p/%40310ebhze' + '\n點擊連結打卡'}
    if not check_holiday.exists() or (check_holiday.exists() and check_holiday.first().isHoliday == False):
        r = requests.post("https://notify-api.line.me/api/notify", headers=headers, params=payload)

    return r.status_code


def checkoutmsg():
    today = datetime.today()
    check_holiday = NTPCCalender.objects.filter(date=datetime.strftime(today, '%Y-%m-%d'))

    # test
    # headers = {
    #     "Authorization": "Bearer pwrAwFD7gamSkpqqAChOuL6tALQDpEBMMHCOzbwUym7",
    #     "Content-Type": "application/x-www-form-urlencoded"
    # }
    # production
    headers = {
        "Authorization": "Bearer A6SxQbHoirAUcFNxOZXILcDfRhxh5nmXqwCc6uvKTQf",
        "Content-Type": "application/x-www-form-urlencoded"
    }
    payload = {'message': '晚上18:30下班打卡提醒\n' + 'https://line.me/R/ti/p/%40310ebhze' + '\n點擊連結打卡'}
    if not check_holiday.exists() or (check_holiday.exists() and check_holiday.first().isHoliday == False):
        r = requests.post("https://notify-api.line.me/api/notify", headers=headers, params=payload)

    return r.status_code


def checkin_api_maideax():
    """
    104打卡功能串接api
    get_timestamp: turn datetime to timestamp(milliseconds)
    send_104_token(): send request to 104 to complete oauth2 authorization, to get the access token for next step
        'Authorization': f'Basic b64encode("your_client_id:your_client_secret")
    send_104_check(): send checkin information to 104
    will check hourly to see if there is new checkin record or not, if there is, call api send to 104 server.
    app_user__usercompanytable__company__tax_id_number should be changed to your company tax_id_number
    """
    def get_timestamp(datetime_obj=None, return_milliseconds=True):
        if not datetime_obj:
            datetime_obj = datetime.now()
        if return_milliseconds is True:
            uts = round(datetime_obj.timestamp() * 1000)
        else:
            uts = round(datetime_obj.timestamp())
        return uts

    def send_104_token():
        url = "https://apis.104api.com.tw/oauth2/token"
        payload = "grant_type=client_credentials&scope=prohrm"
        headers = {
            'Content-Type': 'application/x-www-form-urlencoded',
            'Authorization': f'Basic {b64encode("C00e1dkqjf674g8sso80gkk80gc:KS42YY8BLCUekkIv8vWNaADu1ktwwyvJ".encode()).decode()}'
        }
        response = requests.request("POST", url, headers=headers, data=payload)
        if response.status_code == 200:
            logger_writer('SYSTEM', 'info', 'SEND_104_TOKEN', f'Response Status: {str(response.status_code)}')
            return (response.status_code, response.json()['access_token'])
        else:
            logger_writer('SYSTEM', 'error', 'SEND_104_TOKEN', f'Status Code Not 200: {str(response.status_code)}')
            return (response.status_code, response.content)

    def send_104_check(token, msg):
        url = "https://apis.104api.com.tw/prohrm/1.0/hrmapi/external/transferCard"
        payload = json.dumps(msg)
        headers = {
            'Content-Type': 'application/json',
            'Accept': 'application/json',
            'Authorization': f'Bearer {token}'
        }

        response = requests.request("POST", url, headers=headers, data=payload)
        logger_writer('SYSTEM', 'info', 'SEND_104_CHECK', f'Response: {str(response.json())}')
        return (response.status_code, response.json())

    now = datetime.today()

    create_at_min = datetime.strptime(now.strftime('%Y-%m-%d %H'), '%Y-%m-%d %H') - timedelta(hours=1)
    create_at_max = datetime.strptime(now.strftime('%Y-%m-%d %H'), '%Y-%m-%d %H')

    record_list = PlaceEntryRecord.objects.select_related(
        'place_entry', 'app_user__auth_user', 'place_entry__company'). filter(place_entry__company__name__isnull=True)
    record_list = record_list.filter(app_user__usercompanytable__company__tax_id_number=42735341)
    record_list = record_list.filter(created__gte=timezone.make_aware(create_at_min))
    record_list = record_list.filter(created__lt=timezone.make_aware(create_at_max))
    # Alan_TODO: for production, remove temp result use result=send_104_token, change append empNo to
    #  record.app_user.emp_no
    if record_list.exists():
        # result = send_104_token()
        result = (200, "sample")
        if result[0] == 200:
            msg = []
            for record in record_list:
                local_time = time_utils.utc_time_to_local_time(record.created)
                msg.append({'empNo': record.app_user_id, 'cardTime': get_timestamp(local_time)})
            # send_104_check(result[1], msg)
            print(msg)
    else:
        print("no new checkin record")

