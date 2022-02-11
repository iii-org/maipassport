from rest_framework import serializers

from django.utils.translation import ugettext_lazy as _

from maipassport.records.models import ApproachRecord
from maipassport.companies.models import NewCompanyApply
from maipassport.users.models import HealthCode, AttendanceStatus
from maipassport.core.utils import utc_time_to_local_time


class WebApproachRecordSerializer(serializers.Serializer):

    def to_representation(self, record):
        result = {
            'pub_id': record.pub_id,
            'record_time': utc_time_to_local_time(record.created).strftime('%Y-%m-%d %H:%M:%S'),
        }
        if record.app_user_id == self.context['request'].user_object.id:
            result['approach_user'] = record.scan_user.auth_user.first_name
            result['approach_action'] = 'SCANNED'
        else:
            result['approach_user'] = record.app_user.auth_user.first_name
            result['approach_action'] = 'SCAN'
        if record.type == ApproachRecord.HEALTH_CHECK:
            result['approach_type'] = 'HEALTH'
            if record.healthrecord.health_code == HealthCode.NORMAL:
                result['code_tag'] = 0
                result['code_result'] = _('Normal')
            else:
                result['code_tag'] = 1
                result['code_result'] = _('Danger')
        elif record.type == ApproachRecord.APPROACH_CHECK:
            result['approach_type'] = 'APPROACH'
        elif record.type == ApproachRecord.VISITOR_CHECK:
            result['approach_type'] = 'VISITOR'
        return result


class WebPlaceRecordSerializer(serializers.Serializer):

    def to_representation(self, record):
        result = {
            'pub_id': record.pub_id,
            'record_time': utc_time_to_local_time(record.created).strftime('%Y-%m-%d %H:%M:%S'),
        }
        if record.place_entry:
            if record.place_entry.company:
                result['location_name'] = '{} / {}'.format(record.place_entry.company.name, record.place_entry.name)
            else:
                result['location_name'] = record.place_entry.name
        elif 'location_address' in record.location:
            result['location_name'] = record.location['location_address']
        else:
            if 'latlon_latitude' in record.location and 'latlon_longitude' in record.location:
                result['location_name'] = '{}:{} {}:{}'.format(str(_('latitude')),
                                                               record.location['latlon_latitude'],
                                                               str(_('longitude')),
                                                               record.location['latlon_longitude'])
            else:
                result['location_name'] = _('Get Location Failed')
        result['act_name'] = ''
        result['act_org'] = ''
        result['act_org_contact'] = ''

        if 'act_name' in record.note:
            result['act_name'] = record.note['act_name']
        if 'act_organizer' in record.note:
            result['act_org'] = record.note['act_organizer']
        if 'act_org_contact' in record.note:
            result['act_org_contact'] = record.note['act_org_contact']
        return result


class WebClockInRecordSerializer(serializers.Serializer):

    def to_representation(self, record):
        status_dict = AttendanceStatus.return_status_dict()
        result = {
            'pub_id': record.pub_id,
            'record_time': utc_time_to_local_time(record.created).strftime('%Y-%m-%d %H:%M:%S'),
            'clock_in_place': record.approach_place.name,
            'status_show': status_dict[record.attendance_status],
            'work_status': record.status
        }
        return result


class WebCompanyRegSerializer(serializers.Serializer):

    def to_representation(self, record):
        result = {
            'pub_id': record.pub_id,
            'record_time': utc_time_to_local_time(record.created).strftime('%Y-%m-%d %H:%M:%S'),
            'company_name': record.company_name,
            'tax_id_num': record.tax_id_number,
            'status_show': record.get_status_display(),
            'status': record.status
        }
        return result


class WebShopRegSerializer(serializers.Serializer):

    def to_representation(self, record):
        result = {
            'pub_id': record.pub_id,
            'record_time': utc_time_to_local_time(record.created).strftime('%Y-%m-%d %H:%M:%S'),
            'shop_name': record.name,
            'shop_phone': record.place_contact_phone,
            'shop_address': record.location,
            'status_show': record.get_company_verify_display(),
            'status': record.company_verify
        }
        return result


class WebVacRecordSerializer(serializers.Serializer):

    def to_representation(self, record):
        result = {
            'pub_id': record.pub_id,
            'record_time': utc_time_to_local_time(record.created).strftime('%Y-%m-%d %H:%M:%S'),
            'image_url': record.image_url,
        }
        return result


class WebRapTestSerializer(serializers.Serializer):

    def to_representation(self, record):
        result = {
            'pub_id': record.pub_id,
            'record_time': utc_time_to_local_time(record.created).strftime('%Y-%m-%d %H:%M:%S'),
            'image_url': record.image_url,
        }
        return result


class WebCovHistorySerializer(serializers.Serializer):

    def to_representation(self, record):
        result = {
            'pub_id': record.pub_id,
            'record_time': utc_time_to_local_time(record.created).strftime('%Y-%m-%d %H:%M:%S'),
            'image_url': record.image_url,
        }
        return result
