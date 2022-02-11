import re, os
import json
import qrcode
from urllib.parse import urlencode
from base64 import b64encode
import requests
from celery_once import QueueOnce
from PIL import Image
import uuid
import boto3
from storages.backends.s3boto3 import S3Boto3Storage

from datetime import datetime, timedelta
from django.db import transaction
from django.conf import settings
from django.utils.six import BytesIO

from maipassport.users.models import AppUser
from maipassport import celery_app
from maipassport.citadel.models import User, Role
from maipassport.citadel.services import logger_writer, get_image
from maipassport.core.exceptions import UserAlreadyExists, CreateAppUserFailed, PhoneFormatWrong, RequestFail
from maipassport.core.utils import (aes_enc_data, aes_crypto_js_zero_padding, utc_time_to_local_time,
                                    get_utc_format_today)
from maipassport.records.models import QuestionnaireField
from maipassport.users.models import AppUser, HealthCode


class AppUserServices:

    @staticmethod
    def create_app_user(user_account, password, user_pub_key):
        if User.objects.filter(username=user_account).exists():
            raise UserAlreadyExists
        with transaction.atomic():
            try:
                auth_user = User.objects.create_user(username=user_account, password=password, is_active=True)
                auth_user.role_set.set([Role.objects.get(name='User')])

                app_user = AppUser.objects.create(auth_user=auth_user, public_sign_key=user_pub_key)
                HealthCode.objects.create(app_user=app_user)
                result = AppUserServices.upload_user_qrcode(app_user.pub_id, 'USER')
                app_user.qr_code_upload = result
                app_user.save()
            except Exception as e:
                logger_writer('SYSTEM', 'error', 'CREATE_APP_USER', f'Create app user got error: {str(e)}')
                raise CreateAppUserFailed

        return app_user

    @staticmethod
    def change_phone(phone):
        # 手機目前只給台灣註冊
        if not re.match('^\d+ \d+$', phone):
            if phone[0:2] == '09':
                phone = f'886 {phone[1:]}'
        if not re.match('^\d+ \d+$', phone):
            raise PhoneFormatWrong
        dial_code = phone.split()[0]
        phone_num = phone.split()[1]
        # if f'+{dial_code}' not in CountryCode.dial_code_list():
        #     raise serializers.ValidationError(_('Phone dial code is not valid.'))
        if f'+{dial_code}' != '+886':
            raise PhoneFormatWrong
        else:
            if len(phone_num) == 10 and phone_num[0] == '0':
                phone_num = phone_num[1:]
            elif len(phone_num) == 9 and phone_num[0] == '9':
                phone_num = phone_num
            else:
                raise PhoneFormatWrong
        # if f'+{dial_code}' == '+86':
        #     if len(phone_num) != 11:
        #         raise serializers.ValidationError(_('Phone format is not valid.'))
        #     else:
        #         phone_num = phone_num

        return {
            'dial_code': dial_code,
            'phone': phone,
            'fix_phone': '{} {}'.format(dial_code, phone_num)
        }

    @staticmethod
    def check_phone(phone):
        # 手機目前只給台灣註冊
        phone = phone.replace('-', '')
        if len(phone) > 10:
            raise PhoneFormatWrong
        if not re.match('^\d\d\d\d\d\d\d\d\d\d', phone):
            raise PhoneFormatWrong
        if phone[0:2] != '09':
            raise PhoneFormatWrong
        return phone

    # @staticmethod
    # @celery_app.task(base=QueueOnce, once={'graceful': True})
    # def update_user_b64_pic(pub_id):
    #     try:
    #         app_user = AppUser.objects.filter(pub_id=pub_id)
    #         if app_user.exists():
    #             app_user = app_user.first()
    #             if app_user.user_picture:
    #                 b64_str = get_image(app_user.user_picture)
    #                 app_user.user_picture_b64 = b64_str
    #                 app_user.save(update_fields=['user_picture_b64', 'modified'])
    #                 logger_writer('SYSTEM', 'info', 'UPDATE_USER_B64_PIC', f'Update user base64 picture success')
    #             else:
    #                 logger_writer('SYSTEM', 'error', 'UPDATE_USER_B64_PIC', f"User don't have picture")
    #         else:
    #             logger_writer('SYSTEM', 'error', 'UPDATE_USER_B64_PIC', f'User not exists')
    #     except Exception as e:
    #         logger_writer('SYSTEM', 'error', 'UPDATE_USER_B64_PIC', f'Update user base64 picture error: {str(e)}')

    @staticmethod
    def reset_health_code():
        app_user_list = AppUser.objects.select_related('healthcode').all()
        stime, etime = get_utc_format_today()
        for app_user in app_user_list:
            if app_user.usercompanytable_set.select_related('company').filter(
                    employed=True, company__name='資訊工業策進會').exists():
                app_user.healthcode.code = HealthCode.WAIT_MEASURE
                app_user.healthcode.save(update_fields=['code', 'modified'])
            elif not app_user.questionnaire_set.filter(
                    field_name__type=QuestionnaireField.HEALTH, modified__range=(stime, etime)).exists():
                app_user.healthcode.code = HealthCode.UNFILLED
                app_user.healthcode.save(update_fields=['code', 'modified'])

    @staticmethod
    def send_req(request_method, api_url, send_header, dict_data):
        # query_string = urlencode(dict_data)
        if request_method == 'POST':
            response = requests.post(
                api_url,
                headers=send_header,
                data=json.dumps(dict_data),
            )
        else:
            response = requests.get(
                api_url,
                headers=send_header,
            )
        # if response.status_code == 204:
        #     return True
        # elif response.status_code == 403:
        #     return response.json()
        if response.status_code == 400:
            return False
        else:
            result = response.json()
            return result
            # if 'error' in result:
            #     logger_writer('SYSTEM', 'error', 'GET_ACCOUNT',
            #                   f'Offline result: code {response.status_code}, message: {result}')
            #     raise RequestFail
            # else:
            #     return result

    @staticmethod
    @celery_app.task(base=QueueOnce, once={'graceful': True})
    def upload_to_aws(file_path, content_file):

        s3 = boto3.resource('s3',
                            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
                            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY)
        bucket = s3.Bucket('maipasscode-doc-file')
        bucket.upload_fileobj(content_file, file_path, ExtraArgs={'ACL': 'public-read'})

        signed_url = bucket.meta.client.generate_presigned_url('get_object',
                                                               Params={
                                                                   'Bucket': bucket.name,
                                                                   'Key': file_path
                                                               },
                                                               ExpiresIn=360)
        url = S3Boto3Storage()._strip_signing_parameters(signed_url)
        return url

    # for iii
    @staticmethod
    def iii_user_profile(iii_user_id):
        api_url = settings.III_URL + '/api/health/personinfo'
        timestamp = (utc_time_to_local_time(datetime.now()) + timedelta(seconds=5)).strftime('%Y%m%d%H%M%S')
        content = aes_crypto_js_zero_padding('{}\t{}'.format(iii_user_id, timestamp))
        enc_data = aes_enc_data(content, settings.III_ENC_IV.encode())
        dict_data = {
            'token': b64encode(enc_data).decode()
        }
        try:
            rep_data = AppUserServices.send_req('POST', api_url, {'Content-Type': 'application/json'}, dict_data)
        except Exception as e:
            raise e
        else:
            return rep_data

    @staticmethod
    def upload_qr_to_s3(file_path, upload_file_path, color, frame=False):
        if frame:
            img_f = Image.open(file_path)
            old_size = img_f.size
            new_size = (old_size[0] + 10, old_size[1] + 10)
            new_im = Image.new("RGB", new_size, color=color)
            new_im.paste(img_f, (int((new_size[0] - old_size[0]) / 2),
                                 int((new_size[1] - old_size[1]) / 2)))
            new_im.save(file_path)
        s3 = boto3.resource('s3',
                            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
                            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY)
        bucket = s3.Bucket('maipasscode-qr-image')
        # file_path = f'media/{user_id}/qr_code/{user_id}.png'
        with open(settings.ROOT_DIR.path(file_path), 'rb') as f:
            bucket.put_object(Key=upload_file_path, Body=f)
        client = boto3.client('s3', aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
                              aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY)
        client.put_object_acl(ACL='public-read', Bucket=bucket.name, Key=upload_file_path)
        prove_signed_url = bucket.meta.client.generate_presigned_url('get_object',
                                                                     Params={
                                                                         'Bucket': bucket.name,
                                                                         'Key': file_path
                                                                     },
                                                                     ExpiresIn=360)
        url = S3Boto3Storage()._strip_signing_parameters(prove_signed_url)

    @staticmethod
    def upload_user_qrcode(qr_id, qr_type):
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_H,
            box_size=5,
            border=5
        )
        if qr_type == 'USER':
            qr.add_data(f'USER__{qr_id}')
        else:
            qr.add_data(f'ADDORG__{qr_id}')
        qr.make()
        img = qr.make_image(fill_color='black')

        buf = BytesIO()
        img.save(buf)
        file_path = f'maipassport/static/app_web/qr_code/{qr_id}.png'
        if qr_type == 'USER':
            # black
            upload_file_path = f'media/{qr_id}/qr_code/{qr_id}_black.png'
            with open(settings.ROOT_DIR.path(file_path), 'wb') as file:
                file.write(buf.getvalue())
            # os.remove(settings.ROOT_DIR.path(file_path))
            AppUserServices.upload_qr_to_s3(file_path, upload_file_path, 'black', True)

            # red
            upload_file_path = f'media/{qr_id}/qr_code/{qr_id}_red.png'
            with open(settings.ROOT_DIR.path(file_path), 'wb') as file:
                file.write(buf.getvalue())
            # os.remove(settings.ROOT_DIR.path(file_path))
            AppUserServices.upload_qr_to_s3(file_path, upload_file_path, 'red', True)

            # green
            upload_file_path = f'media/{qr_id}/qr_code/{qr_id}_green.png'
            with open(settings.ROOT_DIR.path(file_path), 'wb') as file:
                file.write(buf.getvalue())
            # os.remove(settings.ROOT_DIR.path(file_path))
            AppUserServices.upload_qr_to_s3(file_path, upload_file_path, 'green', True)

            # orange
            upload_file_path = f'media/{qr_id}/qr_code/{qr_id}_orange.png'
            with open(settings.ROOT_DIR.path(file_path), 'wb') as file:
                file.write(buf.getvalue())
            # os.remove(settings.ROOT_DIR.path(file_path))
            AppUserServices.upload_qr_to_s3(file_path, upload_file_path, 'orange', True)
        else:
            # black
            upload_file_path = f'media/{qr_id}/qr_code/{qr_id}.png'
            with open(settings.ROOT_DIR.path(file_path), 'wb') as file:
                file.write(buf.getvalue())
            # os.remove(settings.ROOT_DIR.path(file_path))
            AppUserServices.upload_qr_to_s3(file_path, upload_file_path, 'black')
        os.remove(settings.ROOT_DIR.path(file_path))
        return True
