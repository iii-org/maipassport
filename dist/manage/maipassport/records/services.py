import json
import requests
from celery_once import QueueOnce

from django.db import transaction
from django.conf import settings

from maipassport import celery_app
from maipassport.citadel.services import logger_writer
from maipassport.companies.models import Company, Place
from maipassport.core.exceptions import (UserNotExists, CreateGpsRecordFailed, HealthCodeNotExists, PlaceNotExists,
                                         CreateHealthRecordFailed, AttendanceStatusNotExists, CompanyNotExists,
                                         UserAttendanceStatusNotExists, CreateUserCompanyRecordFailed,
                                         CreatePlaceEntryRecordFailed, RequestFail)
from maipassport.records.models import PlaceEntryRecord, HealthRecord, AttendanceRecord, FlexContent
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



