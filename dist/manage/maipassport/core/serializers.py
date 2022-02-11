from django.utils.translation import ugettext_lazy as _
from rest_framework import serializers

from maipassport.citadel.services import logger_writer
from maipassport.users.models import AppUser
from maipassport.users.services import AppUserServices
from maipassport.citadel.models import Role, User
from maipassport.core.exceptions import (UserNotExists, AccountCantReset, AccountAlreadyBindPhone, PhoneFormatWrong,
                                         PhoneAlreadyExists)


class OtpSendSerializer(serializers.Serializer):

    account = serializers.CharField(required=False)
    email = serializers.EmailField(required=False)
    phone = serializers.CharField(required=False)
    device_id = serializers.CharField(max_length=40)
    otp_text_type = serializers.CharField(max_length=40, required=False, default='APP')
    otp_type = serializers.CharField(max_length=40, required=False, default='NEW')

    # def validate_email(self, value):
    #     clean_value = WalletUserSerializer().validate_email(value)
    #     if not WalletUser.objects.filter(email=value).exists():
    #         #raise serializers.ValidationError(_('Email does not exists.'), code='email_does_not_exists')
    #         raise EmailNotExist
    #     return clean_value

    # def validate_phone(self, value):
    #     clean_value = WalletUserSerializer().validate_phone(value)
    #     if not WalletUser.objects.filter(phone=clean_value).exists():
    #         raise serializers.ValidationError(_('Phone number does not exists.'), code='phone_number_does_not_exists')
    #     return clean_value

    def validate(self, validated_data):
        logger_writer('SYSTEM', 'info', 'VALIDATE', f'{validated_data}')
        # account -> phone 20210607 by Alan Yang
        if 'phone' in validated_data:
            # case: admin
            if User.objects.filter(username=validated_data['phone'], role__name=Role.ADMIN).exists():
                raise AccountCantReset

            app_user = AppUser.objects.select_related('auth_user').filter(
                auth_user__username=validated_data['phone'])
            logger_writer('SYSTEM', 'info', 'VALIDATE', f'app_user: {app_user}')
            # if not app_user.exists():
            #     raise UserNotExists
            # else:
            app_user = app_user.first()
            if 'phone' in validated_data:
                logger_writer('SYSTEM', 'info', 'VALIDATE', f'{validated_data["phone"]}')
                if validated_data['otp_type'] == 'NEW':
                    # if app_user.phone:
                    #     raise AccountAlreadyBindPhone

                    try:
                        phone_dict = AppUserServices.change_phone(validated_data['phone'])
                    except PhoneFormatWrong:
                        logger_writer('SYSTEM', 'error', 'VALIDATE', f'phone format wrong')
                        raise PhoneFormatWrong
                    else:
                        if AppUser.objects.filter(phone=phone_dict['fix_phone']).exists():
                            raise PhoneAlreadyExists
                        validated_data['phone'] = phone_dict['fix_phone']
                        logger_writer('SYSTEM', 'error', 'VALIDATE', f'{validated_data["phone"]} = {phone_dict["fix_phone"]}')
                else:
                    try:
                        phone_dict = AppUserServices.change_phone(validated_data['phone'])
                    except PhoneFormatWrong:
                        logger_writer('SYSTEM', 'error', 'VALIDATE', f'phone format wrong')
                        raise PhoneFormatWrong
                    else:
                        validated_data['phone'] = phone_dict['fix_phone']
                        logger_writer('SYSTEM', 'error', 'VALIDATE', f'{validated_data["phone"]} = {phone_dict["fix_phone"]}')
            else:
                if app_user.phone:
                    validated_data['phone'] = app_user.phone
                if app_user.email:
                    validated_data['email'] = app_user.email

        return validated_data
