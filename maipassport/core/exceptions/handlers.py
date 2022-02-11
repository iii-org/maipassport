from django.core.exceptions import PermissionDenied
from django.http import Http404
from django.utils.encoding import force_text
from rest_framework import exceptions
from rest_framework.response import Response
from rest_framework.views import set_rollback

from maipassport.core.exceptions.base import AniException
from maipassport.core.exceptions.otp import OtpWrong


def recursive_transform_error_detail(data, upper_data=None, key=None):
    """
    Transform ErrorDetail object to our custom format.
    """
    if isinstance(data, list):
        for i, _ in enumerate(data):
            recursive_transform_error_detail(_, upper_data=data, key=i)
    elif isinstance(data, dict):
        for k, v in data.items():
            recursive_transform_error_detail(v, upper_data=data, key=k)

    elif isinstance(data, exceptions.ErrorDetail):
        result_dict = {
            'code': data.code,
            'message': data
        }
        if isinstance(upper_data, list):
            upper_data[key] = result_dict
        elif isinstance(upper_data, dict):
            upper_data[key] = result_dict


def ani_exception_handler(exc, context):
    """
    Refer to rest_framework.views.exception_handler.

    """
    if isinstance(exc, Http404):
        exc = exceptions.NotFound()
    elif isinstance(exc, PermissionDenied):
        exc = exceptions.PermissionDenied()
    elif isinstance(exc, OtpWrong):
        return Response(
            data={
                'http_code': exc.http_code,
                'attempts_remaining': exc.attempts_remaining,
                'error': {
                    'code': exc.code,
                    'message': force_text(exc.msg)
                }
            },
            status=exc.http_code
        )
    elif isinstance(exc, AniException):
        return Response(
            data={
                'http_code': exc.http_code,
                'error': {
                    'code': exc.code,
                    'message': force_text(exc.msg)
                }
            },
            status=exc.http_code
        )

    if isinstance(exc, exceptions.APIException):
        headers = {}
        if getattr(exc, 'auth_header', None):
            headers['WWW-Authenticate'] = exc.auth_header
        if getattr(exc, 'wait', None):
            headers['Retry-After'] = '%d' % exc.wait

        if isinstance(exc.detail, (dict, list)):
            # ani custom format
            recursive_transform_error_detail(exc.detail)
            data = {
                'http_code': exc.status_code,
                'errors': exc.detail
            }
        else:
            # ani custom format
            data = {
                'http_code': exc.status_code,
                'error': {
                    'code': exc.detail.code,
                    'message': exc.detail
                }
            }

        set_rollback()

        return Response(data, status=exc.status_code, headers=headers)

    return None
