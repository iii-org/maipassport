from django.utils.translation import ugettext_lazy as _

from rest_framework import status


class AniException(Exception):

    # the default http_code is 400 bad request
    http_code = status.HTTP_400_BAD_REQUEST

    code = 'base_exception'
    msg = _('common exception')

    def __init__(self, code=None, msg=None):
        if code:
            self.code = code
        if msg:
            self.msg = msg

    # @property
    # def code(self):
    #     raise NotImplementedError
    #
    # @property
    # def msg(self):
    #     raise NotImplementedError


class InvalidParameter(AniException):
    http_code = status.HTTP_400_BAD_REQUEST
    code = 'invalid_parameter'
    msg = _('One of the request parameters is not valid.')
