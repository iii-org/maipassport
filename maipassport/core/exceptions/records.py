from django.utils.translation import ugettext_lazy as _

from maipassport.core.exceptions.base import AniException


class CreateGpsRecordFailed(AniException):
    code = 'create_gps_record_failed'
    msg = _('Create GPS record failed')


class CreateHealthRecordFailed(AniException):
    code = 'create_health_record_failed'
    msg = _('Create health record failed')


class CreateUserCompanyRecordFailed(AniException):
    code = 'create_user_company_record_failed'
    msg = _('Create user company record failed')


class CreatePlaceEntryRecordFailed(AniException):
    code = 'create_place_entry_record_failed'
    msg = _('Create place entry record failed')
