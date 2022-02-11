import io
from base64 import urlsafe_b64decode
from datetime import datetime, timedelta
from urllib.parse import unquote
import qrcode

from django.conf import settings
from django.contrib import auth
from django.core.paginator import InvalidPage
from django.db import transaction
from django.db.models import Q
from django.http import FileResponse
from django.http import HttpResponseRedirect, HttpResponse
from django.shortcuts import render, reverse
from django.utils.decorators import method_decorator
from django.utils.six import BytesIO
from django.utils.translation import gettext_lazy as _
from django.views.decorators.csrf import csrf_exempt
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

from maipassport.citadel.models import User, Role
from maipassport.citadel.services import logger_writer
from maipassport.companies.models import (Company, Department, Title, UserCompanyTable, CompanyDefaultPrint, Place,
                                          AddRequest, UserCompanyHistory, NewCompanyApply, ActionLog)
from maipassport.core.exceptions import PhoneFormatWrong, UserNotExists, AccountAlreadyBindPhone
from maipassport.core.services import OtpService
from maipassport.core.utils import CachedPaginator
from maipassport.core.utils import (get_utc_format_today, utc_time_to_local_time, aes_dec_data, get_timestamp,
                                    local_time_to_utc_time, des_dec_data)
from maipassport.records.models import Questionnaire, QuestionnaireField, PlaceEntryRecord, ApproachRecord, HealthRecord
from maipassport.users.models import token_generator, AppUser, HealthCode, AttendanceStatus
from maipassport.users.services import AppUserServices


# TODO: 暫時不用
# 重定向裝飾器，只有App User 可以進入網頁，原生登入
def login_required3(func):
    def wrapper(*args, **kwargs):
        request = args[0]
        if 'token' not in kwargs or 'user_id' not in kwargs:
            # TODO: 無token，導入錯誤頁
            request.session['message'] = _('User token or id not exists')
        else:
            if request.path.startswith('/app/scan/'):
                app_user = AppUser.objects.filter(api_token=kwargs['token'], pub_id=kwargs['user_id'])
                if not app_user.exists():
                    # TODO: Token 錯誤，導入登入頁
                    if hasattr(request.user, 'appuser') and request.user.is_authenticated:
                        auth.logout(request)
                    request.session['message'] = _('User token or id not exists')
                    return HttpResponseRedirect(reverse('app_login'))
                else:
                    app_user = app_user.first()
                    auth.login(request, app_user.auth_user)
                    request.app_user = app_user
                    return func(*args, **kwargs)
            elif request.user.is_authenticated and hasattr(request.user, 'appuser'):
                # 檢查有沒有此AppUser
                app_user = AppUser.objects.filter(api_token=kwargs['token'], pub_id=kwargs['user_id'])
                if not app_user.exists():
                    # TODO: Token 錯誤，導入登入頁
                    if hasattr(request.user, 'appuser') and request.user.is_authenticated:
                        auth.logout(request)
                    request.session['message'] = _('User token or id not exists')
                    return HttpResponseRedirect(reverse('app_login'))
                else:
                    # TODO: 此App user 是否屬於此auth_user
                    request.app_user = app_user.first()
                    user_company = request.app_user.usercompanytable_set.filter(default_show=True)
                    if user_company.exists():
                        request.company = user_company.first().company
                    return func(*args, **kwargs)
            else:
                return HttpResponseRedirect(reverse('app_login'))
    return wrapper


# 重定向裝飾器，重新接入
def login_required2(func):
    def wrapper(*args, **kwargs):
        request = args[0]
        if 'token' not in kwargs or 'user_id' not in kwargs:
            # TODO: 無token，導入錯誤頁
            # request.session['message'] = _('User token or id not exists')
            request.session['message'] = _('Verification failed, Please login again')
            if not request.session.get('iii_login'):
                return HttpResponseRedirect(reverse('app_login'))
            else:
                return HttpResponseRedirect(reverse('message_html'))
        else:
            if request.path.startswith('/app/scan/'):
                # app_user = AppUser.objects.filter(api_token=kwargs['token'], pub_id=kwargs['user_id'])
                app_user = AppUser.objects.filter(pub_id=kwargs['user_id'])
                if not app_user.exists():
                    # TODO: Token 錯誤，導入登入頁
                    if hasattr(request.user, 'appuser') and request.user.is_authenticated:
                        auth.logout(request)
                    request.session['message'] = _('Verification failed, Please login again')
                    if not request.session.get('iii_login'):
                        return HttpResponseRedirect(reverse('app_login'))
                    else:
                        return HttpResponseRedirect(reverse('message_html'))
                else:
                    # TODO: 檢查token是否過期
                    app_user = app_user.first()
                    if not request.session.get('iii_login'):
                        if app_user.token_expire_time:
                            if app_user.token_expire_time < local_time_to_utc_time(datetime.now()):
                                if hasattr(request.user, 'appuser') and request.user.is_authenticated:
                                    auth.logout(request)
                                # request.session['message'] = _('Verification failed, Please login again')
                                # return HttpResponseRedirect(reverse('message_html'))
                                request.session['message'] = _('The connection phase has expired, please log in again')
                                return HttpResponseRedirect(reverse('app_login'))
                        else:
                            # request.app_user.token_expire_time = datetime.now() + timedelta(hours=8)
                            request.app_user.token_expire_time = datetime.now() + timedelta(days=7)
                            request.app_user.save(update_fields=['token_expire_time'])
                    auth.login(request, app_user.auth_user)
                    request.app_user = app_user
                    user_company = request.app_user.usercompanytable_set.filter(default_show=True)
                    if user_company.exists():
                        request.company = user_company.first().company
                    return func(*args, **kwargs)
            elif request.user.is_authenticated and hasattr(request.user, 'appuser'):
                # if request.session.get('new_login'):
                #     new_login = request.session.pop('new_login')
                # else:
                #     new_login = 0
                # TODO: 檢查跟當前是否同一人
                # if (request.user.appuser.pub_id != kwargs['user_id'] or
                #         request.user.appuser.api_token != kwargs['token']):
                if request.user.appuser.pub_id != kwargs['user_id']:
                    if hasattr(request.user, 'appuser') and request.user.is_authenticated:
                        auth.logout(request)
                    request.session['message'] = _('Verification failed, Please login again')
                    if not request.session.get('iii_login'):
                        return HttpResponseRedirect(reverse('app_login'))
                    else:
                        return HttpResponseRedirect(reverse('message_html'))
                # TODO: 檢查有沒有此AppUser
                # app_user = AppUser.objects.filter(api_token=kwargs['token'], pub_id=kwargs['user_id'])
                app_user = AppUser.objects.filter(pub_id=kwargs['user_id'])
                if not app_user.exists():
                    # TODO: Token 錯誤，導入登入頁
                    if hasattr(request.user, 'appuser') and request.user.is_authenticated:
                        auth.logout(request)
                    request.session['message'] = _('Verification failed, Please login again')
                    logger_writer('SYSTEM', 'info', 'LOGIN_ERROR', f'User {app_user.auth_user}: Verification failed')
                    if not request.session.get('iii_login'):
                        return HttpResponseRedirect(reverse('app_login'))
                    else:
                        return HttpResponseRedirect(reverse('message_html'))
                else:
                    # TODO: 檢查token是否過期
                    request.app_user = app_user.first()
                    if not request.session.get('iii_login'):
                        if request.app_user.token_expire_time:
                            if request.app_user.token_expire_time < local_time_to_utc_time(datetime.now()):
                                if hasattr(request.user, 'appuser') and request.user.is_authenticated:
                                    auth.logout(request)
                                request.session['message'] = _('The connection phase has expired, please log in again')
                                logger_writer('SYSTEM', 'info', 'LOGIN_ERROR', f'User {app_user.auth_user}: Connection phase has expired')
                                return HttpResponseRedirect(reverse('app_login'))
                        else:
                            # request.app_user.token_expire_time = datetime.now() + timedelta(hours=8)
                            request.app_user.token_expire_time = datetime.now() + timedelta(days=7)
                            request.app_user.save(update_fields=['token_expire_time'])
                    user_company = request.app_user.usercompanytable_set.filter(default_show=True)
                    if user_company.exists():
                        request.company = user_company.first().company
                    return func(*args, **kwargs)
            else:
                request.session['message'] = _('Verification failed, Please login again')
                logger_writer('SYSTEM', 'info', 'LOGIN_ERROR', f'Verification failed')
                if not request.session.get('iii_login'):
                    return HttpResponseRedirect(reverse('app_login'))
                else:
                    return HttpResponseRedirect(reverse('message_html'))
    return wrapper


def message_html(request):
    return_data = dict()
    if request.session.get('message'):
        return_data['return_messages'] = request.session.pop('message')
    return render(request, 'app_web_n/message.html', context=return_data)


@method_decorator(csrf_exempt)
def app_login(request):
    # Django 2.2以上才會有
    if 'Device' in request.headers:
        request.session['DEVICE'] = request.headers['Device']

    if request.user.is_authenticated:
        if request.session.get('iii_login'):
            request.session.pop('iii_login')
            auth.logout(request)
            return HttpResponseRedirect(reverse('app_login'))
        if hasattr(request.user, 'appuser'):
            if 'new_user' in request.user.appuser.user_detail and request.user.appuser.user_detail['new_user']:
                request.session['app_user'] = request.user.appuser
                return HttpResponseRedirect(reverse('fst_login'))
            return HttpResponseRedirect(
                reverse('app_index', kwargs={'user_id': request.user.appuser.pub_id,
                                             'token': request.user.appuser.api_token}))
    return_data = dict()
    if request.COOKIES.get('remember_account'):
        return_data['account'] = des_dec_data(request.COOKIES.get('remember_account')).decode()
        return_data['remember_checkbox'] = 'on'
    if request.method == 'POST':
        account = request.POST.get('user_account')
        password = request.POST.get('user_pwd')
        web_latitude = request.POST.get('web_latitude')
        web_longitude = request.POST.get('web_longitude')
        remember_checkbox = request.POST.get('remember_checkbox')
        if remember_checkbox:
            request.set_account = True
            return_data['account'] = account
            return_data['remember_checkbox'] = 'on'
        else:
            request.set_account = False
        if account and password:
            try:
                user = auth.authenticate(request, username=account, password=password)

                if user is not None:
                    auth.login(request, user)
                    if request.session.get('iii_login'):
                        request.session.pop('iii_login')

                    # user.appuser.token_expire_time = datetime.now() + timedelta(hours=8)
                    user.appuser.token_expire_time = datetime.now() + timedelta(days=7)
                    user.appuser.api_token = token_generator()
                    user.appuser.save(update_fields=['api_token', 'modified', 'token_expire_time'])
                    request.app_user = user.appuser

                    # TODO: 紀錄登錄地
                    if web_latitude and web_longitude:
                        PlaceEntryRecord.objects.create(app_user=request.app_user,
                                                        location={
                                                            'latlon_longitude': web_latitude,
                                                            'latlon_latitude': web_longitude
                                                        })

                else:
                    return_data['message'] = _('Please check your username and password is correct')
                    logger_writer('SYSTEM', 'error', 'LOGIN_ERROR', f'Username or Password not Incorrect')
                    return render(request, 'app_web_n/login.html', context=return_data)
            except Exception as e:
                return_data['message'] = _('System Error.')
                logger_writer('SYSTEM', 'error', 'LOGIN', f'System Error')
                return render(request, 'app_web_n/login.html', context=return_data)

            return HttpResponseRedirect(
                    reverse('app_index', kwargs={
                        'user_id': request.app_user.pub_id,
                        'token': request.app_user.api_token
                    }))
    if request.session.get('message'):
        return_data['message'] = request.session.pop('message')
    return render(request, 'app_web_n/login.html', context=return_data)


@method_decorator(csrf_exempt)
def app_login_new(request):
    if request.GET.get('token'):
        login_token = request.GET.urlencode().split('token=')[1]
        if login_token:
            dec_data = aes_dec_data(urlsafe_b64decode(unquote(login_token)), settings.III_ENC_IV.encode())
            dec_data_list = dec_data.decode().replace('\x00', '').split('\t')
            user_id_from_login = dec_data_list[0]
            login_time = dec_data_list[1]
            login_time_obj = datetime.strptime(login_time, "%Y%m%d%H%M%S")
            login_timestamp = round(login_time_obj.timestamp() * 1000)
            timestamp_now = get_timestamp()
            try:
                diff_seconds = abs(timestamp_now - login_timestamp) / 1000
            except ValueError:
                # TODO: 時間錯誤
                request.session['message'] = _('Client time error')
                logger_writer('SYSTEM', 'error', 'NEW_LOGIN', f'Client time error')
            else:
                if diff_seconds > 1200:
                    # TODO: 時間太久
                    request.session['message'] = _('Client time is way too different from server time')
                    logger_writer('SYSTEM', 'error', 'NEW_LOGIN', f'Client time error')
                else:
                    with transaction.atomic():
                        # app_user = AppUser.objects.filter(
                        #     Q(auth_user__username=user_id_from_login) | Q(alias_id=user_id_from_login) |
                        #     Q(email=user_id_from_login) | Q(phone=user_id_from_login))
                        app_user = AppUser.objects.filter(auth_user__username=user_id_from_login)
                        if app_user.exists():
                            app_user = app_user.first()
                            # app_user.token_expire_time = login_time_obj + timedelta(minutes=5)
                            app_user.api_token = login_token
                            app_user.save(update_fields=['token_expire_time', 'modified', 'api_token'])
                            auth.login(request, app_user.auth_user)
                            request.app_user = app_user
                        else:
                            # TODO:無此使用者，建立新帳號
                            try:
                                app_user = AppUserServices.create_app_user(user_account=user_id_from_login,
                                                                           password=token_generator(8),
                                                                           user_pub_key=token_generator(8))
                            except Exception as e:
                                # TODO: 建立失敗
                                request.session['message'] = _('Create User failed')
                                logger_writer('SYSTEM', 'info', 'NEW_LOGIN', f'Create user failed')
                                return HttpResponseRedirect(reverse('message_html'))
                            else:
                                app_user.alias_id = user_id_from_login
                                #  TODO: 透過資策會無密碼，標記密碼可重設
                                app_user.user_detail = {'new_user': True}
                                # app_user.token_expire_time = login_time_obj + timedelta(minutes=5)
                                app_user.api_token = login_token
                                app_user.save(update_fields=[
                                    'alias_id', 'token_expire_time', 'api_token', 'user_detail', 'modified'])
                                auth.login(request, app_user.auth_user)
                                request.app_user = app_user
                                # app_user.auth_user.first_name = user_sign_up_data['user_real_name']
                                # app_user.auth_user.save(update_fields=['first_name'])
                        try:
                            rep_data = AppUserServices.iii_user_profile(user_id_from_login)
                        except Exception as e:
                            logger_writer('SYSTEM', 'error', 'NEW_LOGIN', f'Get iii user info failed')
                            pass
                        else:
                            logger_writer('SYSTEM', 'info', 'NEW_LOGIN', f'Get iii user info success, {rep_data}')
                            if 'name' in rep_data:
                                if app_user.auth_user.first_name:
                                    if app_user.auth_user.first_name != rep_data['name']:
                                        app_user.auth_user.first_name = rep_data['name']
                                        app_user.auth_user.save(update_fields=['first_name'])
                                    else:
                                        pass
                                else:
                                    app_user.auth_user.first_name = rep_data['name']
                                    app_user.auth_user.save(update_fields=['first_name'])
                            if 'avatar' in rep_data and rep_data['avatar'] != '':
                                if app_user.user_picture:
                                    pic_url = settings.III_URL + rep_data['avatar']
                                    if app_user.user_picture != pic_url:
                                        app_user.user_picture = pic_url
                                        app_user.save(update_fields=['user_picture', 'modified'])
                                else:
                                    app_user.user_picture = settings.III_URL + rep_data['avatar']
                                    app_user.save(update_fields=['user_picture', 'modified'])
                            if 'deptName' in rep_data:
                                iii_company = Company.objects.filter(name='資訊工業策進會')
                                if iii_company.exists():
                                    iii_company = iii_company.first()
                                else:
                                    iii_company = Company.objects.create(name='資訊工業策進會')
                                company_dep = iii_company.department_set.filter(name=rep_data['deptName'])
                                if company_dep.exists():
                                    company_dep = company_dep.first()
                                else:
                                    company_dep = Department.objects.create(name=rep_data['deptName'],
                                                                            company=iii_company)
                                user_company = app_user.usercompanytable_set.filter(company=iii_company)
                                if user_company.exists():
                                    if not user_company.filter(department=company_dep).exists():
                                        company_title = Title.objects.get(name='職員')
                                        user_company_n = UserCompanyTable.objects.create(
                                            app_user=app_user, company=iii_company, department=company_dep,
                                            title=company_title, default_show=True, employed=True)
                                        UserCompanyHistory.objects.create(start_time=user_company_n.created,
                                                                          user_company_table=user_company_n)
                                        other_dep = user_company.exclude(department=company_dep)
                                        if other_dep.exists():
                                            for other_user_company in other_dep:
                                                other_user_company.employed = False
                                                other_user_company.save(update_fields=['employed', 'modified'])
                                else:
                                    company_title = Title.objects.get(name='職員')
                                    user_company_n = UserCompanyTable.objects.create(
                                        app_user=app_user, company=iii_company, department=company_dep,
                                        title=company_title, default_show=True, employed=True)
                                    UserCompanyHistory.objects.create(start_time=user_company_n.created,
                                                                      user_company_table=user_company_n)
                                if not AttendanceStatus.objects.filter(app_user=app_user, company=iii_company).exists():
                                    AttendanceStatus.objects.create(app_user=app_user, company=iii_company)
                        # request.session['new_login'] = 1
                        request.session['iii_login'] = 1
                        return HttpResponseRedirect(
                            reverse('app_index', kwargs={
                                'user_id': request.app_user.pub_id,
                                'token': request.app_user.api_token
                            }))
        else:
            # TODO: 錯誤跳轉
            request.session['message'] = _('Verification failed, Please login again')
            logger_writer('SYSTEM', 'info', 'NEW_LOGIN', f'Verification failed')
    else:
        # TODO: 錯誤跳轉
        request.session['message'] = _('Verification failed, Please login again')
        logger_writer('SYSTEM', 'info', 'NEW_LOGIN', f'Verification failed')
    return HttpResponseRedirect(reverse('message_html'))


# @login_required2
# TODO: 暫時不用
def app_logout(request):
    auth.logout(request)
    return HttpResponseRedirect(reverse('app_login'))


def app_sign_up(request):
    return_data = dict()
    if request.method == 'POST':
        # account = request.POST.get('account')
        phone = request.POST.get('phone')
        user_real_name = request.POST.get('user_real_name')
        password = request.POST.get('user_pwd')
        chk_password = request.POST.get('chk_user_pwd')
        if phone and user_real_name and password and chk_password:
            try:
                phone = AppUserServices.check_phone(phone)
            except PhoneFormatWrong:
                # TODO: 電話格式錯誤
                return_data['message'] = _('Phone format error')
            else:
                if User.objects.filter(username=phone).exists():
                    # TODO: 帳號存在
                    return_data['message'] = _('This phone already exists')
                    return render(request, 'app_web_n/sign_up.html', context=return_data)
                elif password != chk_password:
                    # TODO: 密碼跟確認密碼不相同
                    return_data['message'] = _('The password and verify password not same')
                    return render(request, 'app_web_n/sign_up.html', context=return_data)
                else:
                    request.session['user_sign_up_data'] = {
                        # 'account': account,
                        'password': password,
                        'user_real_name': user_real_name,
                        'phone': phone,
                    }
                    # return render(request, 'app_web_n/sign_up_otc.html', context=return_data)
                    return HttpResponseRedirect(reverse('app_sign_up_otc'))

    return render(request, 'app_web_n/sign_up.html', context=return_data)


def app_sign_up_otc(request):
    return_data = dict()
    if not request.session.get('user_sign_up_data'):
        return HttpResponseRedirect(reverse('app_sign_up'))
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
                logger_writer('SYSTEM', 'info', 'APP_SIGN_UP', f'OTP error')
                return render(request, 'app_web_n/sign_up_otc.html', context=return_data)
            else:
                try:
                    app_user = AppUserServices.create_app_user(user_account=user_sign_up_data['phone'],
                                                               password=user_sign_up_data['password'],
                                                               user_pub_key=token_generator(8))
                except Exception as e:
                    # TODO: 建立失敗
                    request.session['message'] = _('Create User failed')
                    logger_writer('SYSTEM', 'info', 'APP_SIGN_UP', f'User Create Failed')
                    return HttpResponseRedirect(reverse('app_login'))
                else:
                    app_user.phone = user_sign_up_data['phone']
                    app_user.save(update_fields=['phone', 'modified'])
                    app_user.auth_user.first_name = user_sign_up_data['user_real_name']
                    app_user.auth_user.save(update_fields=['first_name'])
                    request.session.pop('user_sign_up_data')
                    request.session['message'] = _('Registration success, Please login again')
                    logger_writer('SYSTEM', 'info', 'APP_SIGN_UP', f'Registration Success')
                    return HttpResponseRedirect(reverse('app_login'))
        else:
            return_data['message'] = _('Field missing')
    return render(request, 'app_web_n/sign_up_otc.html', context=return_data)


def forget_pass(request):
    return_data = dict()
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
                logger_writer('SYSTEM', 'info', 'FORGET_PASS', f'OPT Error')
            else:
                # if send_target.isdigit():
                #     try:
                #         dial_code, send_target = AppUserServices.change_phone(send_target)
                #     except PhoneFormatWrong:
                #         # TODO: 電話格式錯誤
                #         return_data['message'] = _('Phone format error')
                #         return HttpResponseRedirect(reverse('login'))
                request.session['app_user'] = app_user
                return HttpResponseRedirect(reverse('reset_pass'))

    return render(request, 'app_web_n/forget_password.html', context=return_data)


def reset_pass(request):
    return_data = dict()
    if request.method == 'POST':
        app_user = request.session.get('app_user')
        password = request.POST.get('password')
        chkpassword = request.POST.get('chkpassword')
        if app_user and password and chkpassword:
            if password != chkpassword:
                # TODO: 密碼跟確認密碼不相同
                return_data['message'] = _('The password and verify password not same')
                logger_writer('SYSTEM', 'info', 'RESET_PASS', f'Password Reset Failed')
                return render(request, 'app_web_n/forget_password.html', context=return_data)
            else:
                # auth_user = User.objects.get(id=app_user.auth_user.id)
                app_user.auth_user.set_password(password)
                app_user.auth_user.save()
                request.session.pop('app_user')
                request.session['message'] = _('Password has been reset, please log in again')
                logger_writer('SYSTEM', 'info', 'RESET_PASS', f'User: {app_user}, Password Reset Success')
                return HttpResponseRedirect(reverse('app_login'))
    return render(request, 'app_web_n/reset_password.html', context=return_data)


def first_time_login(request):
    return_data = dict()
    if request.method == 'POST':
        account = request.POST.get('account')
        phone = request.POST.get('phone')
        otp = request.POST.get('otp')
        otp_id = request.POST.get('otp_id')
        if account and phone and otp and otp_id:
            app_user = AppUser.objects.filter(auth_user__username=account)
            if not app_user.exists():
                return_data['message'] = UserNotExists.msg
                return render(request, 'app_web_n/first_time_login.html', context=return_data)
            else:
                if not app_user.filter(user_detail__new_user=True).exists():
                    return_data['message'] = AccountAlreadyBindPhone.msg
                    return render(request, 'app_web_n/first_time_login.html', context=return_data)
                else:
                    app_user = app_user.first()
            try:
                phone_dict = AppUserServices.change_phone(phone)
            except PhoneFormatWrong:
                return_data['message'] = PhoneFormatWrong.msg
            else:
                try:
                    OtpService(otp_id).verify(otp, verify_phone=phone_dict['fix_phone'])
                except Exception as e:
                    return_data['message'] = _('Verify Otp Error, Please resend Otp')
                else:
                    app_user.phone = phone_dict['fix_phone']
                    app_user.save(update_fields=['phone', 'modified'])
                    request.session['app_user'] = app_user
                return HttpResponseRedirect(reverse('fst_set_pwd'))
        else:
            return_data['message'] = _('Field missing')
    return render(request, 'app_web_n/first_time_login.html', context=return_data)


def first_time_set_pwd(request):
    return_data = dict()
    if request.method == 'POST':
        # TODO: 暫時不用
        app_user = request.session.get('app_user')
        password = request.POST.get('password')
        chkpassword = request.POST.get('chkpassword')
        if app_user and password and chkpassword:
            if password != chkpassword:
                # TODO: 密碼跟確認密碼不相同
                return_data['message'] = _('The password and verify password not same')
                return render(request, 'app_web_n/first_time_login.html', context=return_data)
            else:
                user_detail = app_user.user_detail
                user_detail.pop('new_user')
                app_user.user_detail = user_detail
                app_user.save(update_fields=['user_detail', 'modified'])
                app_user.auth_user.set_password(password)
                app_user.auth_user.save()
                request.session['message'] = _('Password has been reset, please log in again')
                return HttpResponseRedirect(reverse('app_login'))
    return render(request, 'app_web_n/first_time_set_pwd.html', context=return_data)


@login_required2
def edit_password_otp(request, user_id, token):
    return_data = dict()
    if request.method == 'POST':
        otp = request.POST.get('otp')
        otp_id = request.POST.get('otp_id')
        if otp and otp_id:
            try:
                OtpService(otp_id).verify(otp, verify_phone=request.app_user.phone)
            except Exception as e:
                return_data['message'] = _('Verify Otp Error, Please resend Otp')
            else:
                return HttpResponseRedirect(reverse('edit_password', kwargs={'user_id': user_id, 'token': token}))

    return render(request, 'app_web_n/edit_pwd_otp.html', context=return_data)


@login_required2
def edit_password(request, user_id, token):
    return_data = dict()
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
                # return HttpResponseRedirect(reverse('app_index', kwargs={'user_id': user_id, 'token': token}))
                return HttpResponseRedirect(reverse('user_profile', kwargs={'user_id': user_id, 'token': token}))
    return render(request, 'app_web_n/edit_pwd.html', context=return_data)


@login_required2
def shop_qrcode(request, user_id, token):
    return_data = dict()
    if request.method == 'POST':
        location_dict = dict()
        shop_name = request.POST.get('shop_name')
        shop_address = request.POST.get('shop_address')
        shop_phone = request.POST.get('shop_phone')
        register_code = request.POST.get('register_code')
        company = Company.objects.filter(verification_code=register_code)
        if company.exists():
            if Place.objects.filter(name=shop_name).exists():
                return_data['message'] = _('This Shop Name has already been used')
            # else:
            #     if Place.objects.filter(
            #             name=shop_name,
            #             company_verify__in=[Place.VERIFY_PASS, Place.NOT_VERIFY]).exists():
            #         return_data['message'] = _('This Company name has already been used')
            #     else:
            if shop_address:
                if type(shop_address) != dict:
                    location_dict = {'location_address': shop_address}
                else:
                    location_dict['location_address'] = shop_address
            Place.objects.create(
                name=shop_name,
                location=location_dict,
                place_contact_phone=shop_phone,
                place_user=request.app_user,
                company_id=company.first().id,
            )
            ActionLog.objects.create(user_account=request.user, log_type='Place_Add')
            request.session['message'] = _('Application has been submitted')
            request.session['show_list'] = True
            return HttpResponseRedirect(reverse('shop_qrcode', kwargs={'user_id': user_id, 'token': token}))
        else:
            return_data['message'] = _('Invalid Registration Code')

    if request.session.get('message'):
        return_data['message'] = request.session.pop('message')
    if request.session.get('show_list'):
        return_data['show_list'] = request.session.pop('show_list')
    return_data['applicant'] = request.app_user
    return render(request, 'app_web_n/shop_qrcode.html', context=return_data)


@login_required2
def shop_qrcode_cancel(request, user_id, token):
    apply_id = request.POST.get('apply_id')
    if not apply_id:
        request.session['message'] = _('Application does not exist')
    else:
        shop_code = Place.objects.filter(pub_id=apply_id)
        if shop_code.exists():
            shop_code = shop_code.first()
            shop_code.company_verify = Place.VERIFY_CANCELLED
            shop_code.save(update_fields=['company_verify', 'modified'])
            request.session['message'] = _('Application has been cancel')
        else:
            request.session['message'] = _('Application does not exist')
    request.session['show_list'] = True

    return HttpResponseRedirect(reverse('shop_qrcode', kwargs={'user_id': user_id, 'token': token}))


@login_required2
def shop_qrcode_edit(request, user_id, token):
    return_data = dict()
    location_dict = dict()
    # pub_id = request.GET.get('place_id')
    if request.method == 'POST':
        pub_id = request.POST.get('shop_pub_id')
        edit_shop_name = request.POST.get('shop_name')
        edit_shop_address = request.POST.get('shop_address')
        edit_shop_phone = request.POST.get('shop_phone')
        place = Place.objects.filter(pub_id=pub_id)
        if place.exists():
            place = place.first()
            if edit_shop_name:
                place.name = edit_shop_name
            if edit_shop_address:
                location_dict['location_address'] = edit_shop_address
                place.location = location_dict
            if edit_shop_phone:
                place.place_contact_phone = edit_shop_phone
            place.save(update_fields=['name', 'location', 'place_contact_phone'])
        return HttpResponseRedirect(reverse('shop_qrcode', kwargs={'user_id': user_id, 'token': token}))
    else:
        pub_id = request.GET.get('place_id')
        place = Place.objects.filter(pub_id=pub_id)
        if place.exists():
            place = place.first()
            return_data['place_user'] = place.place_user.auth_user.first_name
            return_data['place_user_phone'] = place.place_user.phone
            return_data['shop_pub_id'] = place.pub_id
            return_data['shop_name'] = place.name
            return_data['shop_address'] = place.location['location_address']
            return_data['shop_phone'] = place.place_contact_phone

    return render(request, 'app_web_n/shop_qrcode_edit.html', context=return_data)


@login_required2
def app_index(request, user_id, token):
    return_data = dict()
    return_data['qr_data'] = f'USER__{user_id}'
    health_code = request.app_user.healthcode.code
    return_data['health_detail'] = HealthCode.code_choice_detail()[request.app_user.healthcode.code]
    stime, etime = get_utc_format_today()
    if request.app_user.usercompanytable_set.select_related('company').filter(
            employed=True, company__name='資訊工業策進會').exists():
        # TODO: 屬於資策會的人此生有填過By pass
        if not Questionnaire.objects.filter(field_name__type=QuestionnaireField.HEALTH,
                                            app_user=request.app_user,).exists():
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
    # pre_qr_trans = PreUserQRTrans.objects.filter(app_user=request.app_user, return_code=PreUserQRTrans.NO_SCAN)
    # if pre_qr_trans.exists():
    #     pre_qr_trans = pre_qr_trans.first()
    # else:
    #     pre_qr_trans = PreUserQRTrans.objects.create(app_user=request.app_user)
    return_data['last_time_update'] = datetime.strftime(
        utc_time_to_local_time(request.app_user.healthcode.modified), "%Y-%m-%d %H:%M:%S")
    if request.session.get('message'):
        return_data['message'] = request.session.pop('message')
    if request.session.get('send_msg'):
        return_data['send_msg'] = request.session.pop('send_msg')
        return_data['send_user'] = request.session.pop('send_user')
    return render(request, 'app_web_n/index.html', context=return_data)


def show_qr_code(request, color_type, data):
    if color_type == '0':
        # green
        color_str = '#0F7D1A'
    elif color_type == '1':
        # orange
        # color_str = '#D0632B'
        color_str = '#c7370b'
    elif color_type == '2':
        # red
        color_str = '#860406'
    elif color_type == '3':
        # red
        color_str = '#red'
    else:
        # black
        color_str = 'black'
    # img = qrcode.make(data)
    # qr = qrcode.QRCode()
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_H,
        box_size=5,
        border=5
    )
    qr.add_data(data)
    qr.make()
    img = qr.make_image(fill_color=color_str)

    buf = BytesIO()
    img.save(buf)
    image_stream = buf.getvalue()

    return HttpResponse(image_stream, content_type="image/png")


# 重定向裝飾器，只有有權限 可以進入後台
def login_required4(func):
    def wrapper(*args, **kwargs):
        request = args[0]
        if request.user.is_authenticated:
            # TODO:檢查有沒有權限
            if request.user:
                if request.user.role_set.filter(name='Administrator').exists():
                    request.user_role = 'ADMIN'
                elif request.user.role_set.filter(name='Management').exists():
                    if 'pub_id' not in kwargs:
                        if request.user.is_authenticated:
                            auth.logout(request)
                        return HttpResponseRedirect(reverse('backend_login'))
                    user_manage_list = request.user.appuser.usercompanytable_set.select_related(
                        'company', 'department').filter(
                        Q(employed=True, manage_enabled=True) |
                        Q(employed=True, department_manage_enabled=True))
                    for user_manage in user_manage_list:
                        if user_manage.manage_enabled:
                            user_manage.url_pub_id = f'COMPANY__{user_manage.company.pub_id}'
                        elif user_manage.department_manage_enabled:
                            user_manage.url_pub_id = f'DEPARTMENT__{user_manage.department.pub_id}'
                    request.company_manage = user_manage_list
                    request.session['company_manage_id_sel_now'] = kwargs['pub_id']
                    request.user_role = 'MANAGEMENT'
                    manage_list = kwargs['pub_id'].split('__')
                    request.session['manage_role'] = manage_list[0]
                    request.session['manage_id'] = manage_list[1]
                    if manage_list[0] == 'COMPANY' and not user_manage_list.filter(
                            manage_enabled=True, company__pub_id=manage_list[1]).exists():
                        if request.user.is_authenticated:
                            auth.logout(request)
                        return HttpResponseRedirect(reverse('backend_login'))
                    if manage_list[0] == 'DEPARTMENT' and not user_manage_list.filter(
                            department_manage_enabled=True, department__pub_id=manage_list[1]).exists():
                        if request.user.is_authenticated:
                            auth.logout(request)
                        return HttpResponseRedirect(reverse('backend_login'))
                # elif request.user.role_set.filter(name='Department Management').exists():
                #     if 'pub_id' not in kwargs and 'dep_pub_id' not in kwargs:
                #         if request.user.is_authenticated:
                #             auth.logout(request)
                #         return HttpResponseRedirect(reverse('backend_login'))
                #     request.user_role = 'DEP_MANAGEMENT'
                #     request.department_manage = request.user.appuser.usercompanytable_set.select_related(
                #         'company').filter(department_manage_enabled=True, company__pub_id=kwargs['pub_id'])
                #     request.session['company_manage_id_sel_now'] = kwargs['pub_id']
                #     request.session['department_manage_id_sel_now'] = kwargs['dep_pub_id']
                else:
                    if request.user.is_authenticated:
                        auth.logout(request)
                    return HttpResponseRedirect(reverse('backend_login'))
            return func(*args, **kwargs)
        else:
            return HttpResponseRedirect(reverse('backend_login'))
    return wrapper


def backend_login(request):
    if request.user.is_authenticated:
        if request.user.role_set.filter(name='Administrator').exists():
            return HttpResponseRedirect(reverse('backend_index'))
        if request.user.role_set.filter(name='Management').exists():
            # company_pub_id = request.user.appuser.usercompanytable_set.select_related(
            #     'company').filter(manage_enabled=True).distinct('app_user')[0].company.pub_id
            user_manage_list = request.user.appuser.usercompanytable_set.select_related(
                'company', 'department').filter(
                Q(employed=True, manage_enabled=True) |
                Q(employed=True, department_manage_enabled=True))
            # for user_manage in user_manage_list:
            #     if user_manage.manage_enabled:
            #         user_manage.url_pub_id = f'COMPANY__{user_manage.company.pub_id}'
            #     elif user_manage.department_manage_enabled:
            #         user_manage.url_pub_id = f'DEPARTMENT__{user_manage.department.pub_id}'
            # request.company_manage = user_manage_list
            default_show = user_manage_list.filter(default_show=True)
            if default_show.exists():
                default_show = default_show.first()
                if default_show.manage_enabled:
                    url_pub_id = f'COMPANY__{default_show.company.pub_id}'
                else:
                    url_pub_id = f'DEPARTMENT__{default_show.department.pub_id}'
            else:
                user_manage = user_manage_list.first()
                if user_manage.manage_enabled:
                    url_pub_id = f'COMPANY__{ user_manage.company.pub_id}'
                else:
                    url_pub_id = f'DEPARTMENT__{ user_manage.department.pub_id}'
            return HttpResponseRedirect(reverse('company_index', kwargs={'pub_id': url_pub_id}))
        # if request.user.role_set.filter(name='Management').exists():
        #     user_company = request.user.appuser.usercompanytable_set.select_related(
        #         'company').filter(manage_enabled=True)
        #     company_pub_id = user_company.distinct('app_user')[0].company.pub_id
        #     department_pub_id = user_company.distinct('app_user')[0].department.pub_id
        #     return HttpResponseRedirect(reverse('department_index',
        #                                         kwargs={'pub_id': company_pub_id,
        #                                                 'dep_pub_id': department_pub_id}))
    return_data = dict()
    if request.method == 'POST':
        account = request.POST.get('account')
        password = request.POST.get('password')
        if account and password:
            user = auth.authenticate(request, username=account, password=password)
            if user is not None:
                auth.login(request, user)
                ActionLog.objects.create(user_account=request.user, log_type='Backend_User_Login')
                # user.appuser.api_token = token_generator()
                # user.appuser.save(update_fields=['api_token', 'modified'])
                # request.app_user = user.appuser
                if user.role_set.filter(name='Management').exists():
                    user_manage_list = user.appuser.usercompanytable_set.select_related(
                        'company', 'department').filter(
                        Q(employed=True, manage_enabled=True)|
                        Q(employed=True, department_manage_enabled=True))
                    # for user_manage in user_manage_list:
                    #     if user_manage.manage_enabled:
                    #         user_manage.url_pub_id = f'COMPANY__{user_manage.company.pub_id}'
                    #     elif user_manage.department_manage_enabled:
                    #         user_manage.url_pub_id = f'DEPARTMENT__{user_manage.department.pub_id}'
                    # request.company_manage = user_manage_list
                    if user_manage_list:
                        default_show = user_manage_list.filter(default_show=True)
                        if default_show.exists():
                            default_show = default_show.first()
                            if default_show.manage_enabled:
                                url_pub_id = f'COMPANY__{default_show.company.pub_id}'
                            else:
                                url_pub_id = f'DEPARTMENT__{default_show.department.pub_id}'
                        else:
                            user_manage = user_manage_list.first()
                            if user_manage.manage_enabled:
                                url_pub_id = f'COMPANY__{user_manage.company.pub_id}'
                            else:
                                url_pub_id = f'DEPARTMENT__{user_manage.department.pub_id}'
                        return HttpResponseRedirect(reverse('company_index', kwargs={'pub_id': url_pub_id}))
                    else:
                        request.session['return_msg'] = _('Please confirm login information is correct.')
                # elif user.role_set.filter(name='Department Management').exists():
                #     user_company = user.appuser.usercompanytable_set.select_related(
                #         'company', 'department').filter(department_manage_enabled=True, default_show=True).first()
                #     return HttpResponseRedirect(reverse('department_index',
                #                                         kwargs={'pub_id': user_company.company.pub_id,
                #                                                 'dep_pub_id': user_company.department.pub_id}))
                elif user.role_set.filter(name='Administrator').exclude(name='Management').exists():
                    return HttpResponseRedirect(reverse('backend_index'))
                else:
                    request.session['return_msg'] = _('Please confirm login information is correct.')
            else:
                request.session['return_msg'] = _('Please confirm login information is correct.')
        else:
            request.session['return_msg'] = _('Please confirm login information is correct.')
    if request.session.get('return_msg'):
        return_data['return_msg'] = request.session.pop('return_msg')
    return render(request, 'backend/login.html', context=return_data)


def backend_logout(request):
    auth.logout(request)
    return HttpResponseRedirect(reverse('backend_login'))


@login_required4
def backend_index(request):
    return_data = dict()
    stime, etime = get_utc_format_today()
    return_data['date_list'] = list()
    return_data['approach_count'] = list()
    return_data['place_count'] = list()

    max_num = 2

    # 七天紀錄
    approach_record = ApproachRecord.objects.select_related('app_user').filter(
        modified__range=((stime - timedelta(days=6)), etime)).order_by('-created')
    place_entry_record = PlaceEntryRecord.objects.select_related('app_user', 'place_entry').filter(
        modified__range=((stime - timedelta(days=6)), etime)).order_by('-created')
    danger_record_list = HealthRecord.objects.select_related(
        'app_user', 'app_user__healthcode', 'approach_record').filter(
        modified__range=(stime, etime),
        health_code__in=[HealthCode.DANGER, HealthCode.QUEST_DANGER]).order_by('-created')
    # 七天前當日
    return_data['date_list'].append((etime - timedelta(days=6)).strftime('%Y-%m-%d'))
    return_data['start_time'] = (etime - timedelta(days=6)).strftime('%Y-%m-%d')
    approach_count = approach_record.filter(
        modified__range=((stime - timedelta(days=6)), (etime - timedelta(days=6)))).count()
    place_entry_count = place_entry_record.filter(
        modified__range=((stime - timedelta(days=6)), (etime - timedelta(days=6)))).count()
    return_data['approach_count'].append(approach_count)
    return_data['place_count'].append(place_entry_count)
    if approach_count > max_num:
        max_num = approach_count + 3
    if place_entry_count > max_num:
        max_num = place_entry_count + 3
    # 六天前當日
    return_data['date_list'].append((etime - timedelta(days=5)).strftime('%Y-%m-%d'))
    approach_count = approach_record.filter(
        modified__range=((stime - timedelta(days=5)), (etime - timedelta(days=5)))).count()
    place_entry_count = place_entry_record.filter(
        modified__range=((stime - timedelta(days=5)), (etime - timedelta(days=5)))).count()
    return_data['approach_count'].append(approach_count)
    return_data['place_count'].append(place_entry_count)
    if approach_count > max_num:
        max_num = approach_count + 3
    if place_entry_count > max_num:
        max_num = place_entry_count + 3
    # 五天前當日
    return_data['date_list'].append((etime - timedelta(days=4)).strftime('%Y-%m-%d'))
    approach_count = approach_record.filter(
        modified__range=((stime - timedelta(days=4)), (etime - timedelta(days=4)))).count()
    place_entry_count = place_entry_record.filter(
        modified__range=((stime - timedelta(days=4)), (etime - timedelta(days=4)))).count()
    return_data['approach_count'].append(approach_count)
    return_data['place_count'].append(place_entry_count)
    if approach_count > max_num:
        max_num = approach_count + 3
    if place_entry_count > max_num:
        max_num = place_entry_count + 3
    # 四天前當日
    return_data['date_list'].append((etime - timedelta(days=3)).strftime('%Y-%m-%d'))
    approach_count = approach_record.filter(
        modified__range=((stime - timedelta(days=3)), (etime - timedelta(days=3)))).count()
    place_entry_count = place_entry_record.filter(
        modified__range=((stime - timedelta(days=3)), (etime - timedelta(days=3)))).count()
    return_data['approach_count'].append(approach_count)
    return_data['place_count'].append(place_entry_count)
    if approach_count > max_num:
        max_num = approach_count + 3
    if place_entry_count > max_num:
        max_num = place_entry_count + 3
    # 前天當日
    return_data['date_list'].append((etime - timedelta(days=2)).strftime('%Y-%m-%d'))
    approach_count = approach_record.filter(
        modified__range=((stime - timedelta(days=2)), (etime - timedelta(days=2)))).count()
    place_entry_count = place_entry_record.filter(
        modified__range=((stime - timedelta(days=2)), (etime - timedelta(days=2)))).count()
    return_data['approach_count'].append(approach_count)
    return_data['place_count'].append(place_entry_count)
    if approach_count > max_num:
        max_num = approach_count + 3
    if place_entry_count > max_num:
        max_num = place_entry_count + 3
    # 昨天當日
    return_data['date_list'].append((etime - timedelta(days=1)).strftime('%Y-%m-%d'))
    approach_count = approach_record.filter(
        modified__range=((stime - timedelta(days=1)), (etime - timedelta(days=1)))).count()
    place_entry_count = place_entry_record.filter(
        modified__range=((stime - timedelta(days=1)), (etime - timedelta(days=1)))).count()
    return_data['approach_count'].append(approach_count)
    return_data['place_count'].append(place_entry_count)
    if approach_count > max_num:
        max_num = approach_count + 3
    if place_entry_count > max_num:
        max_num = place_entry_count + 3
    # 今天
    return_data['date_list'].append((etime).strftime('%Y-%m-%d'))
    approach_count = approach_record.filter(modified__range=(stime, etime)).count()
    place_entry_count = place_entry_record.filter(modified__range=(stime, etime)).count()
    return_data['approach_count'].append(approach_count)
    return_data['place_count'].append(place_entry_count)
    if approach_count > max_num:
        max_num = approach_count + 3
    if place_entry_count > max_num:
        max_num = place_entry_count + 3
    page = request.GET.get('page')
    page2 = request.GET.get('page2')
    page3 = request.GET.get('page3')
    if page or page2 or page3:
        return_data['nav_no_reset'] = 1
    else:
        return_data['nav_no_reset'] = 0
    paginator = CachedPaginator(approach_record.select_related(
        'app_user__auth_user', 'app_user').filter(modified__range=(stime, etime)), 5)
    paginator2 = CachedPaginator(place_entry_record.select_related(
        'place_entry', 'app_user').filter(modified__range=(stime, etime)), 5)
    paginator3 = CachedPaginator(danger_record_list, 5)
    try:
        approach_record_list = paginator.get_page(page)
        page_range = paginator.page_range_list(page)
        place_entry_record_list = paginator2.get_page(page2)
        page_range2 = paginator2.page_range_list(page2)
        danger_record_list = paginator3.get_page(page3)
        page_range3 = paginator3.page_range_list(page3)
    except InvalidPage:
        # page error - log
        # request.session['return_msg'] = _('System Error')
        return HttpResponseRedirect(reverse('backend_logout'))
    for record in place_entry_record_list:
        if record.place_entry:
            record.location_place = record.place_entry.name
            record.place_link = True
        else:
            if 'location_address' in record.location:
                record.location_place = record.location['location_address']
            elif 'latlon_latitude' in record.location and 'latlon_longitude' in record.location:
                record.location_place = '緯度:{} / 經度:{}'.format(
                    record.location['latlon_latitude'], record.location['latlon_longitude'])
    for record in danger_record_list:
        if record.approach_record:
            record.scan_user = record.approach_record.scan_user.auth_user.first_name
            record.scan_user_id = record.approach_record.scan_user.pub_id
        else:
            record.scan_user = record.app_user.auth_user.first_name
            record.scan_user_id = record.app_user.pub_id
    return_data['approach_record_list'] = approach_record_list
    return_data['page_range'] = page_range
    return_data['place_entry_record_list'] = place_entry_record_list
    return_data['page_range2'] = page_range2
    return_data['danger_record_list'] = danger_record_list
    return_data['paginator3'] = page_range3
    return_data['end_time'] = etime.strftime('%Y-%m-%d')
    return_data['max_num'] = max_num
    return render(request, 'backend/index.html', context=return_data)


@login_required4
def backend_company_index(request, pub_id):
    return_data = dict()
    manage_role = request.session.get('manage_role')
    manage_id = request.session.get('manage_id')

    stime, etime = get_utc_format_today()
    return_data['date_list'] = list()
    return_data['approach_count'] = list()
    return_data['place_count'] = list()
    if manage_role == 'COMPANY':
        company = Company.objects.filter(pub_id=manage_id)
        if not company.exists():
            return HttpResponseRedirect(reverse('backend_logout'))
        else:
            company = company.first()
        add_req = company.addcompanytag.addrequest_set.filter(status=AddRequest.WAIT_AUDIT)
        if add_req.exists():
            return_data['add_req_num'] = add_req.count()
            return_data['new_add_req'] = True
        else:
            return_data['add_req_num'] = 0
        return_data['company_name'] = company.name
        return_data['add_tag'] = company.addcompanytag.pub_id
        return_data['staff_num'] = company.usercompanytable_set.filter(employed=True).count()
        return_data['department_num'] = company.department_set.count()
        return_data['place_num'] = company.place_set.count()
        max_num = 2
        # 七天紀錄
        approach_record = ApproachRecord.objects.select_related('app_user').filter(
            modified__range=((stime - timedelta(days=6)), etime)).filter(
            Q(app_user__usercompanytable__company=company) |
            Q(scan_user__usercompanytable__company=company)).order_by('-created')
        place_entry_record = PlaceEntryRecord.objects.select_related('app_user', 'place_entry').filter(
            app_user__usercompanytable__company=company,
            place_entry__company=company,
            modified__range=((stime - timedelta(days=6)), etime)).order_by('-created')
        danger_record_list = HealthRecord.objects.select_related(
            'app_user', 'app_user__healthcode', 'approach_record').filter(
            modified__range=(stime, etime),
            health_code__in=[HealthCode.DANGER, HealthCode.QUEST_DANGER]).filter(
            Q(approach_record__app_user__usercompanytable__company=company) |
            Q(approach_record__scan_user__usercompanytable__company=company)
        ).order_by('-created')
        # 七天前當日
        return_data['date_list'].append((etime - timedelta(days=6)).strftime('%Y-%m-%d'))
        return_data['start_time'] = (etime - timedelta(days=6)).strftime('%Y-%m-%d')
        approach_count = approach_record.filter(
            modified__range=((stime - timedelta(days=6)), (etime - timedelta(days=6)))).count()
        place_entry_count = place_entry_record.filter(
            modified__range=((stime - timedelta(days=6)), (etime - timedelta(days=6)))).count()
        return_data['approach_count'].append(approach_count)
        return_data['place_count'].append(place_entry_count)
        if approach_count > max_num:
            max_num = approach_count + 3
        if place_entry_count > max_num:
            max_num = place_entry_count + 3
        # 六天前當日
        return_data['date_list'].append((etime - timedelta(days=5)).strftime('%Y-%m-%d'))
        approach_count = approach_record.filter(
            modified__range=((stime - timedelta(days=5)), (etime - timedelta(days=5)))).count()
        place_entry_count = place_entry_record.filter(
            modified__range=((stime - timedelta(days=5)), (etime - timedelta(days=5)))).count()
        return_data['approach_count'].append(approach_count)
        return_data['place_count'].append(place_entry_count)
        if approach_count > max_num:
            max_num = approach_count + 3
        if place_entry_count > max_num:
            max_num = place_entry_count + 3
        # 五天前當日
        return_data['date_list'].append((etime - timedelta(days=4)).strftime('%Y-%m-%d'))
        approach_count = approach_record.filter(
            modified__range=((stime - timedelta(days=4)), (etime - timedelta(days=4)))).count()
        place_entry_count = place_entry_record.filter(
            modified__range=((stime - timedelta(days=4)), (etime - timedelta(days=4)))).count()
        return_data['approach_count'].append(approach_count)
        return_data['place_count'].append(place_entry_count)
        if approach_count > max_num:
            max_num = approach_count + 3
        if place_entry_count > max_num:
            max_num = place_entry_count + 3
        # 四天前當日
        return_data['date_list'].append((etime - timedelta(days=3)).strftime('%Y-%m-%d'))
        approach_count = approach_record.filter(
            modified__range=((stime - timedelta(days=3)), (etime - timedelta(days=3)))).count()
        place_entry_count = place_entry_record.filter(
            modified__range=((stime - timedelta(days=3)), (etime - timedelta(days=3)))).count()
        return_data['approach_count'].append(approach_count)
        return_data['place_count'].append(place_entry_count)
        if approach_count > max_num:
            max_num = approach_count + 3
        if place_entry_count > max_num:
            max_num = place_entry_count + 3
        # 前天當日
        return_data['date_list'].append((etime - timedelta(days=2)).strftime('%Y-%m-%d'))
        approach_count = approach_record.filter(
            modified__range=((stime - timedelta(days=2)), (etime - timedelta(days=2)))).count()
        place_entry_count = place_entry_record.filter(
            modified__range=((stime - timedelta(days=2)), (etime - timedelta(days=2)))).count()
        return_data['approach_count'].append(approach_count)
        return_data['place_count'].append(place_entry_count)
        if approach_count > max_num:
            max_num = approach_count + 3
        if place_entry_count > max_num:
            max_num = place_entry_count + 3
        # 昨天當日
        return_data['date_list'].append((etime - timedelta(days=1)).strftime('%Y-%m-%d'))
        approach_count = approach_record.filter(
            modified__range=((stime - timedelta(days=1)), (etime - timedelta(days=1)))).count()
        place_entry_count = place_entry_record.filter(
            modified__range=((stime - timedelta(days=1)), (etime - timedelta(days=1)))).count()
        return_data['approach_count'].append(approach_count)
        return_data['place_count'].append(place_entry_count)
        if approach_count > max_num:
            max_num = approach_count + 3
        if place_entry_count > max_num:
            max_num = place_entry_count + 3
        # 今天
        return_data['date_list'].append((etime).strftime('%Y-%m-%d'))
        approach_count = approach_record.filter(modified__range=(stime, etime)).count()
        place_entry_count = place_entry_record.filter(modified__range=(stime, etime)).count()
        return_data['approach_count'].append(approach_count)
        return_data['place_count'].append(place_entry_count)
        if approach_count > max_num:
            max_num = approach_count + 3
        if place_entry_count > max_num:
            max_num = place_entry_count + 3
        page = request.GET.get('page')
        page2 = request.GET.get('page2')
        page3 = request.GET.get('page3')
        if page or page2 or page3:
            return_data['nav_no_reset'] = 1
        else:
            return_data['nav_no_reset'] = 0
        paginator = CachedPaginator(approach_record.select_related(
            'app_user__auth_user', 'app_user').filter(modified__range=(stime, etime)), 5)
        paginator2 = CachedPaginator(place_entry_record.select_related(
            'place_entry', 'app_user').filter(modified__range=(stime, etime)), 5)
        paginator3 = CachedPaginator(danger_record_list, 5)
        try:
            approach_record_list = paginator.get_page(page)
            page_range = paginator.page_range_list(page)
            place_entry_record_list = paginator2.get_page(page2)
            page_range2 = paginator2.page_range_list(page2)
            danger_record_list = paginator3.get_page(page3)
            page_range3 = paginator3.page_range_list(page3)
        except InvalidPage:
            # page error - log
            # request.session['return_msg'] = _('System Error')
            return HttpResponseRedirect(reverse('backend_logout'))
        for record in approach_record_list:
            staff = record.app_user.usercompanytable_set.filter(company=company)
            if staff.exists():
                # record.staff_id = staff.first().pub_id
                record.app_user_link = True
            scan_staff = record.scan_user.usercompanytable_set.filter(company=company)
            if scan_staff.exists():
                # record.scan_staff_id = scan_staff.first().pub_id
                record.scan_user_link = True
        for record in place_entry_record_list:
            staff = record.app_user.usercompanytable_set.filter(company=company)
            if staff.exists():
                # record.staff_id = staff.first().pub_id
                record.app_user_link = True
        for record in danger_record_list:
            if record.approach_record:
                staff = record.app_user.usercompanytable_set.filter(company=company)
                if staff.exists():
                    record.app_user_link = True
                scan_staff = record.approach_record.scan_user.usercompanytable_set.filter(company=company)
                if scan_staff.exists():
                    record.scan_user_link = True
                # record.scan_user = record.approach_record.scan_user.auth_user.first_name
                # record.scan_user_id = record.approach_record.scan_user.pub_id
            else:
                staff = record.app_user.usercompanytable_set.filter(company=company)
                if staff.exists():
                    record.app_user_link = True
                # record.scan_user = record.app_user.auth_user.first_name
                # record.scan_user_id = record.app_user.pub_id
        return_data['approach_record_list'] = approach_record_list
        return_data['page_range'] = page_range
        return_data['place_entry_record_list'] = place_entry_record_list
        return_data['page_range2'] = page_range2
        return_data['danger_record_list'] = danger_record_list
        return_data['paginator3'] = page_range3
        return_data['end_time'] = etime.strftime('%Y-%m-%d')
        return_data['max_num'] = max_num
    else:
        department = Department.objects.filter(pub_id=manage_id)
        if not department.exists():
            return HttpResponseRedirect(reverse('backend_logout'))
        else:
            department = department.first()
        company = department.company
        return_data['company_name'] = company.name
        return_data['department_name'] = department.name
        return_data['staff_num'] = department.usercompanytable_set.filter(employed=True).count()
        max_num = 2
        # 七天紀錄
        approach_record = ApproachRecord.objects.select_related('app_user').filter(
            modified__range=((stime - timedelta(days=6)), etime)).filter(
            Q(app_user__usercompanytable__department=department) |
            Q(scan_user__usercompanytable__department=department)).order_by('-created')
        danger_record_list = HealthRecord.objects.select_related(
            'app_user', 'app_user__healthcode', 'approach_record').filter(
            modified__range=(stime, etime),
            health_code__in=[HealthCode.DANGER, HealthCode.QUEST_DANGER]).filter(
            Q(approach_record__app_user__usercompanytable__department=department) |
            Q(approach_record__scan_user__usercompanytable__department=department)
        ).order_by('-created')

        # 七天前當日
        return_data['date_list'].append((etime - timedelta(days=6)).strftime('%Y-%m-%d'))
        return_data['start_time'] = (etime - timedelta(days=6)).strftime('%Y-%m-%d')
        approach_count = approach_record.filter(
            modified__range=((stime - timedelta(days=6)), (etime - timedelta(days=6)))).count()
        return_data['approach_count'].append(approach_count)
        if approach_count > max_num:
            max_num = approach_count + 3
        # 六天前當日
        return_data['date_list'].append((etime - timedelta(days=5)).strftime('%Y-%m-%d'))
        approach_count = approach_record.filter(
            modified__range=((stime - timedelta(days=5)), (etime - timedelta(days=5)))).count()
        return_data['approach_count'].append(approach_count)
        if approach_count > max_num:
            max_num = approach_count + 3
        # 五天前當日
        return_data['date_list'].append((etime - timedelta(days=4)).strftime('%Y-%m-%d'))
        approach_count = approach_record.filter(
            modified__range=((stime - timedelta(days=4)), (etime - timedelta(days=4)))).count()
        return_data['approach_count'].append(approach_count)
        if approach_count > max_num:
            max_num = approach_count + 3
        # 四天前當日
        return_data['date_list'].append((etime - timedelta(days=3)).strftime('%Y-%m-%d'))
        approach_count = approach_record.filter(
            modified__range=((stime - timedelta(days=3)), (etime - timedelta(days=3)))).count()
        return_data['approach_count'].append(approach_count)
        if approach_count > max_num:
            max_num = approach_count + 3
        # 前天當日
        return_data['date_list'].append((etime - timedelta(days=2)).strftime('%Y-%m-%d'))
        approach_count = approach_record.filter(
            modified__range=((stime - timedelta(days=2)), (etime - timedelta(days=2)))).count()
        return_data['approach_count'].append(approach_count)
        if approach_count > max_num:
            max_num = approach_count + 3
        # 昨天當日
        return_data['date_list'].append((etime - timedelta(days=1)).strftime('%Y-%m-%d'))
        approach_count = approach_record.filter(
            modified__range=((stime - timedelta(days=1)), (etime - timedelta(days=1)))).count()
        return_data['approach_count'].append(approach_count)
        if approach_count > max_num:
            max_num = approach_count + 3
        # 今天
        return_data['date_list'].append((etime).strftime('%Y-%m-%d'))
        approach_count = approach_record.filter(modified__range=(stime, etime)).count()
        return_data['approach_count'].append(approach_count)
        if approach_count > max_num:
            max_num = approach_count + 3
        page = request.GET.get('page')
        page3 = request.GET.get('page3')
        if page or page3:
            return_data['nav_no_reset'] = 1
        else:
            return_data['nav_no_reset'] = 0
        paginator = CachedPaginator(approach_record.select_related(
            'app_user__auth_user', 'app_user').filter(modified__range=(stime, etime)), 5)
        paginator3 = CachedPaginator(danger_record_list, 5)
        try:
            approach_record_list = paginator.get_page(page)
            page_range = paginator.page_range_list(page)
            danger_record_list = paginator3.get_page(page3)
            page_range3 = paginator3.page_range_list(page3)
        except InvalidPage:
            # page error - log
            # request.session['return_msg'] = _('System Error')
            return HttpResponseRedirect(reverse('backend_logout'))
        for record in approach_record_list:
            staff = record.app_user.usercompanytable_set.filter(department=department)
            if staff.exists():
                # record.staff_id = staff.first().pub_id
                record.app_user_link = True
            scan_staff = record.scan_user.usercompanytable_set.filter(department=department)
            if scan_staff.exists():
                # record.scan_staff_id = scan_staff.first().pub_id
                record.scan_user_link = True
        for record in danger_record_list:
            if record.approach_record:
                staff = record.app_user.usercompanytable_set.filter(department=department)
                if staff.exists():
                    record.app_user_link = True
                scan_staff = record.approach_record.scan_user.usercompanytable_set.filter(department=department)
                if scan_staff.exists():
                    record.scan_user_link = True
                # record.scan_user = record.approach_record.scan_user.auth_user.first_name
                # record.scan_user_id = record.approach_record.scan_user.pub_id
            else:
                staff = record.app_user.usercompanytable_set.filter(department=department)
                if staff.exists():
                    record.app_user_link = True
                # record.scan_user = record.app_user.auth_user.first_name
                # record.scan_user_id = record.app_user.pub_id
        return_data['approach_record_list'] = approach_record_list
        return_data['page_range'] = page_range
        return_data['danger_record_list'] = danger_record_list
        return_data['paginator3'] = page_range3
        return_data['end_time'] = etime.strftime('%Y-%m-%d')
        return_data['max_num'] = max_num
    return render(request, 'backend/company_index.html', context=return_data)


def user_verify(request):
    return_data = dict()
    if request.method == 'POST':
        account = request.POST.get('account')
        phone = request.POST.get('phone')
        otp = request.POST.get('otp')
        otp_id = request.POST.get('otp_id')
        if account and phone and otp and otp_id:
            try:
                phone_dict = AppUserServices.change_phone(phone)
            except PhoneFormatWrong:
                return_data['return_msg'] = PhoneFormatWrong.msg
            else:
                try:
                    OtpService(otp_id).verify(otp, verify_phone=phone_dict['fix_phone'])
                except Exception as e:
                    return_data['return_msg'] = _('Verify Otp Error, Please resend Otp')
                else:
                    app_user = AppUser.objects.select_related('auth_user').filter(
                        auth_user__username=account, auth_user__role__name=Role.MANAGEMENT)
                    if app_user.exists():
                        app_user = app_user.first()
                        if not app_user.phone:
                            app_user.phone = phone_dict['fix_phone']
                            app_user.save(update_fields=['phone', 'modified'])
                            request.session['fst_account'] = account
                            return HttpResponseRedirect(reverse('verify_set_pwd'))
                        else:
                            request.session['return_msg'] = AccountAlreadyBindPhone.msg
                            request.session['account'] = account
                            return HttpResponseRedirect(reverse('backend_login'))
                    else:
                        return_data['return_msg'] = _('Verify Otp Error, Please resend Otp')
    return render(request, 'backend/user_verify.html', context=return_data)


def verify_set_pwd(request):
    return_data = dict()
    account = request.session.get('fst_account')
    if not account:
        request.session['return_msg'] = _('Field missing')
        return HttpResponseRedirect(reverse('backend_login'))
    if request.method == 'POST':
        password = request.POST.get('password')
        chk_password = request.POST.get('chk_password')
        if password and chk_password:
            app_user = AppUser.objects.select_related('auth_user').filter(
                auth_user__username=account, auth_user__role__name=Role.MANAGEMENT)
            if app_user.exists():
                app_user = app_user.first()
                if password != chk_password:
                    return_data['return_msg'] = _('Password and check password not same')
                else:
                    request.session.pop('account')
                    user_detail = app_user.user_detail
                    user_detail.pop('new_user')
                    app_user.user_detail = user_detail
                    app_user.save(update_fields=['user_detail', 'modified'])
                    app_user.auth_user.set_password(password)
                    app_user.auth_user.save()
                    request.session['return_msg'] = _('Password has been reset, please log in again')
                    return HttpResponseRedirect(reverse('backend_login'))
            else:
                return_data['return_msg'] = _('User not exists')
    return_data['account'] = account
    return render(request, 'backend/reset_password_after_verify.html', context=return_data)


def backend_reset_pwd(request):
    return_data = dict()
    if request.method == 'POST':
        account = request.POST.get('account')
        password = request.POST.get('password')
        chk_password = request.POST.get('chk_password')
        otp = request.POST.get('otp')
        otp_id = request.POST.get('otp_id')
        if account and password and chk_password and otp and otp_id:
            app_user = AppUser.objects.select_related('auth_user').filter(
                auth_user__username=account, auth_user__role__name=Role.MANAGEMENT)
            if app_user.exists():
                app_user = app_user.first()
                try:
                    OtpService(otp_id).verify(otp, verify_phone=app_user.phone)
                except Exception as e:
                    return_data['return_msg'] = _('Verify Otp Error, Please resend Otp')
                else:
                    if password != chk_password:
                        return_data['return_msg'] = _('Password and check password not same')
                    else:
                        if request.session.get('fst_account'):
                            request.session.pop('fst_account')
                        app_user.auth_user.set_password(password)
                        app_user.auth_user.save()
                        request.session['return_msg'] = _('Password has been reset, please log in again')
                        return HttpResponseRedirect(reverse('backend_login'))
            else:
                return_data['return_msg'] = _('User not exists')
    if request.session.get('fst_account'):
        return_data['account'] = request.session.get('fst_account')
    return render(request, 'backend/reset_password.html', context=return_data)


def print_view(request, print_type, user_type):
    pdfmetrics.registerFont(TTFont('msjh', 'maipassport/static/backend/font/msjh.ttf'))
    if request.method == 'POST':
        middle_w = 297
        middle_h = 410

        if print_type == 'PLACE':
            print_dict = dict()
            place_id_list = request.session.get('check_place')
            if place_id_list:
                buffer = io.BytesIO()
                p = canvas.Canvas(buffer)
                for place_id in place_id_list:
                    p.setFont('msjh', 20)
                    place = Place.objects.select_related('company').filter(pub_id=place_id)
                    if place.exists():
                        place = place.first()
                        company_name = place.company.name
                        if company_name not in print_dict:
                            default_print = CompanyDefaultPrint.objects.filter(company=place.company)
                            if default_print.exists():
                                print_dict[company_name] = default_print.first().place_code
                                print_str = print_dict[company_name]
                            else:
                                if user_type == 'ADMIN':
                                    return HttpResponseRedirect(reverse('place_management'))
                                elif user_type == 'MANAGE':
                                    return HttpResponseRedirect(
                                        reverse('company_place',
                                                kwargs={'pub_id': request.session.get('company_manage_id_sel_now')}))
                                else:
                                    return HttpResponseRedirect(reverse('backend_login'))
                        else:
                            print_str = print_dict[company_name]
                        if 'fst_line' in print_str and print_str['fst_line'] != "":
                            p.drawCentredString(middle_w, middle_h + 150 + 175, print_str['fst_line'])
                        if 'sec_line' in print_str and print_str['sec_line'] != "":
                            p.drawCentredString(middle_w, middle_h + 150 + 140, print_str['sec_line'].encode('utf-8'))
                        if 'thd_line' in print_str and print_str['thd_line'] != "":
                            p.drawCentredString(middle_w, middle_h + 150 + 105, print_str['thd_line'].encode('utf-8'))
                        if 'forth_line' in print_str and print_str['forth_line'] != "":
                            p.drawCentredString(middle_w, middle_h + 150 + 70, print_str['forth_line'].encode('utf-8'))
                        p.drawCentredString(middle_w, middle_h - 30 + 150 + 50, place.name.encode('utf-8'))
                        p.drawCentredString(middle_w, middle_h - 30 + 150 + 10, place.serial_num.encode('utf-8'))
                        qr = qrcode.QRCode(
                            version=1,
                            error_correction=qrcode.constants.ERROR_CORRECT_H,
                            box_size=4,
                            border=3
                        )
                        qr.add_data('PLACE__' + place.pub_id)
                        qr.make()
                        img = qr.make_image(fill_color='black')
                        image = ImageReader(img._img)
                        p.drawImage(image, middle_w - 150, middle_h - 30 - 150, 300, 300)
                        if 'last_line' in print_str and print_str['last_line'] != "":
                            p.drawCentredString(middle_w, middle_h - 30 - 150 - 50, print_str['last_line'])

                        p.showPage()
                p.save()
                buffer.seek(0)

                return FileResponse(buffer, as_attachment=True, filename=str(_('PLACE_QR_CODE')) + '.pdf')
        # elif print_type == 'ADDORG':
    if user_type == 'ADMIN':
        return HttpResponseRedirect(reverse('place_management'))
    elif user_type == 'MANAGE':
        return HttpResponseRedirect(reverse('company_place',
                                            kwargs={'pub_id': request.session.get('company_manage_id_sel_now')}))
    else:
        return HttpResponseRedirect(reverse('backend_login'))

