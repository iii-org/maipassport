from django.utils.translation import ugettext_lazy as _
from rest_framework import status

from maipassport.core.exceptions.base import AniException


class InvalidSignature(AniException):
    """
    For DigitalSignatureVerifyMiddleware.
    """
    http_code = status.HTTP_400_BAD_REQUEST
    code = 'invalid_signature'
    msg = _('The signature value specified in the request is invalid.')


class InvalidToken(AniException):
    """
    For TokenParseMiddleware.
    """
    http_code = status.HTTP_403_FORBIDDEN
    code = 'invalid_token'
    msg = _('The access token value specified in the request is invalid.')


class InvalidClientVersion(AniException):

    http_code = status.HTTP_400_BAD_REQUEST
    code = 'invalid_client_version'
    msg = _('The client version specified in the request is invalid.')


class InvalidClientId(AniException):

    http_code = status.HTTP_400_BAD_REQUEST
    code = 'invalid_client_id'
    msg = _('The client id specified in the request is invalid.')


class UpgradeRequired(AniException):

    http_code = 426
    code = 'upgrade_required'
    msg = _('Your app version is out of date, please upgrade to latest version.')


class ServiceUnavailable(AniException):

    http_code = status.HTTP_503_SERVICE_UNAVAILABLE
    code = 'service_unavailable'
    msg = _('Service is under maintenance.')


class AuthenticationFailed(AniException):
    """
    For UtsCheckMiddleware.
    """
    http_code = status.HTTP_403_FORBIDDEN
    code = 'authentication_failed'
    msg = _('Server failed to authenticate the request.')


class ClientTimeError(AniException):
    """
    For UtsCheckMiddleware.
    """
    http_code = status.HTTP_403_FORBIDDEN
    code = 'client_time_error'
    msg = _('Client time is way too different from server time.')
