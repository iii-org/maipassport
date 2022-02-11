from datetime import datetime, timedelta
from decimal import Decimal

from rest_framework.response import Response
from rest_framework.decorators import api_view
from rest_framework import status

from django.shortcuts import render, reverse
from django.conf import settings
from django.http import HttpResponseRedirect
from django.http import HttpResponse
from django.contrib import auth
from django.utils.translation import gettext_lazy as _
from django.db.models import Q

from linebot import (
    LineBotApi, WebhookHandler
)
from linebot.exceptions import (
    InvalidSignatureError
)
from linebot.models import (
    MessageEvent, TextMessage, TextSendMessage,
)

from maipassport.citadel.models import User
from maipassport.citadel.services import read_qr_code, logger_writer
from maipassport.core.exceptions import UserNotExists, PhoneFormatWrong
from maipassport.core.services import OtpService
from maipassport.core.utils import des_enc_data, get_utc_format_today, utc_time_to_local_time
from maipassport.companies.models import UserCompanyTable, Place, Company, AddRequest, AddCompanyTag, NewCompanyApply
from maipassport.records.models import (PlaceEntryRecord, Questionnaire, QuestionnaireField, ApproachRecord,
                                        HealthRecord, VisitorRegistration, AttendanceRecord)
from maipassport.records.services import GpsService
from maipassport.users.models import AppUser, HealthCode, token_generator, AttendanceStatus
from maipassport.users.services import AppUserServices

# channel_secret = os.getenv('LINE_CHANNEL_SECRET', None)
# channel_access_token = os.getenv('LINE_CHANNEL_ACCESS_TOKEN', None)
# if channel_secret is None or channel_access_token is None:
#     print('Specify LINE_CHANNEL_SECRET and LINE_CHANNEL_ACCESS_TOKEN as environment variables.')
#     sys.exit(1)

line_bot_api = LineBotApi('')
handler = WebhookHandler('')

QR_SCAN = 'QR_SCAN'
QR_SHOW = 'QR_SHOW'
HISTORY = 'HISTORY'
CLOCK_IN = 'CLOCK_IN'
DECLARATION = 'DECLARATION'
BIND_ACCOUNT = 'BIND_ACCOUNT'
USER_FILE = 'USER_FILE'
COM_REG = 'COM_REG'

func_list = [QR_SCAN, QR_SHOW, HISTORY, CLOCK_IN, DECLARATION, BIND_ACCOUNT, USER_FILE, COM_REG]

# return_data_base = {
#     'LIFF_REDIRECT_URL': settings.LIFF_REDIRECT_URL
# }


def get_return_data_base():
    return {'LIFF_REDIRECT_URL': settings.LIFF_REDIRECT_URL}


def get_liff_id(request):
    func_type = request.session.get('func_type')
    lang = request.session.get('language')
    if not request.session.get('LIFF_ID'):
        if func_type == QR_SHOW:
            if lang == 'en-us':
                request.session['LIFF_ID'] = settings.LIFF_ID_QR_SHOW_ENG
            else:
                request.session['LIFF_ID'] = settings.LIFF_ID_QR_SHOW
        elif func_type == HISTORY:
            if lang == 'en-us':
                request.session['LIFF_ID'] = settings.LIFF_ID_HISTORY_ENG
            else:
                request.session['LIFF_ID'] = settings.LIFF_ID_HISTORY
        elif func_type == DECLARATION:
            if lang == 'en-us':
                request.session['LIFF_ID'] = settings.LIFF_ID_DECLARATION_ENG
            else:
                request.session['LIFF_ID'] = settings.LIFF_ID_DECLARATION
        elif func_type == QR_SCAN:
            if lang == 'en-us':
                request.session['LIFF_ID'] = settings.LIFF_ID_QR_SCAN_ENG
            else:
                request.session['LIFF_ID'] = settings.LIFF_ID_QR_SCAN
        elif func_type == BIND_ACCOUNT:
            if lang == 'en-us':
                request.session['LIFF_ID'] = settings.LIFF_ID_BIND_ENG
            else:
                request.session['LIFF_ID'] = settings.LIFF_ID_BIND
        elif func_type == CLOCK_IN:
            if lang == 'en-us':
                request.session['LIFF_ID'] = settings.LIFF_ID_CLOCK_IN_ENG
            else:
                request.session['LIFF_ID'] = settings.LIFF_ID_CLOCK_IN
        elif func_type == USER_FILE:
            if lang == 'en-us':
                request.session['LIFF_ID'] = settings.LIFF_ID_USER_FILE_ENG
            else:
                request.session['LIFF_ID'] = settings.LIFF_ID_USER_FILE
        elif func_type == COM_REG:
            if lang == 'en-us':
                request.session['LIFF_ID'] = settings.LIFF_ID_COM_REG_ENG
            else:
                request.session['LIFF_ID'] = settings.LIFF_ID_COM_REG
        else:
            if lang == 'en-us':
                request.session['LIFF_ID'] = settings.LIFF_ID_QR_SHOW_ENG
            else:
                request.session['LIFF_ID'] = settings.LIFF_ID_QR_SHOW


def route_html(request):
    func_type = request.session.get('func_type')
    if not func_type or func_type not in func_list:
        return Response(status=status.HTTP_404_NOT_FOUND)
    else:
        if func_type == HISTORY:
            return HttpResponseRedirect(reverse('liff_history', kwargs={}))
        elif func_type == DECLARATION:
            return HttpResponseRedirect(reverse('liff_declaration', kwargs={}))
        elif func_type == QR_SCAN:
            return HttpResponseRedirect(reverse('liff_scan', kwargs={}))
            # return HttpResponseRedirect(reverse('liff_scan_test', kwargs={}))
        elif func_type == BIND_ACCOUNT:
            request.session['BIND'] = True
            return HttpResponseRedirect(reverse('liff_bind', kwargs={}))
        elif func_type == CLOCK_IN:
            return HttpResponseRedirect(reverse('liff_check_in', kwargs={}))
        elif func_type == USER_FILE:
            return HttpResponseRedirect(reverse('liff_personal_file', kwargs={}))
        elif func_type == COM_REG:
            return HttpResponseRedirect(reverse('liff_com_reg', kwargs={}))
        else:
            return HttpResponseRedirect(reverse('liff_qr_code', kwargs={}))


def liff_router(request):

    return_data = get_return_data_base().copy()
    if request.session.get('LIFF_ID'):
        request.session.pop('LIFF_ID')
    if request.method == 'GET':
        func_type = request.GET.get('func_type')
        if not func_type or func_type not in func_list:
            return Response(status=status.HTTP_404_NOT_FOUND)
        else:
            request.session['func_type'] = func_type

    if request.method == 'POST':
        # func_type = request.POST.get('func_type')
        func_type = request.session.get('func_type')
        if not func_type or func_type not in func_list:
            return Response(status=status.HTTP_404_NOT_FOUND)
        user_id = request.POST.get('user_id')
        device_os = request.POST.get('device_os')
        if user_id:
            enc_line_id = des_enc_data(user_id).decode()
            request.session['enc_line_id'] = enc_line_id
            if device_os:
                request.session['DEVICE'] = device_os
            if func_type == BIND_ACCOUNT:
                return route_html(request)
            if not AppUser.objects.filter(user_detail__line_id=enc_line_id).exists():
                return HttpResponseRedirect(reverse('liff_bind', kwargs={}))
            else:
                return route_html(request)
        else:
            return Response(status=status.HTTP_404_NOT_FOUND)
    get_liff_id(request)
    return render(request, 'line_liff/router.html', context=return_data)


def liff_bind_user(request):
    return_data = get_return_data_base().copy()
    if hasattr(request, 'user') and request.user.is_authenticated:
        enc_line_id = request.session.get('enc_line_id')
        if 'line_id' in request.user.appuser.user_detail and request.user.appuser.user_detail['line_id'] == enc_line_id:
            if request.session.get('BIND'):
                request.session.pop('BIND')
                get_liff_id(request)
                return render(request, 'line_liff/account_bind_completed.html', context=return_data)
            else:
                return route_html(request)

    if request.method == 'POST':
        enc_line_id = request.session.get('enc_line_id')
        account = request.POST.get('account')
        password = request.POST.get('password')
        web_latitude = request.POST.get('web_latitude')
        web_longitude = request.POST.get('web_longitude')
        if enc_line_id:
            user = auth.authenticate(request, username=account, password=password)
            if user is not None:
                auth.login(request, user)
                # TODO: 儲存token?
                user.appuser.api_token = token_generator()
                # user.appuser.user_detail['line_id'] = enc_line_id
                user.appuser.save(update_fields=['modified', 'user_detail'])
                request.app_user = user.appuser

                if web_latitude and web_longitude:
                    PlaceEntryRecord.objects.create(app_user=request.app_user,
                                                    location={
                                                        'latlon_longitude': web_latitude,
                                                        'latlon_latitude': web_longitude
                                                    })
                if request.session.get('BIND'):
                    request.session.pop('BIND')
                    get_liff_id(request)
                    return render(request, 'line_liff/account_bind_completed.html', context=return_data)
                else:
                    return route_html(request)
            else:
                return_data['message'] = _('Please check your username and password is correct')
        else:
            return Response(status=status.HTTP_404_NOT_FOUND)
    if request.session.get('message') and 'message' not in return_data:
        return_data['message'] = request.session.pop('message')
    get_liff_id(request)
    return render(request, 'line_liff/bind.html', context=return_data)


def liff_forget_pass(request):
    return_data = get_return_data_base().copy()
    if request.method == 'POST':
        account = request.POST.get('account')

        otp = request.POST.get('otp')
        otp_id = request.POST.get('otp_id')
        if account and otp and otp_id:
            app_user = AppUser.objects.filter(auth_user__username=account)
            if not app_user.exists():
                return_data['message'] = UserNotExists.msg
                return HttpResponseRedirect(reverse('forget_pass'))
            else:
                app_user = app_user.first()
            try:
                OtpService(otp_id).verify(otp, verify_phone=app_user.phone)
            except Exception as e:
                return_data['return_msg'] = _('Verify Otp Error, Please resend Otp')
            else:
                request.session['app_user'] = app_user
                return HttpResponseRedirect(reverse('liff_reset_pass'))
    get_liff_id(request)
    return render(request, 'line_liff/forget_password.html', context=return_data)


def liff_reset_pass(request):
    return_data = get_return_data_base().copy()
    if request.method == 'POST':
        app_user = request.session.get('app_user')
        password = request.POST.get('password')
        chkpassword = request.POST.get('chkpassword')
        if app_user and password and chkpassword:
            if password != chkpassword:
                return_data['message'] = _('The password and verify password not same')
                return render(request, 'line_liff/forget_password.html', context=return_data)
            else:
                # auth_user = User.objects.get(id=app_user.auth_user.id)
                app_user.auth_user.set_password(password)
                app_user.auth_user.save()
                request.session.pop('app_user')
                request.session['message'] = _('Password has been reset, please log in again')
                return HttpResponseRedirect(reverse('liff_bind'))
    get_liff_id(request)
    return render(request, 'line_liff/reset_password.html', context=return_data)


def liff_sign_up(request):
    return_data = get_return_data_base().copy()
    if 'message' in request.session:
        return_data['message'] = request.session['message']
    if request.method == 'POST':
        # account = request.POST.get('account')
        phone = request.POST.get('phone')
        user_real_name = request.POST.get('user_real_name')
        password = request.POST.get('inputPassword')
        chk_password = request.POST.get('confirmPassword')
        if phone and user_real_name and password and chk_password:
            try:
                # phone_dict = AppUserServices.change_phone(phone)
                phone = AppUserServices.check_phone(phone)
            except PhoneFormatWrong:
                # TODO: 電話格式錯誤
                return_data['message'] = _('Phone format error')
            else:
                if User.objects.filter(username=phone).exists():
                    # TODO: 帳號存在
                    # return_data['message'] = _('This account already exists')
                    return_data['message'] = _('This phone already exists')
                elif AppUser.objects.filter(phone=phone).exists():
                    # TODO: 電話已存在
                    return_data['message'] = _('This phone already exists')
                elif password != chk_password:
                    # TODO: 密碼跟確認密碼不相同
                    return_data['message'] = _('The password and verify password not same')
                else:
                    request.session['user_sign_up_data'] = {
                        # 'account': account,
                        'password': password,
                        'user_real_name': user_real_name,
                        'phone': phone,
                        # 'phone': phone_dict['phone'],
                        # 'fix_phone': phone_dict['fix_phone'],
                        # 'dial_code': phone_dict['dial_code']
                    }
                    # return render(request, 'app_web_n/sign_up_otc.html', context=return_data)
                    return HttpResponseRedirect(reverse('liff_sign_up_otp'))
    get_liff_id(request)
    return render(request, 'line_liff/sign_up.html', context=return_data)


def liff_sign_up_otp(request):
    return_data = get_return_data_base().copy()
    if not request.session.get('user_sign_up_data'):
        return HttpResponseRedirect(reverse('liff_sign_up'))
    else:
        user_sign_up_data = request.session.get('user_sign_up_data')
    return_data['phone'] = user_sign_up_data['phone']
    if request.method == 'POST':
        otp = request.POST.get('otp')
        otp_id = request.POST.get('otp_id')

        if otp and otp_id:
            try:
                OtpService(otp_id).verify(otp, verify_phone=user_sign_up_data['phone'])
            except Exception as e:
                return_data['message'] = _('Verify Otp Error, Please resend Otp')
                # return render(request, 'app_web_n/sign_up_otc.html', context=return_data)
            else:
                try:
                    app_user = AppUserServices.create_app_user(user_account=user_sign_up_data['phone'],
                                                               password=user_sign_up_data['password'],
                                                               user_pub_key=token_generator(8))
                except Exception as e:
                    # TODO: 建立失敗
                    request.session['message'] = _('Create User failed')
                    logger_writer('SYSTEM', 'error', 'LINE_SING_UP_OTP', f"Line Create User failed, err: {str(e)}")
                    return HttpResponseRedirect(reverse('liff_sign_up'))
                else:
                    app_user.phone = user_sign_up_data['phone']
                    app_user.save(update_fields=['phone', 'modified'])
                    app_user.auth_user.first_name = user_sign_up_data['user_real_name']
                    app_user.auth_user.save(update_fields=['first_name'])
                    request.session.pop('user_sign_up_data')
                    request.session['message'] = _('Registration success')
                    return HttpResponseRedirect(reverse('liff_bind'))
        else:
            return_data['message'] = _('Field missing')
    get_liff_id(request)
    return render(request, 'line_liff/sign_up_otc.html', context=return_data)


def login_required_liff(func):
    def wrapper(*args, **kwargs):
        request = args[0]
        enc_line_id = request.session.get('enc_line_id')
        if enc_line_id:
            app_user = AppUser.objects.filter(user_detail__line_id=enc_line_id)
            if not app_user.exists():
                return HttpResponseRedirect(reverse('liff_bind', kwargs={}))
            else:
                app_user = app_user.first()
                if not app_user.api_token or app_user.api_token == '':
                    app_user.api_token = token_generator()
                    app_user.save(update_fields=['api_token'])
                    app_user.refresh_from_db(fields=['api_token'])
                request.app_user = app_user
                request.user = app_user.auth_user
                user_company = request.app_user.usercompanytable_set.filter(default_show=True)
                if user_company.exists():
                    request.company = user_company.first().company
                return func(*args, **kwargs)
        else:
            return Response(status=status.HTTP_404_NOT_FOUND)
    return wrapper


@login_required_liff
def liff_qr_code(request):
    return_data = get_return_data_base().copy()
    app_user = request.app_user
    return_data['qr_data'] = f'USER__{app_user.pub_id}'
    return_data['health_detail'] = HealthCode.code_choice_detail()[request.app_user.healthcode.code]
    stime, etime = get_utc_format_today()
    health_code = app_user.healthcode.code
    if request.app_user.usercompanytable_set.select_related('company').filter(
            employed=True, company__name='資訊工業策進會').exists():
        # TODO: 屬於資策會的人此生有填過By pass
        if not Questionnaire.objects.filter(field_name__type=QuestionnaireField.HEALTH,
                                            app_user=request.app_user, ).exists():
            return_data['health_detail'] = _('Unfilled Form')
            return_data['color_type'] = 'black'
        elif health_code == HealthCode.WAIT_MEASURE:
            return_data['color_type'] = '1'
        elif health_code == HealthCode.NORMAL:
            return_data['color_type'] = '0'
        elif health_code in [HealthCode.DANGER, HealthCode.QUEST_DANGER]:
            return_data['color_type'] = '2'
            if health_code == HealthCode.DANGER:
                return_data['danger_reason'] = _('Alerted by measuring staff')
            else:
                return_data['danger_reason'] = _('High risk, may have recently gone abroad or have symptoms')
        else:
            return_data['color_type'] = 'none'
    else:
        if not Questionnaire.objects.filter(
                field_name__type=QuestionnaireField.HEALTH,
                app_user=request.app_user, modified__range=(stime, etime)).exists():
            return_data['health_detail'] = _('Unfilled Form')
            return_data['color_type'] = 'black'
        elif health_code == HealthCode.WAIT_MEASURE:
            return_data['color_type'] = '1'
        elif health_code == HealthCode.NORMAL:
            return_data['color_type'] = '0'
        elif health_code in [HealthCode.DANGER, HealthCode.QUEST_DANGER]:
            return_data['color_type'] = '2'
            if health_code == HealthCode.DANGER:
                return_data['danger_reason'] = _('Alerted by measuring staff')
            else:
                return_data['danger_reason'] = _('High risk, may have recently gone abroad or have related symptoms')
        else:
            return_data['color_type'] = 'none'
    return_data['last_time_update'] = datetime.strftime(
        utc_time_to_local_time(request.app_user.healthcode.modified), "%Y-%m-%d %H:%M:%S")
    get_liff_id(request)
    return render(request, 'line_liff/show_qr_code.html', context=return_data)


@login_required_liff
def liff_history(request):
    return_data = get_return_data_base().copy()
    health_field_all = QuestionnaireField.objects.filter(type=QuestionnaireField.HEALTH)
    if not health_field_all.exists():
        # TODO: 找不到此問券
        request.session['message'] = _('The health declaration form is not exists')
        return Response(status=status.HTTP_404_NOT_FOUND)
    else:
        health_field = health_field_all.filter(name='健康聲明調查表').first()
        health_field_en = health_field_all.filter(name='HEALTH_QUESTIONNAIRE_EN').first()
    stime, etime = get_utc_format_today()
    seven_day_ago = stime - timedelta(days=7)
    # all record
    health_question = Questionnaire.objects.filter(app_user=request.app_user,
                                                   field_name__type=QuestionnaireField.HEALTH,
                                                   created__range=(seven_day_ago, etime)).order_by('created')
    if health_question.exists():
        last_health_question = health_question.last()
        last_health_question_list = list()
        if 'language' in request.user.appuser.user_detail:
            lang = request.user.appuser.user_detail['language']
        else:
            lang = 'zh_Hant'
        if lang == 'en-us':
            show_field_name = health_field_en.field_name['field_trans_name']
        else:
            show_field_name = health_field.field_name['field_trans_name']
        if last_health_question.field_name.name == 'HEALTH_QUESTIONNAIRE_EN':
            trans_field_name = health_field_en.field_name['field_trans_name']
        else:
            trans_field_name = health_field.field_name['field_trans_name']
        field_count = 0
        for show_field in show_field_name:
            field_value = last_health_question.content[trans_field_name[field_count]][0]
            if lang == 'en-us':
                if field_value == '無':
                    field_value = 'None'
                elif field_value == '本人':
                    field_value = 'Myself'
                elif field_value == '同居人':
                    field_value = 'Cohabitant'
            else:
                if field_value == 'None':
                    field_value = '無'
                elif field_value == 'Myself':
                    field_value = '本人'
                elif field_value == 'Cohabitant':
                    field_value = '同居人'
            last_health_question_list.append((show_field, field_value, len(show_field)))
            field_count += 1
        return_data['last_health_question_list'] = last_health_question_list
        return_data['last_health_question_date'] = last_health_question.modified.strftime('%Y-%m-%d')
    # health_record = HealthRecord.objects.select_related('approach_record').filter(app_user=request.app_user)
    approach_record = ApproachRecord.objects.select_related('healthrecord').filter(
        Q(healthrecord__isnull=False, app_user=request.app_user) |
        Q(healthrecord__isnull=False, scan_user=request.app_user)
    ).order_by('-created')
    label_list = list()
    temperature_list = list()
    for question in health_question:
        if '今日額溫(填寫至小數點第1位)' in question.content:
            temperature_list.append(question.content['今日額溫(填寫至小數點第1位)'][0])
        if "Today's body/forehead temperature (fill in to the first decimal place)" in question.content:
            temperature_list.append(
                question.content["Today's body/forehead temperature (fill in to the first decimal place)"][0])
        label_list.append(utc_time_to_local_time(question.modified).strftime('%Y-%m-%d %H:%M'))
    for record in approach_record:
        if record.healthrecord.health_code == HealthCode.NORMAL:
            record.code_tag = 0
            record.code_result = _('Normal')
        else:
            record.code_tag = 1
            record.code_result = _('Danger')
        if record.app_user_id == request.app_user.id:
            record.approach_user = record.scan_user
        elif record.scan_user_id == request.app_user.id:
            record.approach_user = record.app_user

    return_data['label_list'] = label_list
    return_data['temperature_list'] = temperature_list
    if temperature_list:
        return_data['max_temp'] = max(temperature_list)
        return_data['min_temp'] = min(temperature_list)
    return_data['health_question'] = health_question
    return_data['approach_record'] = approach_record
    get_liff_id(request)
    return render(request, 'line_liff/history.html', context=return_data)


@login_required_liff
def liff_declaration(request):
    return_data = get_return_data_base().copy()
    # 區分英文版與中文版
    if request.COOKIES.get('language') == 'en-us':
        health_field = QuestionnaireField.objects.filter(type=QuestionnaireField.HEALTH, name='HEALTH_QUESTIONNAIRE_EN')
    else:
        health_field = QuestionnaireField.objects.filter(type=QuestionnaireField.HEALTH, name='健康聲明調查表')
    if not health_field.exists():
        # TODO: 找不到此問券
        request.session['message'] = _('The health declaration form is not exists')
        # return HttpResponseRedirect(reverse('liff_router', kwargs={}) + '?func_type=' + QR_SHOW)
        return HttpResponseRedirect(reverse('liff_qr_code', kwargs={}))
    else:
        health_field = health_field.first()

    if request.method == 'POST':
        request_data = dict(request.POST)
        request_data.pop('csrfmiddlewaretoken')
        latitude = request_data.pop('latitude')
        longitude = request_data.pop('longitude')
        content = dict()
        danger_flag = 0
        temp = ''
        for field in request_data:
            field_list = field.split('__')
            list_num = int(field_list[1])
            content[health_field.field_name['field_trans_name'][list_num]] = request_data[field]

            # 判斷問券內容，更換問券內容這邊必需調整
            if danger_flag != 1 and list_num == 0:
                if Decimal('38') < Decimal(request_data[field][0]):
                    danger_flag = 1
                temp = str(request_data[field][0])
            if danger_flag != 1 and list_num in [1, 2, 3, 4, 5, 6, 7]:
                if '無' in request_data[field] and len(request_data[field]) == 1:
                    danger_flag = 0
                elif 'None' in request_data[field] and len(request_data[field]) == 1:
                    danger_flag = 0
                else:
                    danger_flag = 1
            # if list_num == 2:
            #     if not request_data[field]:
            #         danger_flag = 1
            #     if '無' != request_data[field][0]:
            #         danger_flag = 1
        if danger_flag == 1:
            health_code = HealthCode.QUEST_DANGER
            request.app_user.healthcode.code = HealthCode.QUEST_DANGER
        else:
            health_code = HealthCode.WAIT_MEASURE
            request.app_user.healthcode.code = HealthCode.WAIT_MEASURE
        request.app_user.healthcode.save(update_fields=['code', 'modified'])
        health_question = Questionnaire.objects.create(app_user=request.app_user, field_name=health_field,
                                                       content=content)
        HealthRecord.objects.create(app_user=request.app_user,
                                    record_type=HealthRecord.QUESTIONNAIRE_RECORD,
                                    temperature=temp,
                                    health_code=health_code,
                                    content=content)
        if latitude and longitude and latitude[0] and longitude[0]:
            health_question.location = {
                'latlon_longitude': longitude[0],
                'latlon_latitude': latitude[0],
            }
            try:
                location_address = GpsService.get_gps_location(latitude[0], longitude[0])
            except Exception as e:
                pass
            else:
                if location_address:
                    health_question.location['location_address'] = location_address
            health_question.save(update_fields=['location', 'modified'])
        return HttpResponseRedirect(reverse('liff_qr_code', kwargs={}))
    return_data['questionnaire_name'] = health_field.name
    return_data['html_context'] = health_field.field_name
    get_liff_id(request)
    return render(request, 'line_liff/question.html', context=return_data)


def scan_result(request, qr_type, qr_id):
    return_data = get_return_data_base().copy()
    if qr_type == 'USER':
        # TODO: 使用者QR Code
        return_data['qr_type'] = 'USER'
        return_data['scan_health'] = 0
        return_data['scan_visitor'] = 0
        return_data['scan_approach'] = 0
        if qr_id == request.app_user.pub_id:
            # TODO: 掃描對象為自己
            request.session['message'] = _('Scanning objects error')
            return HttpResponseRedirect(reverse('liff_scan'))
        scaned_user = AppUser.objects.filter(pub_id=qr_id)
        if not scaned_user.exists():
            request.session['message'] = _('Scanning objects error')
            return HttpResponseRedirect(reverse('liff_scan'))
        else:
            scaned_user = scaned_user.first()
        return_data['scan_approach'] = 1
        return_data['qr_id'] = qr_id

        scan_user_company = UserCompanyTable.objects.select_related(
            'company', 'app_user').filter(employed=True, app_user=scaned_user)
        if scan_user_company.filter(company__name='資訊工業策進會').exists():
            # TODO: 屬於資策會的人此生有填過By pass
            if not Questionnaire.objects.filter(field_name__type=QuestionnaireField.HEALTH,
                                                app_user=scaned_user).exists():
                request.session['message'] = _('Scanning objects have not filled out the declaration')
                request.session['send_msg'] = _('Please filled out the declaration')
                request.session['send_user'] = qr_id
                return HttpResponseRedirect(reverse('liff_scan'))
            else:
                pass
        else:
            stime, etime = get_utc_format_today()
            if not Questionnaire.objects.filter(
                    field_name__type=QuestionnaireField.HEALTH,
                    app_user=scaned_user, modified__range=(stime, etime)).exists():
                # pre_scan.return_code = PreUserQRTrans.NO_HEALTH_QU
                # TODO: 跳到沒有做健康碼
                request.session['message'] = _('Scanning objects have not filled out the declaration')
                request.session['send_msg'] = _('Please filled out the declaration')
                request.session['send_user'] = qr_id
                return HttpResponseRedirect(reverse('liff_scan'))
        if HealthCode.objects.filter(app_user=scaned_user, code=HealthCode.QUEST_DANGER).exists():
            # TODO: 被掃描者由填表判定為高風險
            request.session['message'] = _('Scanning objects is judged as high risk by the system')
            request.session['send_msg'] = _('You are currently a high-risk object, temporarily banned')
            request.session['send_user'] = qr_id
            return HttpResponseRedirect(reverse('liff_scan'))
        # not_visitor = 1
        user_company_list = UserCompanyTable.objects.filter(app_user=request.user.appuser)
        if user_company_list.exists():
            for user_company in user_company_list:
                # 判斷有沒有掃描健康碼權限及可更新的公司選項
                if (user_company.scan_enabled and request.user.appuser.attendancestatus_set.filter(
                        company=user_company.company, status=AttendanceStatus.ON_WORK)):
                    return_data['scan_health'] = 1
                    # scan_company_list.append(user_company.company)
                    # return_data['scan_company_list'] = scan_company_list

                # 判斷訪客與掃描者公司是否相同
                if not scan_user_company.filter(company=user_company.company).exists():
                    return_data['scan_visitor'] = 1
                    # visitor_company_list.append(user_company.company)
            # if not_visitor == 0:
            #     return_data['scan_visitor'] = 1
    elif qr_type == 'PLACE':
        # TODO: 地點QR Code
        return_data['qr_type'] = 'PLACE'
        return_data['scan_clock_in'] = 0
        place = Place.objects.filter(pub_id=qr_id)
        if place.exists():
            place = place.first()
            return_data['scan_place'] = 1
            return_data['qr_id'] = qr_id
            if place.company:
                #  暫時關閉上班打卡，改為有掃描權限的人才要打卡
                # if UserCompanyTable.objects.filter(app_user=request.user.appuser, company=place.company).exists():
                #     return_data['scan_clock_in'] = 1
                if UserCompanyTable.objects.filter(app_user=request.user.appuser, company=place.company,
                                                   scan_enabled=True).exists():
                    return_data['scan_user_clock_in'] = 1
        else:
            # TODO: 跳到找不到地址
            request.session['message'] = _('Scanning objects error')
            return HttpResponseRedirect(reverse('liff_scan'))
    elif qr_type == 'ADDORG':
        # TODO: 加入組織QR Code
        company = Company.objects.select_related('addcompanytag').filter(addcompanytag__pub_id=qr_id)
        if not company.exists():
            request.session['message'] = _('Scanning objects error')
            return HttpResponseRedirect(reverse('liff_scan'))
        else:
            company = company.first()
            if request.user.appuser.usercompanytable_set.filter(company=company, employed=True).exists():
                request.session['message'] = _('Already in this company')
                return HttpResponseRedirect(reverse('liff_scan'))
            add_req = AddRequest.objects.filter(add_user=request.user.appuser, add_tag__pub_id=qr_id,
                                                status=AddRequest.WAIT_AUDIT)
            if add_req.exists():
                add_req = add_req.first()
                if add_req.status == AddRequest.WAIT_AUDIT:
                    return_data['company'] = company
                    return_data['tag_id'] = qr_id
                    return_data['add_req_id'] = add_req.pub_id
                    return_data['add_req_time'] = utc_time_to_local_time(add_req.modified)
                    return_data['message'] = _('Already submitted an application')
            else:
                return_data['company'] = company
                return_data['tag_id'] = qr_id
            # TODO:直接跳轉
            return render(request, 'line_liff/addorg_sel.html', context=return_data)
    else:
        request.session['message'] = _('Scanning objects error')
        return HttpResponseRedirect(reverse('liff_scan'))
    return render(request, 'line_liff/scan_func.html', context=return_data)


@login_required_liff
def liff_scan(request):
    return_data = get_return_data_base().copy()

    if request.session.get('message'):
        return_data['message'] = request.session.pop('message')

    if request.method == 'POST':
        scan_file = request.FILES.get('scan_file')
        scan_value = request.POST.get('scan_value')
        user_name = request.POST.get('user_name')
        if scan_file:
            qr_data = read_qr_code(scan_file)
            # return_data['qr_data'] = qr_data
            if qr_data:
                qr_data = qr_data.split('__')
                if len(qr_data) == 2:
                    qr_type = qr_data[0]
                    qr_id = qr_data[1]
                    return scan_result(request, qr_type, qr_id)
                else:
                    return_data['message'] = _('Scanning objects error')
            else:
                return_data['message'] = _('Scanning objects error')
        elif scan_value:
            qr_data = scan_value.split('__')
            if len(qr_data) == 2:
                qr_type = qr_data[0]
                qr_id = qr_data[1]
                return scan_result(request, qr_type, qr_id)
            else:
                return_data['message'] = _('Scanning objects error')
        elif user_name:
            scaned_app_user = AppUser.objects.filter(auth_user__username=user_name)
            if scaned_app_user.exists():
                return scan_result(request, 'USER', scaned_app_user.first().pub_id)
            else:
                scan_place = Place.objects.filter(serial_num=user_name)
                if scan_place.exists():
                    return scan_result(request, 'PLACE', scan_place.first().pub_id)
                else:
                    return_data['message'] = _('Scanning objects error')
    get_liff_id(request)
    return render(request, 'line_liff/scan_page.html', context=return_data)


@login_required_liff
def liff_scan_sel(request):
    return_data = get_return_data_base().copy()
    qr_id = request.POST.get('qr_id')
    func_sel = request.POST.get('func_sel')
    # location = request.POST.get('location')

    longitude = request.POST.get('longitude')  # 網頁經度
    latitude = request.POST.get('latitude')  # 網頁緯度

    # TODO: 之後強制加入地點
    # if location:
    #     return_data['location'] = location
    # else:
    #     if web_latitude and web_longitude:
    #         return_data['location'] = {
    #             'latlon_longitude': web_latitude,
    #             'latlon_latitude': web_longitude
    #         }
    if latitude and longitude:
        return_data['location'] = {
            'latlon_longitude': longitude,
            'latlon_latitude': latitude,
        }

    if qr_id and func_sel:
        if func_sel == 'scan_health':
            # place_entry = PlaceEntryRecord.objects.filter(app_user=request.app_user).order_by('-created')
            # if place_entry.exists():
            #     last_place = place_entry.first()
            #     return_data['last_place'] = last_place
            # scan_company_list = list()
            # company_place_dict = dict()
            # user_company_list = UserCompanyTable.objects.filter(app_user=request.user.appuser)
            # if user_company_list.exists():
            #     for user_company in user_company_list:
            #         # 判斷有沒有掃描健康碼權限及可更新的公司選項
            #         if (user_company.scan_enabled and request.user.appuser.attendancestatus_set.filter(
            #                 company=user_company.company, status=AttendanceStatus.ON_WORK)):
            #             scan_company_list.append(user_company.company)
            #             company_place_dict[user_company.company.name] = [
            #                 f'{place.name}__{place.pub_id}' for place in user_company.company.place_set.filter(
            #                     scan_enabled=True)]
            #     return_data['scan_company_list'] = scan_company_list
            #     return_data['company_place_dict'] = company_place_dict
            scanned_app_user = AppUser.objects.filter(pub_id=qr_id)
            if scanned_app_user.exists():
                return_data['scanned_app_user'] = scanned_app_user.first()
                return render(request, 'line_liff/health_code_sel.html', context=return_data)
            else:
                # TODO: 無此使用者
                request.session['message'] = _('Scanning objects error')
                return HttpResponseRedirect(reverse('liff_scan'))
        elif func_sel == 'scan_approach':
            scanned_app_user = AppUser.objects.filter(pub_id=qr_id)
            if scanned_app_user.exists():
                return_data['scanned_app_user'] = scanned_app_user.first()
                return render(request, 'line_liff/approach_sel.html', context=return_data)
            else:
                # TODO: 無此使用者
                request.session['message'] = _('Scanning objects error')
                return HttpResponseRedirect(reverse('liff_scan'))
        elif func_sel == 'scan_visitor':
            scanned_app_user = AppUser.objects.filter(pub_id=qr_id)
            if not scanned_app_user.exists():
                # TODO: 無此使用者
                request.session['message'] = _('Scanning objects error')
                return HttpResponseRedirect(reverse('liff_scan'))
            else:
                scanned_app_user = scanned_app_user.first()
            user_company_list = UserCompanyTable.objects.filter(app_user=request.user.appuser, employed=True)
            if user_company_list.exists():
                scan_company_list = list()
                for user_company in user_company_list:
                    if not UserCompanyTable.objects.filter(app_user=scanned_app_user,
                                                           company=user_company.company,
                                                           employed=True).exists():
                        scan_company_list.append(user_company.company)
                if not scan_company_list:
                    # TODO: 無此訪客資料可以加入
                    request.session['message'] = _('No visitor information can be added')
                    return HttpResponseRedirect(reverse('liff_scan'))
                return_data['scan_company_list'] = scan_company_list
                return_data['scanned_app_user'] = scanned_app_user
                return render(request, 'line_liff/visitor_sel.html', context=return_data)
            else:
                # TODO: 掃描者無公司資料
                request.session['message'] = _('You currently have no company / school')
                return HttpResponseRedirect(reverse('liff_scan'))
        elif func_sel == 'scan_clock_in':
            # TODO:暫時不用
            status_dict = AttendanceStatus.return_status_dict()
            place = Place.objects.select_related('company').filter(pub_id=qr_id)
            if not place.exists():
                # TODO: 無此地點
                request.session['message'] = _('Scanning objects error')
                return HttpResponseRedirect(reverse('liff_scan'))
            else:
                place = place.first()
                return_data['company'] = place.company
                return_data['place'] = place
            app_user_attendance = request.app_user.attendancestatus_set.filter(company=place.company)
            if not app_user_attendance.exists():
                # TODO: 無此公司打卡資料
                request.session['message'] = _('You may no longer be in this company')
                return HttpResponseRedirect(reverse('liff_scan'))
            else:
                app_user_attendance = app_user_attendance.first()
                return_data['user_status'] = status_dict[app_user_attendance.status]

            if app_user_attendance.status == AttendanceStatus.ON_WORK:
                return_data['status_list'] = [
                    (AttendanceStatus.GET_OFF_WORK, status_dict[AttendanceStatus.GET_OFF_WORK])]
            elif app_user_attendance.status == AttendanceStatus.GET_OFF_WORK:
                return_data['status_list'] = [
                    (AttendanceStatus.ON_WORK, status_dict[AttendanceStatus.ON_WORK]),
                    (AttendanceStatus.LEAVE, status_dict[AttendanceStatus.LEAVE]),
                    (AttendanceStatus.FIELDWORK, status_dict[AttendanceStatus.FIELDWORK]),
                    (AttendanceStatus.BUSINESS_TRIP, status_dict[AttendanceStatus.BUSINESS_TRIP])]
            elif app_user_attendance.status == AttendanceStatus.FIELDWORK:
                return_data['status_list'] = [
                    (AttendanceStatus.ON_WORK, status_dict[AttendanceStatus.ON_WORK]),
                    (AttendanceStatus.GET_OFF_WORK, status_dict[AttendanceStatus.GET_OFF_WORK]),
                    (AttendanceStatus.LEAVE, status_dict[AttendanceStatus.LEAVE]),
                    (AttendanceStatus.FIELDWORK, status_dict[AttendanceStatus.FIELDWORK]),
                    (AttendanceStatus.BUSINESS_TRIP, status_dict[AttendanceStatus.BUSINESS_TRIP])]
            elif app_user_attendance.status in [AttendanceStatus.BUSINESS_TRIP, AttendanceStatus.LEAVE]:
                return_data['status_list'] = [
                    (AttendanceStatus.ON_WORK, status_dict[AttendanceStatus.ON_WORK]),
                    (AttendanceStatus.GET_OFF_WORK, status_dict[AttendanceStatus.GET_OFF_WORK]),
                    (AttendanceStatus.LEAVE, status_dict[AttendanceStatus.LEAVE]),
                    (AttendanceStatus.FIELDWORK, status_dict[AttendanceStatus.FIELDWORK]),
                    (AttendanceStatus.BUSINESS_TRIP, status_dict[AttendanceStatus.BUSINESS_TRIP])]
            return render(request, 'line_liff/work_sel.html', context=return_data)
        elif func_sel == 'scan_user_clock_in':
            status_dict = AttendanceStatus.return_status_dict()
            place = Place.objects.select_related('company').filter(pub_id=qr_id)
            if not place.exists():
                # TODO: 無此地點
                request.session['message'] = _('Scanning objects error')
                return HttpResponseRedirect(reverse('liff_scan'))
            else:
                place = place.first()
                return_data['company'] = place.company
                return_data['place'] = place
            app_user_attendance = request.app_user.attendancestatus_set.filter(company=place.company)
            if not app_user_attendance.exists():
                # TODO: 無此公司打卡資料
                request.session['message'] = _('You may no longer be in this company')
                return HttpResponseRedirect(reverse('liff_scan'))
            else:
                app_user_attendance = app_user_attendance.first()
                return_data['user_status'] = status_dict[app_user_attendance.status]

            if app_user_attendance.status == AttendanceStatus.ON_WORK:
                return_data['user_status'] = _('Scan permission enabled')
                return_data['status_to_change'] = AttendanceStatus.GET_OFF_WORK
                return_data['status_to_change_show'] = _('Scan permission disabled')
            elif app_user_attendance.status == AttendanceStatus.GET_OFF_WORK:
                return_data['user_status'] = _('Scan permission disabled')
                return_data['status_to_change'] = AttendanceStatus.ON_WORK
                return_data['status_to_change_show'] = _('Scan permission enabled')

            return render(request, 'line_liff/scan_work_sel.html', context=return_data)
        elif func_sel == 'scan_place':
            place = Place.objects.select_related('company').filter(pub_id=qr_id)
            if not place.exists():
                # TODO: 無此地點
                request.session['message'] = _('Scanning objects error')
                return HttpResponseRedirect(reverse('liff_scan'))
            else:
                place = place.first()
                return_data['place'] = place

            return render(request, 'line_liff/place_sel.html', context=return_data)
    else:
        request.session['message'] = _('Field missing')
        return HttpResponseRedirect(reverse('liff_scan'))


@login_required_liff
def liff_health_status(request):
    scanned_user_id = request.POST.get('scanned_user_id')
    # place_id = request.POST.get('place_sel')
    health_status = request.POST.get('health_status')
    location = request.POST.get('location')

    # 未通過原因，預留
    content = request.POST.get('content')
    # 溫度，預留
    temperature = request.POST.get('temperature')

    if scanned_user_id and health_status:
        scanned_app_user = AppUser.objects.select_related('healthcode').filter(pub_id=scanned_user_id)
        if not scanned_app_user.exists():
            # TODO: 無此user
            request.session['message'] = _('Scanning objects error')
            return HttpResponseRedirect(reverse('liff_scan'))
        else:
            scanned_app_user = scanned_app_user.first()
        # place = Place.objects.select_related('company').filter(pub_id=place_id)
        # if not place.exists():
        #     # TODO: 無此地點
        #     return HttpResponseRedirect(
        #         reverse('app_index', kwargs={'user_id': request.user.appuser.pub_id,
        #                                      'token': request.user.appuser.api_token}))
        # else:
        #     place = place.first()
        if health_status == 'PASS':
            health_code = HealthCode.NORMAL
        else:
            health_code = HealthCode.DANGER
        scanned_app_user.healthcode.code = health_code
        scanned_app_user.healthcode.save(update_fields=['code', 'modified'])
        # 接觸紀錄
        approach_record = ApproachRecord.objects.create(app_user=scanned_app_user, scan_user=request.app_user,
                                                        type=ApproachRecord.HEALTH_CHECK)
        # approach_record.approach_place = place
        # TODO: 之後強制加入地點
        # Alan_TODO: location_dict=eval(location) -> location_dict=location
        if location:
            location_dict = location
            approach_record.location = location_dict
            try:
                location_address = GpsService.get_gps_location(location_dict['latlon_longitude'],
                                                               location_dict['latlon_latitude'])
            except Exception as e:
                pass
            else:
                if location_address:
                    approach_record.location['location_address'] = location_address
            approach_record.save(update_fields=['location', 'modified'])
        # 健康碼紀錄
        health_record = HealthRecord.objects.create(app_user=scanned_app_user, health_code=health_code,
                                                    approach_record=approach_record)
        if content:
            health_record.content = content
        if temperature:
            health_record.temperature = temperature
        health_record.save(update_fields=['content', 'temperature', 'modified'])
        if health_status == 'PASS':
            request.session['send_msg'] = _('Update Health Code success, you have passed')
        else:
            request.session['send_msg'] = _('You did not pass')
        request.session['send_user'] = scanned_app_user.pub_id
    else:
        request.session['message'] = _('Field missing')
    return HttpResponseRedirect(reverse('liff_scan'))


@login_required_liff
def liff_approach_status(request):
    scanned_user_id = request.POST.get('scanned_user_id')
    location = request.POST.get('location')

    if scanned_user_id:
        scanned_app_user = AppUser.objects.filter(pub_id=scanned_user_id)
        if scanned_app_user.exists():
            scanned_app_user = scanned_app_user.first()
            approach_record = ApproachRecord.objects.create(app_user=scanned_app_user, scan_user=request.app_user,
                                                            type=ApproachRecord.APPROACH_CHECK)
            # Alan_TODO: location_dict=eval(location) -> location_dict=location
            if location:
                location_dict = location
                approach_record.location = location_dict
                try:
                    location_address = GpsService.get_gps_location(location_dict['latlon_longitude'],
                                                                   location_dict['latlon_latitude'])
                except Exception as e:
                    pass
                else:
                    if location_address:
                        approach_record.location['location_address'] = location_address
                approach_record.save(update_fields=['location'])
            request.session['send_msg'] = _('Update approach record success')
            request.session['send_user'] = scanned_app_user.pub_id
        else:
            # TODO: 無此user
            request.session['message'] = _('Scanning objects error')
    else:
        # TODO: 欄位有缺
        request.session['message'] = _('Field missing')
    return HttpResponseRedirect(reverse('liff_scan'))


@login_required_liff
def liff_visitor_status(request):
    scanned_user_id = request.POST.get('scanned_user_id')
    company_id = request.POST.get('company_id')
    # place_id = request.POST.get('place_id')
    location = request.POST.get('location')

    if scanned_user_id and company_id:
        stime, etime = get_utc_format_today()
        if not VisitorRegistration.objects.filter(modified__range=(stime, etime), company__pub_id=company_id,
                                                  app_user__pub_id=scanned_user_id).exists():
            company = Company.objects.filter(pub_id=company_id)
            if not company.exists():
                # TODO: 無此公司
                request.session['message'] = _('Scanning objects error')
                return HttpResponseRedirect(reverse('liff_scan'))
            else:
                company = company.first()
            scanned_app_user = AppUser.objects.filter(pub_id=scanned_user_id)
            if not scanned_app_user.exists():
                # TODO: 無此使用者
                request.session['message'] = _('Scanning objects error')
                return HttpResponseRedirect(reverse('liff_scan'))
            else:
                scanned_app_user = scanned_app_user.first()
            # 接觸紀錄
            approach_record = ApproachRecord.objects.create(app_user=scanned_app_user, scan_user=request.app_user,
                                                            type=ApproachRecord.VISITOR_CHECK)
            VisitorRegistration.objects.create(company=company, app_user=scanned_app_user,
                                               approach_record=approach_record, visitor=True)
            # place_entry = PlaceEntryRecord.objects.create(app_user=request.app_user, place_entry=place)
            # Alan_TODO: location_dict=eval(location) -> location_dict=location
            if location:
                location_dict = location
                approach_record.location = location_dict
                # place_entry.location = location
                try:
                    location_address = GpsService.get_gps_location(location_dict['latlon_longitude'],
                                                                   location_dict['latlon_latitude'])
                except Exception as e:
                    pass
                else:
                    if location_address:
                        approach_record.location['location_address'] = location_address
                approach_record.save(update_fields=['location', 'modified'])
            # place_entry.save(update_fields=['location', 'modified'])
            request.session['send_msg'] = _('Update visitor record success')
            request.session['send_user'] = scanned_app_user.pub_id
        else:
            # TODO: 已經有訪客紀錄
            request.session['message'] = _('Visitor record already exist')
        return HttpResponseRedirect(reverse('liff_scan'))
    else:
        # TODO: 欄位有缺
        request.session['message'] = _('Field missing')
    return HttpResponseRedirect(reverse('liff_scan'))


# TODO: 暫時關閉
@login_required_liff
def liff_work_status(request):
    company_id = request.POST.get('company_id')
    place_id = request.POST.get('place_id')
    status = request.POST.get('status')
    remote_work = request.POST.get('remote_work')
    location = request.POST.get('location')

    if company_id and place_id and status:
        place = Place.objects.select_related('company').filter(pub_id=place_id, company__pub_id=company_id)
        if not place.exists():
            # TODO: 無此地點
            request.session['message'] = _('Scanning objects error')
            return HttpResponseRedirect(reverse('liff_scan'))
        else:
            place = place.first()
        app_user_attendance = request.app_user.attendancestatus_set.filter(company=place.company)
        if not app_user_attendance.exists():
            # TODO: 無此公司打卡資料
            request.session['message'] = _('You may no longer be in this company')
            return HttpResponseRedirect(reverse('liff_scan'))
        else:
            app_user_attendance = app_user_attendance.first()
        app_user_attendance.status = int(status)
        if remote_work:
            app_user_attendance.remote_work = True
        app_user_attendance.save(update_fields=['status', 'remote_work', 'modified'])

        if int(status) in [AttendanceStatus.ON_WORK, AttendanceStatus.FIELDWORK, AttendanceStatus.BUSINESS_TRIP]:
            record_status = AttendanceRecord.ON_WORK
        else:
            record_status = AttendanceRecord.GET_OFF_WORK

        attendance_record = AttendanceRecord.objects.create(app_user=request.app_user, status=record_status,
                                                            attendance_status=int(status))

        attendance_record.approach_place = place

        place_entry = PlaceEntryRecord.objects.create(app_user=request.app_user, place_entry=place)
        # TODO: 之後強制加入地點
        # Alan_TODO: location_dict=eval(location) -> location_dict=location
        if location:
            location_dict = location
            attendance_record.location = location_dict
            place_entry.location = location_dict
            try:
                location_address = GpsService.get_gps_location(location_dict['latlon_longitude'],
                                                               location_dict['latlon_latitude'])
            except Exception as e:
                pass
            else:
                if location_address:
                    attendance_record.location['location_address'] = location_address
        attendance_record.save(update_fields=['approach_place', 'location', 'modified'])
        place_entry.save(update_fields=['location', 'modified'])
    else:
        # TODO: 資料有缺
        request.session['message'] = _('Field missing')
    return HttpResponseRedirect(reverse('liff_scan'))


@login_required_liff
def liff_scan_work_status(request):
    company_id = request.POST.get('company_id')
    place_id = request.POST.get('place_id')
    location = request.POST.get('location')

    if company_id and place_id:
        place = Place.objects.select_related('company').filter(pub_id=place_id, company__pub_id=company_id)
        if not place.exists():
            # TODO: 無此地點
            request.session['message'] = _('Scanning objects error')
            return HttpResponseRedirect(reverse('liff_scan'))
        else:
            place = place.first()
        app_user_attendance = request.app_user.attendancestatus_set.filter(company=place.company)
        if not app_user_attendance.exists():
            # TODO: 無此公司打卡資料
            request.session['message'] = _('You may no longer be in this company')
            return HttpResponseRedirect(reverse('liff_scan'))
        else:
            app_user_attendance = app_user_attendance.first()

        if app_user_attendance.status == AttendanceStatus.ON_WORK:
            record_status = AttendanceRecord.GET_OFF_WORK
            status = AttendanceRecord.GET_OFF_WORK
        elif app_user_attendance.status == AttendanceStatus.GET_OFF_WORK:
            record_status = AttendanceRecord.ON_WORK
            status = AttendanceRecord.ON_WORK
        else:
            request.session['message'] = _('Select status is not exists')
            return HttpResponseRedirect(reverse('liff_scan'))
        app_user_attendance.status = status
        app_user_attendance.save(update_fields=['status', 'remote_work', 'modified'])
        attendance_record = AttendanceRecord.objects.create(app_user=request.app_user, status=record_status,
                                                            attendance_status=status)
        attendance_record.approach_place = place
        place_entry = PlaceEntryRecord.objects.create(app_user=request.app_user, place_entry=place)
        # TODO: 之後強制加入地點
        # Alan_TODO: location_dict=eval(location) -> location_dict=location
        if location:
            location_dict = location
            attendance_record.location = location_dict
            place_entry.location = location_dict
            try:
                location_address = GpsService.get_gps_location(location_dict['latlon_longitude'],
                                                               location_dict['latlon_latitude'])
            except Exception as e:
                pass
            else:
                if location_address:
                    attendance_record.location['location_address'] = location_address
        attendance_record.save(update_fields=['approach_place', 'location', 'modified'])
        place_entry.save(update_fields=['location', 'modified'])
    else:
        # TODO: 資料有缺
        request.session['message'] = _('Field missing')
    return HttpResponseRedirect(reverse('liff_scan'))


@login_required_liff
def liff_place_entry(request):
    place_id = request.POST.get('place_id')
    location = request.POST.get('location')
    # act_name = request.POST.get('act_name')
    # act_organizer = request.POST.get('act_organizer')
    # act_org_contact = request.POST.get('act_org_contact')
    if place_id:
        place = Place.objects.select_related('company').filter(pub_id=place_id)
        if not place.exists():
            # TODO: 無此地點
            request.session['message'] = _('Scanning objects error')
            return HttpResponseRedirect(reverse('liff_scan'))
        else:
            place = place.first()
        if place.update_health_code:
            if request.app_user.healthcode.code in [HealthCode.DANGER, HealthCode.QUEST_DANGER]:
                request.session['message'] = _('You are currently a high-risk object, temporarily banned')
                return HttpResponseRedirect(reverse('liff_scan'))
            elif request.app_user.usercompanytable_set.filter(company__name='資訊工業策進會').exists():
                # TODO: 屬於資策會的人此生有填過By pass
                if not Questionnaire.objects.filter(field_name__type=QuestionnaireField.HEALTH,
                                                    app_user=request.app_user).exists():
                    request.session['message'] = _('Please filled out the declaration')
                    return HttpResponseRedirect(reverse('liff_scan'))
            else:
                stime, etime = get_utc_format_today()
                if not Questionnaire.objects.filter(
                        field_name__type=QuestionnaireField.HEALTH,
                        app_user=request.app_user, modified__range=(stime, etime)).exists():
                    request.session['message'] = _('Please filled out the declaration')
                    return HttpResponseRedirect(reverse('liff_scan'))
            request.app_user.healthcode.code = HealthCode.NORMAL
            request.app_user.healthcode.save(update_fields=['code', 'modified'])

            # 健康碼紀錄
            health_record = HealthRecord.objects.create(app_user=request.app_user, health_code=HealthCode.NORMAL)
            # 暫時未使用
            # if content:
            #     health_record.content = content
            # if temperature:
            #     health_record.temperature = temperature
            # health_record.save(update_fields=['content', 'temperature', 'modified'])
        place_entry = PlaceEntryRecord.objects.create(app_user=request.app_user, place_entry=place)
        # TODO: 之後強制加入地點
        # Alan_TODO: location_dict=eval(location) -> location_dict=location
        if location:
            location_dict = location
            place_entry.location = location_dict
            try:
                location_address = GpsService.get_gps_location(location_dict['latlon_longitude'],
                                                               location_dict['latlon_latitude'])
            except Exception as e:
                pass
            else:
                if location_address:
                    place_entry.location['location_address'] = location_address
        # entry_note = dict()
        # if act_name:
        #     entry_note['act_name'] = act_name
        # if act_organizer:
        #     entry_note['act_organizer'] = act_organizer
        # if act_org_contact:
        #     entry_note['act_org_contact'] = act_org_contact
        # place_entry.note = entry_note
        place_entry.save(update_fields=['location', 'modified', 'note'])
    return HttpResponseRedirect(reverse('liff_scan'))


@login_required_liff
def liff_add_company(request):
    company_id = request.POST.get('company_id')
    tag_id = request.POST.get('tag_id')
    add_req_id = request.POST.get('add_req_id')
    if company_id:
        if add_req_id:
            add_req = AddRequest.objects.filter(pub_id=add_req_id, add_tag__company__pub_id=company_id,
                                                status=AddRequest.WAIT_AUDIT, add_user=request.app_user)
            if add_req.exists():
                add_req = add_req.first()
                add_req.status = AddRequest.CANCEL
                add_req.agree_user = request.app_user
                add_req.note = {'cancel_user': 'SELF'}
                add_req.save(update_fields=['modified', 'status', 'note', 'agree_user'])
                request.session['message'] = _('Add organization request deleted')
            else:
                request.session['message'] = _('Scanning objects error')
            return HttpResponseRedirect(reverse('liff_scan'))
        else:
            add_tag = AddCompanyTag.objects.filter(pub_id=tag_id, company__pub_id=company_id)
            if add_tag.exists():
                add_tag = add_tag.first()
                AddRequest.objects.create(add_tag=add_tag, add_user=request.app_user)
                request.session['message'] = _('Add request sent, pending review')
            else:
                request.session['message'] = _('Scanning objects error')
            return HttpResponseRedirect(reverse('liff_scan'))
    else:
        # TODO: 欄位有缺
        request.session['message'] = _('Field missing')
    return HttpResponseRedirect(reverse('liff_scan'))


@login_required_liff
def liff_check_in(request):
    return_data = get_return_data_base().copy()
    if request.method == 'POST':
        longitude = request.POST.get('longitude')  # 網頁經度
        latitude = request.POST.get('latitude')  # 網頁緯度
        act_name = request.POST.get('act_name')
        act_organizer = request.POST.get('act_organizer')
        act_org_contact = request.POST.get('act_org_contact')
        if latitude and longitude:
            location_dict = {
                'latlon_longitude': longitude,
                'latlon_latitude': latitude
            }
            try:
                location_address = GpsService.get_gps_location(latitude, longitude)
            except Exception as e:
                pass
            else:
                if location_address:
                    location_dict['location_address'] = location_address
            place_entry = PlaceEntryRecord.objects.create(app_user=request.app_user, location=location_dict)
            entry_note = dict()
            if act_name:
                entry_note['act_name'] = act_name
            if act_organizer:
                entry_note['act_organizer'] = act_organizer
            if act_org_contact:
                entry_note['act_org_contact'] = act_org_contact
            place_entry.note = entry_note
            place_entry.save(update_fields=['modified', 'note'])
            return HttpResponseRedirect(reverse('liff_history', kwargs={}))
        else:
            # TODO: 無定位到
            return_data['message'] = _('Please wait locate')
    get_liff_id(request)
    return render(request, 'line_liff/location_check_in.html', context=return_data)


@login_required_liff
def liff_personal_file(request):
    return_data = get_return_data_base().copy()
    if request.method == 'POST':
        user_first_name = request.POST.get('user_first_name')
        # email = request.POST.get('email')
        # phone = request.POST.get('phone')
        company_id = request.POST.get('company_id')
        note = request.POST.get('note')
        # request.app_user.email = email
        try:
            # if phone != 'None' or phone:
            #     dial_code, phone = AppUserServices.change_phone(phone)
            # request.app_user.phone = phone
            # request.app_user.email = email
            if company_id:
                user_company = request.app_user.usercompanytable_set.filter(pub_id=company_id, employed=True)
                if user_company.exists():
                    user_company = user_company.first()
                    user_company.default_show = True
                    user_company.save(update_fields=['default_show', 'modified'])
                user_company_other = request.app_user.usercompanytable_set.filter(
                    employed=True).exclude(pub_id=company_id)
                if user_company_other.exists():
                    for comp in user_company_other:
                        comp.default_show = False
                        comp.save(update_fields=['default_show', 'modified'])
            if note:
                request.app_user.note = note
                request.app_user.save(update_fields=['phone', 'email', 'note', 'modified'])
            if user_first_name:
                request.user.first_name = user_first_name
                request.user.save()
        except PhoneFormatWrong:
            # TODO: 電話格式錯誤
            return_data['message'] = _('Phone format error')
        request.app_user = request.user.appuser
    return_data['user_company_list'] = [
        user_company for user_company in request.app_user.usercompanytable_set.filter(employed=True)]
    get_liff_id(request)
    return render(request, 'line_liff/user_profile.html', context=return_data)


@login_required_liff
def liff_upload_user_img(request):
    user_img_file = request.FILES.copy()
    if 'upload_img' in user_img_file:
        img_file_obj = user_img_file['upload_img']
        file_path = \
            f'media/{request.app_user.pub_id}/user_image/{request.app_user.pub_id}.{img_file_obj.name.split(".")[1]}'
        url = AppUserServices.upload_to_aws(file_path, user_img_file['upload_img'])
        request.app_user.user_picture_local = url
        request.app_user.save(update_fields=['modified', 'user_picture_local'])
    return HttpResponseRedirect(reverse('liff_personal_file'))


@login_required_liff
def liff_edit_password_otp(request):
    return_data = get_return_data_base().copy()
    if request.method == 'POST':
        otp = request.POST.get('otp')
        otp_id = request.POST.get('otp_id')
        if otp and otp_id:
            try:
                OtpService(otp_id).verify(otp, verify_phone=request.app_user.phone)
            except Exception as e:
                return_data['message'] = _('Verify Otp Error, Please resend Otp')
            else:
                return HttpResponseRedirect(reverse('liff_edit_password', kwargs={}))
    get_liff_id(request)
    return render(request, 'line_liff/edit_pwd_otp.html', context=return_data)


@login_required_liff
def liff_edit_password(request):
    return_data = get_return_data_base().copy()
    if request.method == 'POST':
        password = request.POST.get('password')
        chkpassword = request.POST.get('chkpassword')
        if password and chkpassword:
            if password != chkpassword:
                # TODO: 密碼跟確認密碼不相同
                return_data['message'] = _('The password and verify password not same')
            else:
                request.user.set_password(password)
                request.user.save()
                auth.login(request, request.user)
                request.session['message'] = _('Password has been reset')
                return HttpResponseRedirect(reverse('liff_personal_file'))
    get_liff_id(request)
    return render(request, 'line_liff/edit_pwd.html', context=return_data)


@login_required_liff
def liff_com_reg(request):
    return_data = get_return_data_base().copy()
    if request.method == 'POST':
        company_name = request.POST.get('company_name')
        tax_id_number = request.POST.get('tax_id_number')
        contact_mail = request.POST.get('contact_mail')
        if Company.objects.filter(tax_id_number=tax_id_number).exists():
            return_data['message'] = _('This Tax ID number has already been used')
        else:
            if NewCompanyApply.objects.filter(
                    tax_id_number=tax_id_number,
                    status__in=[NewCompanyApply.AGREE, NewCompanyApply.WAIT_AUDIT]).exists():
                return_data['message'] = _('This Tax ID number has already been used')
            else:
                NewCompanyApply.objects.create(
                    company_name=company_name, tax_id_number=tax_id_number, apply_user=request.app_user)
                # return_data['message'] = _('Application has been submitted')
                request.session['message'] = _('Application has been submitted')
                request.session['show_list'] = True
                return HttpResponseRedirect(reverse('liff_com_reg'))
    if request.session.get('message'):
        return_data['message'] = request.session.pop('message')
    if request.session.get('show_list'):
        return_data['show_list'] = request.session.pop('show_list')
    # return_data['show_list'] = True
    return_data['applicant'] = request.app_user
    get_liff_id(request)
    return render(request, 'line_liff/com_reg.html', context=return_data)


@login_required_liff
def liff_com_reg_cancel(request):
    apply_id = request.POST.get('apply_id')
    if not apply_id:
        request.session['message'] = _('Application is not exist')
    else:
        com_reg = NewCompanyApply.objects.filter(pub_id=apply_id)
        if com_reg.exists():
            com_reg = com_reg.first()
            com_reg.status = NewCompanyApply.CANCEL
            com_reg.save(update_fields=['status', 'modified'])
            request.session['message'] = _('Application has been cancel')
        else:
            request.session['message'] = _('Application is not exist')
    request.session['show_list'] = True
    return HttpResponseRedirect(reverse('liff_com_reg'))


# @api_view(['POST'])
# def callback(request):
#     # get X-Line-Signature header value
#     signature = request.headers['X-Line-Signature']
#
#     # get request body as text
#     body = request.get_data(as_text=True)
#
#     # handle webhook body（負責）
#     try:
#         handler.handle(body, signature)
#     except InvalidSignatureError:
#         print("Invalid signature. Please check your channel access token/channel secret.")
#         return Response(status=status.HTTP_400_BAD_REQUEST)
#
#     # return 'OK'\
#     return HttpResponse("OK", content_type='text')


# @api_view(['GET'])
# def handle_currency_exchange(request):
#     print(1)
#     return Response(data={'result': '1'})


# def return_index(request):
#     return render(request, 'line_liff/liff_index.html', context={})


@login_required_liff
def liff_scan_test(request):
    if request.method == 'POST':
        qr_type = request.POST.get('qr_type')
        qr_content = request.POST.get('qr_content')
        return scan_result(request, qr_type, qr_content)
    user_list = AppUser.objects.exclude(pub_id=request.app_user.pub_id)
    place_list = Place.objects.all()
    return render(request, 'line_liff/scan_test.html', context={
        'user_list': user_list,
        'place_list': place_list,
        'company_list': [(company.name, company.addcompanytag.pub_id) for company in Company.objects.all()]
    })


# description
def line_func_description(request):
    return_data = dict()
    if request.method == 'GET':
        func_type = request.GET.get('func_type')
        if func_type:
            return_data['func_type'] = func_type
    return render(request, 'line_liff/description.html', context=return_data)


def img_router(request, file_name, file_size):
    try:
        image_data = open(
            settings.ROOT_DIR.path(
                f'maipassport/static/app_web/img/{file_name}/{file_size}.png'
            ), "rb").read()
    except FileNotFoundError:
        return Response(status=status.HTTP_404_NOT_FOUND)
    else:
        return HttpResponse(image_data, content_type="image/png")



