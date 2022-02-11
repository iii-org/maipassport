from django.utils.translation import ugettext_lazy as _

from maipassport.core.exceptions.base import AniException


class UserAlreadyExists(AniException):
    code = 'user_already_exists'
    msg = _('User already exists')


class UserNotExists(AniException):
    code = 'user_not_exists'
    msg = _('User not exists')


class UserAttendanceStatusNotExists(AniException):
    code = 'user_attendance_status_not_exists'
    msg = _('User Attendance status not exists')


class HealthCodeNotExists(AniException):
    code = 'health_code_not_exists'
    msg = _('Health Code not exists')


class AttendanceStatusNotExists(AniException):
    code = 'attendance_status_not_exists'
    msg = _('Attendance status not exists')


class CompanyNotExists(AniException):
    code = 'company_not_exists'
    msg = _('Company not exists')


class CompanyAlreadyExists(AniException):
    code = 'company_already_exists'
    msg = _('Company already exists')


class DepartmentNotExists(AniException):
    code = 'department_not_exists'
    msg = _('Department not exists')


class DepartmentAlreadyExists(AniException):
    code = 'department_already_exists'
    msg = _('Department already exists')


class TitleNotExists(AniException):
    code = 'title_not_exists'
    msg = _('Title not exists')


class CreateAppUserFailed(AniException):
    code = 'create_app_user_failed'
    msg = _('Create App user failed')


class CreateDepartmentFailed(AniException):
    code = 'create_department_failed'
    msg = _('Create department failed')


class CreatePlaceFailed(AniException):
    code = 'create_place_failed'
    msg = _('Create place failed')


class CompanyTitleAlreadyExists(AniException):
    code = 'company_title_already_exists'
    msg = _('Company title already exists')


class PlaceNotExists(AniException):
    code = 'place_not_exists'
    msg = _('Place not exists')


class UserAttendanceStatusAlreadyExists(AniException):
    code = 'user_attendance_status_already_exists'
    msg = _('User Attendance Status already exists')


class PhoneFormatWrong(AniException):
    code = 'phone_format_wrong'
    msg = _('User phone format wrong')


class PhoneAlreadyExists(AniException):
    code = 'phone_already_exists'
    msg = _('This phone already exists')


class RequestFail(AniException):
    code = 'request_fail'
    msg = _('Request Fail')


class AccountCantReset(AniException):
    code = 'account_can_not_reset'
    msg = _('This account can not reset')


class AccountAlreadyBindPhone(AniException):
    code = 'account_already_bind_phone'
    msg = _('The user is bound, please reset the password directly or contact the administrator')


class GetUserImgFailed(AniException):
    code = 'get_user_image_failed'
    msg = _('Get User Image Failed')
