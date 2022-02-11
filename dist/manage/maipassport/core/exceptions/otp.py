from django.utils.translation import ugettext_lazy as _

from maipassport.core.exceptions.base import AniException


class OtpWrong(AniException):
    code = 'wrong_otp'
    msg = _('OTP value is not valid.')

    def __init__(self, attempts_remaining):
        self.attempts_remaining = attempts_remaining


class OtpExpired(AniException):
    code = 'otp_expired'
    msg = _('OTP is expired.')


class OtpNoMoreAttempt(AniException):
    code = 'no_more_otp_attempts'
    msg = _("There's no more OTP attempts left.")


class OtpLost(AniException):
    code = 'otp_lost'
    msg = _('OTP data is totally lost. Cannot resend OTP by otp_id.')


class OtpSendEmailError(AniException):
    code = 'otp_send_email_error'
    msg = _('OTP Send Email Error.')


class OtpSendTooClose(AniException):
    code = 'otp_send_too_close'
    msg = _('Send OTP times can not be too close.')


class OtpNoTarget(AniException):
    code = 'otp_no_target'
    msg = _('No phone or email set up to send OTP')

