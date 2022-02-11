import logging
import random
import time
import requests
import json
from collections import namedtuple
from base64 import b64encode
from email.message import EmailMessage
import smtplib, ssl

from django.conf import settings
from django.core.cache import cache
from django.core.mail import send_mail
from django.utils.translation import activate
from rest_framework.exceptions import Throttled

from maipassport.citadel.services import logger_writer
from maipassport.core.models import AutoPubIDField
from maipassport.core.exceptions import (OtpWrong, OtpExpired, OtpNoMoreAttempt, OtpLost, OtpSendEmailError,
                                         OtpSendTooClose)

import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)


OtpCacheData = namedtuple('OtpCacheData',
                          ['otp_index', 'otp_value', 'email', 'phone', 'retry_timestamp', 'expired_timestamp'])
                          # ['otp_index', 'otp_value', 'otp_target', 'expired_timestamp'])


class OtpService:

    def __init__(self, otp_id=None):

        if otp_id:
            self.otp_id = otp_id
            # self.has_sent = True
        else:
            self.otp_id = otp_id if otp_id else AutoPubIDField().create_pushid()
            # self.has_sent = False

        self.otp_data_key = f'otp:{self.otp_id}:data'
        self.otp_retry_limit_key = f'otp:{self.otp_id}:retry-limit'

    @classmethod
    def _send_aws_sms(cls, phone, msg):
        try:
            client = boto3.client('sns', aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
                                  aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
                                  region_name=settings.AWS_REGION)

            client.set_sms_attributes(
                attributes={
                    'DefaultSMSType': 'Transactional'
                }
            )

            client.publish(PhoneNumber=phone,
                           Message=msg)
        except ClientError as e:
            logger.critical(f'AWS SMS error: {e}', exc_info=True)

    @classmethod
    def _send_mitake_sms(cls, phone, msg):

        # 三竹目前僅支援台灣地區

        fix_phone = phone

        if phone[0:3] == '886':
            fix_phone = phone[3:]
        if fix_phone[0] == '0':
            fix_phone = fix_phone[1:]

        dict_data = cls.generate_mitake_sms_url(fix_phone, msg)
        logger.debug(f'send mitake sms start {time.time()}')

        # print(dict_data)

        headers = {
            'Content-Type': 'application/x-www-form-urlencoded;',
        }

        is_error = True

        try:
            response = requests.get(f'{settings.MITAKE_SMS_URL}', params=dict_data)

            if response.status_code in (200, 201, 202, 203, 204, 205, 206, 207, 208, 226):
                if ('statuscode=0' in response.text or 'statuscode=1' in response.text or
                     'statuscode=2' in response.text or 'statuscode=4' in response.text):
                    is_error = False
                    # logger.info(
                    #     f'send mitake sms success, phone={phone}, extra={msg}, {response.status_code}, {response.text}')
                    logger_writer('SYSTEM', 'info', 'SEND_MITAKE_SMS',
                                  f'Send OTP phone message to {phone} success.')
            if is_error:
                # logger.error(f'send mitake sms error, phone={phone}, extra={response.status_code}, {response.text}')
                logger_writer('SYSTEM', 'error', 'SEND_MITAKE_SMS',
                              f'send mitake sms error, phone={phone}, extra={response.status_code}, {response.text}.')

        except requests.exceptions.RequestException as e:
            # logger.error(f'send mitake sms error, phone={phone}, extra={e}')
            logger_writer('SYSTEM', 'error', 'SEND_MITAKE_SMS',
                          f'send mitake sms error, phone={phone}, extra={e}.')

        # logger.debug(f'send mitake sms end {time.time()}')

    @classmethod
    def generate_mitake_sms_url(cls, phone, msg):

        dict_data = {
            'username': settings.MITAKE_SMS_USERNAME,
            'password': settings.MITAKE_SMS_PASSWORD,
            'dstaddr': phone,
            'smbody': msg,
            'CharsetURL': 'UTF-8'
        }
        return dict_data

    @classmethod
    def generate_infobip_header(cls):

        b64_encoded = b64encode(bytes(f'{settings.INFOBIP_SMS_USERNAME}:{settings.INFOBIP_SMS_PASSWORD}', 'utf-8')) \
            .decode('ascii')
        headers = {
            'Authorization': f'Basic {b64_encoded}',
            'Content-Type': 'application/json'
        }
        return headers

    @classmethod
    def _send_infobip_sms(cls, phone, msg):

        logger.debug(f'send infobip sms start {time.time()}')

        headers = cls.generate_infobip_header()
        query_string = cls.generate_infobip_data(phone=phone, msg=msg)
        print(headers)
        print(query_string)

        is_error = True

        try:
            response = requests.post(f'{settings.INFOBIP_SMS_URL}', headers=headers,
                                     data=json.dumps(query_string))

            if response.status_code in (200, 201, 202, 203, 204, 205, 206, 207, 208, 226):

                if 'groupId' in response.text:
                    json_data = json.loads(response.text)
                    print(response.text)
                    status = json_data['messages'][0]['status']['groupId']
                    if status == 1 or status == 3:
                        is_error = False
                        logger.info(f'send infobip sms success, phone={phone}, extra={msg}, '
                                    f'{response.status_code}, {response.text}')

            if is_error:
                logger.error(f'send infobip sms error, phone={phone}, extra={response.status_code}, {response.text}')

        except requests.exceptions.RequestException as e:
            logger.error(f'send infobip sms error, phone={phone}, extra={e}')

        logger.debug(f'send infobip sms end {time.time()}')

    @classmethod
    def generate_infobip_data(cls, phone, msg):

        dict_data = {
            'to': phone,
            'text': msg,
        }
        return dict_data


    # @classmethod
    # def _send_otp_email(cls, email, otp_text):
    #     send_mail(f'{settings.PROJECT_NAME} verification code', otp_text,
    #               from_email=settings.DEFAULT_FROM_EMAIL, recipient_list=[email])
    #     return True

    @classmethod
    def _send_otp_email(cls, email, device_id, otp_title, otp_text):
        throttle = SMSThrottleService(device_id)
        if not throttle.allow_send():
            activate('en_US')
            raise Throttled(wait=throttle.wait())
        # TODO: will open when production
        # if settings.DEBUG:
        #     pass
        # else:
        #     send_mail(f'{settings.PROJECT_NAME} verification code', otp_text,
        #               from_email=settings.DEFAULT_FROM_EMAIL, recipient_list=[email])
        # send_mail(f'{settings.PROJECT_NAME} verification code', otp_text,
        #           from_email=settings.DEFAULT_FROM_EMAIL, recipient_list=[email])
        try:
            if settings.DEBUG:
                return True
            else:
                # TODO: django default tls is 1.1, but OFFICE365 must be 1.2
                # send_mail(f'{settings.PROJECT_NAME} verification code', otp_text,
                #           from_email=settings.DEFAULT_FROM_EMAIL, recipient_list=[email])
                send_result = SmtpSendMailService.smtp_send_mail(f'{settings.PROJECT_NAME} verification code',
                                                                 otp_text, to_mail=email)
                return send_result
        except:
            logger_writer('SYSTEM', 'error', 'OTP_SEND_MAIL',
                          f'Send OTP email to {email} Failed.')
            # return False
            return False

    @classmethod
    def _send_otp_sms(cls, normalized_phone, device_id, otp_text):
        # TODO: Not use
        throttle = SMSThrottleService(device_id)
        if not throttle.allow_send():
            activate('en_US')
            raise Throttled(wait=throttle.wait())
        # only send aws sms if DEBUG=False
        if settings.DEBUG:
            # cls._send_mitake_sms(normalized_phone, otp_text)
            pass
        else:
            if normalized_phone.split(' ')[0] == '886' or normalized_phone.split(' ')[0:1] == '09':
                cls._send_mitake_sms(normalized_phone, otp_text)
            # elif normalized_phone.split(' ')[0] == '86':
            #     cls._send_infobip_sms(normalized_phone, otp_text)
            # else:
            #     cls._send_aws_sms(normalized_phone, otp_text)
            else:
                logger_writer('SYSTEM', 'error', 'OTP_SEND_PHONE',
                              f'Send OTP phone {normalized_phone} not support.')
        # if normalized_phone.split(' ')[0] == '886':
        #     cls._send_mitake_sms(normalized_phone, otp_text)
        # # elif normalized_phone.split(' ')[0] == '86':
        # #     cls._send_infobip_sms(normalized_phone, otp_text)
        # # else:
        # #     cls._send_aws_sms(normalized_phone, otp_text)
        # else:
        #     logger_writer('SYSTEM', 'error', 'OTP_SEND_PHONE',
        #                   f'Send OTP phone {normalized_phone} not support.')

        return True

    @staticmethod
    def _generate_otp_value():
        return ''.join([str(random.randint(0, 9)) for _ in range(6)])

    def _set_cache(self, otp_index, otp_value, email=None, phone=None):

        now_timestamp = time.time()
        retry_timestamp = now_timestamp + 30
        expired_timestamp = now_timestamp + 180 + 30  # SMS might delay, so we add 30 seconds by default.
        if not email:
            email = 'null'
        if not phone:
            phone = 'null'
        otp_data = [otp_index, otp_value, email, phone, retry_timestamp, expired_timestamp]

        # set one hour cache
        cache.set(self.otp_data_key, otp_data, 60 * 60)
        cache.set(self.otp_retry_limit_key, 10, 60 * 60)

        return OtpCacheData(*otp_data)

    def get_cache(self):
        cache_result = cache.get(self.otp_data_key)
        if cache_result:
            return OtpCacheData(*cache_result)
        else:
            return None

    def delete_cache(self):
        cache.delete(self.otp_data_key)
        cache.delete(self.otp_retry_limit_key)

    def _decr_retry_limit(self):
        return cache.decr(self.otp_retry_limit_key)

    def _normalize_phone(self, phone):
        phone_no_white_space = phone.replace(' ', '')
        normalized_phone = f'+{phone_no_white_space}'
        return normalized_phone

    def send(self, device_id, email=None, phone=None, sys_name='APP'):
        # assert self.has_sent is False
        if not email and not phone:
            raise NotImplementedError
        otp_cache_object = self.get_cache()
        if otp_cache_object:
            if time.time() < otp_cache_object.retry_timestamp:
                if email and email == otp_cache_object.email:
                    raise OtpSendTooClose
                if phone and phone == otp_cache_object.phone:
                    raise OtpSendTooClose
            else:
                self.delete_cache()
                self.otp_id = AutoPubIDField().create_pushid()
                self.otp_data_key = f'otp:{self.otp_id}:data'
                self.otp_retry_limit_key = f'otp:{self.otp_id}:retry-limit'

        otp_value = self._generate_otp_value()
        # otp_text = f'{otp_value} is your {sys_name} verification code.'
        if sys_name == 'APP':
            otp_title = f'通行碼驗證碼'
            otp_text = f'【通行碼】您的驗證碼為{otp_value}'
        else:
            otp_title = f'健康通行人員防疫管理平台驗證碼'
            otp_text = f'【健康通行人員防疫管理平台】您的驗證碼為{otp_value}'

        if email:
            if not self._send_otp_email(email, device_id, otp_title, otp_text):
                raise OtpSendEmailError
        if phone:
            if not self._send_otp_sms(phone, device_id, otp_text):
                raise OtpSendEmailError
        self._set_cache(otp_index=device_id, otp_value=otp_value, email=email, phone=phone)

        # self._set_cache(otp_value, email, device_id)
        # self.has_sent = True  # flag to prevent sent otp twice
        return self.otp_id

    def resend(self):

        otp_cache_object = self.get_cache()
        if not otp_cache_object:
            raise OtpLost()
        else:
            new_otp_service = OtpService()
            # otp_cache_data = otp_cache_object.otp_index.split('_')
            if otp_cache_object.email == 'null':
                email = None
            else:
                email = otp_cache_object.email
            if otp_cache_object.phone == 'null':
                phone = None
            else:
                phone = otp_cache_object.phone
            self.delete_cache()
            new_otp_id = new_otp_service.send(device_id=otp_cache_object.otp_index,
                                              email=email, phone=phone)
        return new_otp_id

    def verify(self, value, verify_email=None, verify_phone=None):
        """
        :return: phone which is stored in OtpCacheData
        """

        otp_cache_object = self.get_cache()
        if not otp_cache_object:
            logger.error(f'error with no otp_cache_object, value')
            raise OtpLost()

        # Check suspicious action
        # if verify_phone:
        #     if verify_phone != otp_cache_object.phone:
        #         logger.warning(f'Suspicious operation to verify otp.'
        #                        f' verify_phone:{verify_phone} against otp_phone:{otp_cache_object.phone}')
        #         self.delete_cache()  # delete OTP cache, no more try.
        #         raise OtpLost()
        if verify_email:
            if verify_email != otp_cache_object.email:
                logger.warning(f'Suspicious operation to verify otp.'
                               f' verify_email:{verify_email} against otp_email:{otp_cache_object.email}')
                self.delete_cache()  # delete OTP cache, no more try.
                raise OtpLost()
        if verify_phone:
            if verify_phone != otp_cache_object.otp_index:
                logger.warning(f'Suspicious operation to verify otp.'
                               f' verify_phone:{verify_phone} against otp_email:{otp_cache_object.phone}')
                self.delete_cache()  # delete OTP cache, no more try.
                raise OtpLost()

        # Check expired time
        if time.time() > otp_cache_object.expired_timestamp:
            raise OtpExpired()

        # Check Retry time
        try:
            retry_limit = self._decr_retry_limit()
        except ValueError:
            logger.error(f'error with retry limit error, value')
            raise OtpLost()  # otp_retry_limit_key is lost
        else:
            if retry_limit < 0:
                raise OtpNoMoreAttempt()

        # Check OTP value.
        # TODO: Before production - delete 000000 which is for debug usage
        if settings.DEBUG:
            if value != otp_cache_object.otp_value and value != "000000":
                raise OtpWrong(retry_limit)
        else:
            if value != otp_cache_object.otp_value:
                raise OtpWrong(retry_limit)
        # if value != otp_cache_object.otp_value and value != "000000":
        #     raise OtpWrong(retry_limit)
        # otp_cache_data = otp_cache_object.otp_index.split('_')

        # if value != otp_cache_object.otp_value:
        #     raise OtpWrong(retry_limit)

        # Verify passed
        self.delete_cache()  # delete OTP cache

        # refresh sms throttle limit
        # normalized_phone = self._normalize_phone(otp_cache_object.email)
        throttle = SMSThrottleService(otp_cache_object.otp_index)
        throttle.refresh_throttle()

        # return otp_cache_object.phone
        return otp_cache_object.email, otp_cache_object.phone


class SMSThrottleService:
    """
    Refer to SimpleRateThrottle.
    """
    num_requests = 3  # limit count
    duration = 600  # second

    def __init__(self, device_id):
        # self.key = f'email:{email}'
        self.key = f'device_id:{device_id}'
    # def __init__(self, normalized_phone):
    #     self.key = f'sms:{normalized_phone}'

    def refresh_throttle(self):
        cache.delete(self.key)

    def allow_send(self):
        """
        Implement the check to see if the request should be throttled.

        On success calls `throttle_success`.
        On failure calls `throttle_failure`.
        """
        self.now = time.time()
        self.history = cache.get(self.key, [])

        # Drop any requests from the history which have now passed the
        # throttle duration
        while self.history and self.history[-1] <= self.now - self.duration:
            self.history.pop()
        if len(self.history) >= self.num_requests:
            return self.throttle_failure()
        return self.throttle_success()

    def throttle_success(self):
        """
        Inserts the current request's timestamp along with the key
        into the cache.
        """
        self.history.insert(0, self.now)
        cache.set(self.key, self.history, self.duration)
        return True

    def throttle_failure(self):
        """
        Called when a request to the API has failed due to throttling.
        """
        return False

    def wait(self):
        """
        Returns the recommended next request time in seconds.
        """
        if self.history:
            remaining_duration = self.duration - (self.now - self.history[-1])
        else:
            remaining_duration = self.duration

        available_requests = self.num_requests - len(self.history) + 1
        if available_requests <= 0:
            return None

        return remaining_duration / float(available_requests)


class SmtpSendMailService:

    @staticmethod
    def smtp_send_mail(subj, mail_content, to_mail, from_mail=None):
        if not from_mail:
            from_mail = settings.EMAIL_HOST_USER

        try:
            msg = EmailMessage()
            msg.set_content(mail_content)
            msg['Subject'] = subj
            msg['From'] = from_mail
            msg['To'] = to_mail
            smtp = smtplib.SMTP(settings.EMAIL_HOST, settings.EMAIL_PORT)
            ssl_protocol = ssl.SSLContext(ssl.PROTOCOL_TLSv1_2)
            # smtp.connect(host=settings.EMAIL_HOST, port=settings.EMAIL_PORT)
            smtp.starttls(context=ssl_protocol)
            smtp.login(settings.EMAIL_HOST_USER, settings.EMAIL_HOST_PASSWORD)
            smtp.send_message(msg)
        except Exception as e:
            logger_writer('SYSTEM', 'error', 'SMTP_SEND_MAIL',
                          f'Send email to {to_mail} Failed, error: {str(e)}.')
            return False
        else:
            return True
