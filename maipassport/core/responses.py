from django.http.response import JsonResponse

from maipassport.core.exceptions import (AuthenticationFailed, InvalidToken, InvalidSignature,
                                         InvalidClientVersion, InvalidClientId,
                                         UpgradeRequired, ServiceUnavailable, ClientTimeError)


def generate_response_from_middleware_exception(middleware_exception):
    """
    Function to generate custom response from custom exception.
    """
    def inner_func(msg=None):
        return JsonResponse(
            {
                'http_code': middleware_exception.http_code,
                'error': {
                    'code': middleware_exception.code,
                    'message': msg or middleware_exception.msg
                }
            },
            status=middleware_exception.http_code,
            content_type='application/vnd.ani.v1.wallet+json'
        )
    return inner_func


ResponseAuthenticationFailed = generate_response_from_middleware_exception(AuthenticationFailed)
ResponseInvalidToken = generate_response_from_middleware_exception(InvalidToken)
ResponseInvalidSignature = generate_response_from_middleware_exception(InvalidSignature)
ResponseInvalidClientVersion = generate_response_from_middleware_exception(InvalidClientVersion)
ResponseInvalidClientId = generate_response_from_middleware_exception(InvalidClientId)
ResponseUpgradeRequired = generate_response_from_middleware_exception(UpgradeRequired)
ResponseServiceUnavailable = generate_response_from_middleware_exception(ServiceUnavailable)
ResponseClientTimeError = generate_response_from_middleware_exception(ClientTimeError)
