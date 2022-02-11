import logging
import json
from datetime import datetime, timedelta
from base64 import b64decode, b64encode

from django.utils.deprecation import MiddlewareMixin
from django.utils.translation import activate

from maipassport.citadel.services import logger_writer
from maipassport.core.responses import (ResponseAuthenticationFailed, ResponseInvalidToken,
                                         ResponseInvalidSignature, ResponseClientTimeError,
                                         ResponseUpgradeRequired, ResponseServiceUnavailable,
                                         ResponseInvalidClientVersion, ResponseInvalidClientId)
from maipassport.core.decorators import django_admin_exempt

from Crypto.Hash import SHA256
from Crypto.Signature import pkcs1_15

from maipassport.core.utils import get_timestamp, des_enc_data
from maipassport.users.models import TYPE_APP_USER, TYPE_DEVICE_USER, AppUser, DeviceUser


logger = logging.getLogger(__name__)


class VersionCheckMiddleware(MiddlewareMixin):

    @django_admin_exempt
    def process_request(self, request):

        app_id = request.META.get('HTTP_X_CLIENT_ID')
        version = request.META.get('HTTP_X_CLIENT_VERSION')

        if not app_id:
            return ResponseInvalidClientId()

        raw_token = request.META.get('HTTP_X_MAI_TOKEN', None)
        if not raw_token:
            logging.warning('[MIDDLEWARE] missing token')
            return ResponseInvalidToken()

        try:
            user_type, token = raw_token.split()
        except ValueError:
            logging.warning('[MIDDLEWARE] token format error')
            return ResponseInvalidToken()
        else:
            if user_type not in {'WebUser', 'DeviceUser'}:
                logging.warning(f'[MIDDLEWARE] user type {user_type} wrong')
                return ResponseInvalidToken()

        # if user_type == 'Ec':
        #     if not ECUser.objects.filter(pub_id=app_id).exists():
        #         logging.warning(f'[MIDDLEWARE] can not find ec pub_id in database')
        #         return ResponseInvalidToken()
        #     else:
        #         return
        #
        # version_info_dict = VersionService(app_id).get()
        # if not version_info_dict:
        #     logging.warning(f'[MIDDLEWARE] error in version check with pub_id ')
        #     return ResponseInvalidClientId()
        #
        # if not version:
        #     return ResponseInvalidClientVersion()
        #
        # try:
        #     version = float(version)
        # except ValueError:
        #     return ResponseInvalidClientVersion()
        #
        # if not version_info_dict['service_operable']:
        #     return ResponseServiceUnavailable(version_info_dict['service_message'])
        #
        # if version < float(version_info_dict['upgrade_before']):
        #     return ResponseUpgradeRequired(version_info_dict['upgrade_message'])


class TokenParseMiddleware(MiddlewareMixin):

    @django_admin_exempt
    def process_request(self, request):

        raw_token = request.META.get('HTTP_X_MAI_TOKEN', None)
        logger_writer('SYSTEM', 'info', 'RAW TOKEN', f'{raw_token}')
        if not raw_token:
            return ResponseInvalidToken()

        try:
            user_type, token = raw_token.split()
        except ValueError:
            return ResponseInvalidToken()
        else:
            if user_type not in {'WebUser', 'DeviceUser'}:
                return ResponseInvalidToken()
            if user_type == 'WebUser':
                try:
                    app_user = (
                        AppUser.objects
                            # .get(id=token_cache_object.id)
                            .get(api_token=token)
                    )
                except AppUser.DoesNotExist:
                    return ResponseInvalidToken()
                else:
                    user = app_user
                    user_type = TYPE_APP_USER
                    request.user_object = user
                    request.user_type = user_type
                    request.token = token
            elif user_type == 'DeviceUser':
                try:
                    logger_writer('SYSTEM', 'info', 'CHECK OTP', f'{token}')
                    logger_writer('SYSTEM', 'info', 'DU OTP', f'{DeviceUser.api_token}')
                    device_user = (
                        DeviceUser.objects
                            # .get(id=token_cache_object.id)
                            .get(api_token=token)
                    )
                except AppUser.DoesNotExist:
                    return ResponseInvalidToken()
                else:
                    user = device_user
                    user_type = TYPE_DEVICE_USER
                    request.user_object = user
                    request.user_type = user_type
                    request.token = token


class UtsCheckMiddleware(MiddlewareMixin):

    @django_admin_exempt
    def process_request(self, request):
        if request.user_type in [TYPE_APP_USER, TYPE_DEVICE_USER]:
            if request.method in {'GET', 'DELETE'}:
                uts = request.GET.get('uts')
            else:
                if request.content_type == 'application/json':
                    request_body = request.body if request.body else "{}"
                    try:
                        data = json.loads(request_body)
                    except ValueError:
                        logging.warning(f'[MIDDLEWARE] json load error ')
                        return ResponseAuthenticationFailed()
                    else:
                        uts = data.get('uts')
                else:
                    logging.warning(f'[MIDDLEWARE] need json format')
                    return ResponseAuthenticationFailed()
            if not uts:
                logging.warning(f'[MIDDLEWARE] uts get error')
                return ResponseAuthenticationFailed()
            else:
                try:
                    uts = int(uts)
                except (ValueError, TypeError):
                    logging.warning(f'[MIDDLEWARE] uts value error')
                    return ResponseAuthenticationFailed()

            uts_now = get_timestamp()
            try:
                diff_seconds = abs(uts_now - uts) / 1000
            except ValueError:
                logging.warning(f'[MIDDLEWARE] uts value error ')
                return ResponseAuthenticationFailed()

            if diff_seconds > 1200:
                return ResponseClientTimeError()
            request.uts = uts
            return
        else:
            logging.warning(f'[MIDDLEWARE] uts value error ')
            return ResponseAuthenticationFailed()


class LanguageCheckMiddleware(MiddlewareMixin):

    # @django_admin_exempt
    def process_request(self, request):
        lang_list = ['zh_Hant', 'en-us']
        lang = 'zh_Hant'
        if (hasattr(request, 'user') and hasattr(request.user, 'appuser') and
                'language' in request.user.appuser.user_detail):
            lang = request.user.appuser.user_detail['language']
        elif hasattr(request, 'user_object'):
            if hasattr(request.user_object, 'user_detail') and 'language' in request.user_object.user_detail:
                lang = request.user_object.user_detail['language']
            else:
                lang = 'zh_Hant'
        elif request.COOKIES.get('language'):
            lang = request.COOKIES.get('language')
        elif request.META.get('HTTP_ACCEPT_LANGUAGE', ['en-US', ]):
            if request.META.get('HTTP_ACCEPT_LANGUAGE', ['en-US', ]) == 'zh-tw':
                lang = 'zh_Hant'
            elif 'zh-TW' in request.META.get('HTTP_ACCEPT_LANGUAGE', ['en-US', ]):
                lang = 'zh_Hant'
            else:
                lang = 'en-us'

        if request.method in {'GET', 'DELETE'}:
            url_lang = request.GET.get('language')
            if url_lang and url_lang in lang_list and url_lang != lang:
                lang = url_lang
        elif request.content_type == 'application/json':
            request_body = request.body if request.body else "{}"
            try:
                data = json.loads(request_body)
            except ValueError:
                logging.warning(f'[MIDDLEWARE] json load error ')
            else:
                url_lang = request.POST.get('language')
                if url_lang and url_lang in lang_list and url_lang != lang:
                    lang = url_lang

        if lang not in ['zh_Hant', 'en-us']:
            lang = 'zh_Hant'

        if hasattr(request.user, 'appuser'):
            request.user.appuser.user_detail['language'] = lang
            request.user.appuser.save()
        if hasattr(request, 'user_object') and hasattr(request.user_object, 'user_detail'):
            request.user_object.user_detail['language'] = lang
            request.user_object.save()
        if '/msg_api' in request.path or '/passboard' in request.path:
            lang = 'zh_Hant'
        activate(lang)
        request.session['language'] = lang
        return


    def process_response(self, request, response):
        if request.session.get('language'):
            lang = request.session.pop('language')
            cookie_lang = request.COOKIES.get('language')
            if lang and lang != cookie_lang:
                response.set_cookie("language", lang, max_age=3600)
        return response


# class DigitalSignatureVerifyMiddleware(MiddlewareMixin):
#
#     @django_admin_exempt
#     def process_request(self, request):
#         # 壓測
#         if hasattr(request, 'user_object'):
#             if hasattr(request.user_object, 'name'):
#                 if request.user_object.name == 'mai_user' and request.user_object.pub_id == '0LUDkneAfPaTguneiinY':
#                     return None
#             if hasattr(request.user_object, 'nick_name'):
#                 if request.user_object.nick_name == 'mai_user' and request.user_object.pub_id == '0LUDkneAfPaTguneiinY':
#                     return None
#             if hasattr(request.user_object, 'ec_name'):
#                 if request.user_object.ec_name == 'mai_user' and request.user_object.pub_id == '0LUDkneAfPaTguneiinY':
#                     return None
#
#         signature = request.META.get('HTTP_X_ANI_SIGNATURE')
#         if not signature:
#             return ResponseInvalidSignature()
#
#         # TokenCacheObject = namedtuple('TokenCacheObject', ['id', 'public_sign_key', 'uts'])
#         token_cache_object = request.token_cache_object
#
#         if request.method in {'GET', 'DELETE'}:
#             get_dict = dict(request.GET)
#             sorted_get_dict = {k: v[0] for k, v in sorted(get_dict.items())}
#             sorted_query_string = "&".join(f"{k}={v}" for k, v in sorted_get_dict.items())
#             msg_hash = SHA256.new(b64encode(sorted_query_string.encode()))
#         else:
#             msg_hash = SHA256.new(b64encode(request.body))
#
#         rsa_public_key = rsa_import_key_string(token_cache_object.public_sign_key)
#         try:
#             pkcs1_15.new(rsa_public_key).verify(msg_hash, b64decode(signature))
#         except (ValueError, TypeError):
#             return ResponseInvalidSignature()
#         else:
#             return None
#
#

class CookieSettingMiddleware(MiddlewareMixin):

    def process_response(self, request, response):
        if hasattr(request, 'set_account'):
            if request.set_account:
                try:
                    account = des_enc_data(request.POST.get('user_account')).decode()
                except Exception as e:
                    # TODO: log
                    pass
                else:
                    response.set_cookie('remember_account', account, expires=datetime.now() + timedelta(days=365))
            else:
                response.delete_cookie('remember_account')
        return response


class DigitalSignatureSignMiddleware(MiddlewareMixin):

    def process_response(self, request, response):
        # 壓測
        # if hasattr(request, 'user_object'):
        #     if hasattr(request.user_object, 'name'):
        #         if request.user_object.name == 'mai_user' and request.user_object.pub_id == '0LUDkneAfPaTguneiinY':
        #             return response
        #     if hasattr(request.user_object, 'nick_name'):
        #         if request.user_object.nick_name == 'mai_user' and request.user_object.pub_id == '0LUDkneAfPaTguneiinY':
        #             return response
        #     if hasattr(request.user_object, 'ec_name'):
        #         if request.user_object.ec_name == 'mai_user' and request.user_object.pub_id == '0LUDkneAfPaTguneiinY':
        #             return response

        if hasattr(response, 'content') and response.content:
            # msg_hash = SHA256.new(b64encode(response.content))
            # signature = b64encode(pkcs1_15.new(rsa_sign_key).sign(msg_hash))
            # response['X-ANI-Signature'] = signature
            pass

        return response
#
#
# class ElasticLogMiddleware(MiddlewareMixin):
#     """
#     The action name will be stored in ElasticSearch, which should not be modified.
#     """
#     action_map = {
#         "GET:echo": "get_echo",
#         "PUT:user-change-phone": "change_phone",
#         "PUT:user-change-password": "change_password",
#         "PUT:user-reset-password": "reset_password",
#         "POST:transfer-list": "create_exchange",
#         "POST:cash_in-list": "create_cash_in",
#         "POST:cash_out-list": "create_cash_out"
#     }
#
#     def process_request(self, request):
#         request.initial_body = request.body
#
#     def process_response(self, request, response):
#
#         resolver_match = request.resolver_match
#         if resolver_match:
#             action_key = f'{request.method}:{resolver_match.url_name}'
#             if action_key in self.action_map:
#                 action_name = self.action_map[action_key]
#                 # try:
#                 #     ElasticLogService.log(action_name, request, response)
#                 # except Exception:
#                 #     pass
#
#         return response
