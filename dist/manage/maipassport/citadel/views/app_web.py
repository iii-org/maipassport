import json
from datetime import datetime, timedelta

from decimal import Decimal
from django.shortcuts import render, reverse
from django.conf import settings
from django.http import HttpResponseRedirect
from django.utils.decorators import method_decorator
from django.utils.translation import ugettext_lazy as _
from django.views.decorators.csrf import csrf_exempt
from django.db.models import Q

from rest_framework.decorators import api_view
from rest_framework.response import Response

from maipassport.records.models import (QuestionnaireField, Questionnaire, ApproachRecord, AttendanceRecord,
                                        PlaceEntryRecord, HealthRecord, VisitorRegistration)
from maipassport.records.services import GpsService
from maipassport.users.models import AppUser, HealthCode, AttendanceStatus
from maipassport.users.services import AppUserServices
from maipassport.companies.models import UserCompanyTable, Place, Company, AddRequest, AddCompanyTag
from maipassport.citadel.views.base import login_required2
from maipassport.core.utils import get_utc_format_today, utc_time_to_local_time
from maipassport.core.exceptions import PhoneFormatWrong
from maipassport.transfers.models import PreUserQRTrans


@login_required2
def get_health_question_html(request, user_id, token):
    # 區分英文版與中文版
    if request.COOKIES.get('language') == 'en-us':
        health_field = QuestionnaireField.objects.filter(type=QuestionnaireField.HEALTH, name='HEALTH_QUESTIONNAIRE_EN')
    else:
        health_field = QuestionnaireField.objects.filter(type=QuestionnaireField.HEALTH, name='健康聲明調查表')
    if not health_field.exists():
        # TODO: 找不到此問券
        request.session['message'] = _('The health declaration form is not exists')
        return HttpResponseRedirect(
            reverse('app_index', kwargs={'user_id': request.user.appuser.pub_id,
                                         'token': request.user.appuser.api_token}))
    else:
        health_field = health_field.first()

    # 檢查有沒有填過
    # if not Questionnaire.objects.filter(app_user=request.app_user, field_name=health_field).exists()

    return_data = dict()
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
        return HttpResponseRedirect(
            reverse('app_index', kwargs={'user_id': request.user.appuser.pub_id,
                                         'token': request.user.appuser.api_token}))
    return_data['questionnaire_name'] = health_field.name
    return_data['html_context'] = health_field.field_name
    return render(request, 'app_web_n/question.html', context=return_data)


# TODO: 不使用
@login_required2
def get_health_code(request, user_id, token):
    return_data = dict()
    return_data['qr_data'] = f'USER__{user_id}'
    health_code = request.app_user.healthcode.code
    return_data['health_detail'] = HealthCode.code_choice_detail()[request.app_user.healthcode.code]
    stime, etime = get_utc_format_today()
    if not Questionnaire.objects.filter(
            field_name__type=QuestionnaireField.HEALTH,
            app_user=request.app_user, modified__range=(stime, etime)).exists():
        return_data['color_type'] = 'black'
    elif health_code == HealthCode.WAIT_MEASURE:
        return_data['color_type'] = '1'
    elif health_code == HealthCode.NORMAL:
        return_data['color_type'] = '0'
    elif health_code == HealthCode.DANGER:
        return_data['color_type'] = '2'
        return_data['danger_reason'] = _('Alerted by measuring staff')
    elif health_code == HealthCode.QUEST_DANGER:
        return_data['color_type'] = '3'
        return_data['danger_reason'] = _('High risk, may have recently gone abroad or have related symptoms')
    else:
        return_data['color_type'] = 'none'
    return_data['last_time_update'] = datetime.strftime(
        utc_time_to_local_time(request.app_user.healthcode.modified), "%Y-%m-%d %H:%M:%S")
    # pre_qr_trans = PreUserQRTrans.objects.filter(app_user=request.app_user, return_code=PreUserQRTrans.NO_SCAN)
    # if pre_qr_trans.exists():
    #     pre_qr_trans = pre_qr_trans.first()
    # else:
    #     pre_qr_trans = PreUserQRTrans.objects.create(app_user=request.app_user)
    # return_data['pre_qr_trans_pub_id'] = pre_qr_trans.pub_id
    return render(request, 'app_web/health_code.html', context=return_data)


# 公告
@login_required2
def get_announcement(request, user_id, token):
    return_data = dict()
    return render(request, 'app_web/announcement.html', context=return_data)


# @api_view(['POST'])
@method_decorator(csrf_exempt)
@login_required2
def scan_post(request, user_id, token):
    if 'Device' in request.headers:
        request.session['DEVICE'] = request.headers['Device']
    return_data = dict()
    # qr_content = request.POST.get('qr_content')

    qr_id = request.POST.get('qr_content')
    qr_type = request.POST.get('qr_type')

    # latlon_longitude = request.POST.get('latlon_longitude')  # 經度
    # latlon_latitude = request.POST.get('latlon_latitude')  # 緯度

    # web_latitude = request.POST.get('web_latitude')  # 網頁經度
    # web_longitude = request.POST.get('web_longitude')  # 網頁緯度

    # location = request.POST.get('location')
    # if latlon_longitude and latlon_latitude:
    #     location = {
    #         'latlon_longitude': latlon_longitude,
    #         'latlon_latitude': latlon_latitude
    #     }
    # else:
    #     if web_latitude and web_longitude:
    #         location = {
    #             'latlon_longitude': web_latitude,
    #             'latlon_latitude': web_longitude
    #         }
    #     else:
    #         location = None

    # TODO: 之後強制加入地點
    # if location:
    #     return_data['location'] = str(location)

    if qr_type == 'USER':
        # TODO: 使用者QR Code
        return_data['qr_type'] = 'USER'
        return_data['scan_health'] = 0
        return_data['scan_visitor'] = 0
        return_data['scan_approach'] = 0
        if qr_id == request.app_user.pub_id:
            # TODO: 掃描對象為自己
            request.session['message'] = _('Scanning objects error')
            return HttpResponseRedirect(
                reverse('app_index', kwargs={'user_id': request.user.appuser.pub_id,
                                             'token': request.user.appuser.api_token}))
        scaned_user = AppUser.objects.filter(pub_id=qr_id)
        if not scaned_user.exists():
            request.session['message'] = _('Scanning objects error')
            return HttpResponseRedirect(
                reverse('app_index', kwargs={'user_id': request.user.appuser.pub_id,
                                             'token': request.user.appuser.api_token}))
        else:
            scaned_user = scaned_user.first()

        # pre_scan = PreUserQRTrans.objects.filter(app_user__pub_id=qr_id, return_code=PreUserQRTrans.NO_SCAN)
        # if not pre_scan.exists():
        #     # TODO: 跳到找不到此user
        #     request.session['message'] = _('Scanning objects error')
        #     return HttpResponseRedirect(
        #         reverse('app_index', kwargs={'user_id': request.user.appuser.pub_id,
        #                                      'token': request.user.appuser.api_token}))
        # else:
        #     pre_scan = pre_scan.first()
        #     return_data['scan_approach'] = 1
        #     return_data['qr_id'] = qr_id
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
                return HttpResponseRedirect(
                    reverse('app_index', kwargs={'user_id': request.user.appuser.pub_id,
                                                 'token': request.user.appuser.api_token}))
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
                return HttpResponseRedirect(
                    reverse('app_index', kwargs={'user_id': request.user.appuser.pub_id,
                                                 'token': request.user.appuser.api_token}))
        if HealthCode.objects.filter(app_user=scaned_user, code=HealthCode.QUEST_DANGER).exists():
            # TODO: 被掃描者由填表判定為高風險
            request.session['message'] = _('Scanning objects is judged as high risk by the system')
            request.session['send_msg'] = _('You are currently a high-risk object, temporarily banned')
            request.session['send_user'] = qr_id
            return HttpResponseRedirect(
                reverse('app_index', kwargs={'user_id': request.user.appuser.pub_id,
                                             'token': request.user.appuser.api_token}))
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
            return HttpResponseRedirect(
                reverse('app_index', kwargs={'user_id': request.user.appuser.pub_id,
                                             'token': request.user.appuser.api_token}))
    elif qr_type == 'ADDORG':
        # TODO: 加入組織QR Code
        company = Company.objects.select_related('addcompanytag').filter(addcompanytag__pub_id=qr_id)
        if not company.exists():
            request.session['message'] = _('Scanning objects error')
            return HttpResponseRedirect(
                reverse('app_index', kwargs={'user_id': request.user.appuser.pub_id,
                                             'token': request.user.appuser.api_token}))
        else:
            company = company.first()
            if request.user.appuser.usercompanytable_set.filter(company=company, employed=True).exists():
                request.session['message'] = _('Already in this company')
                return HttpResponseRedirect(
                    reverse('app_index', kwargs={'user_id': request.user.appuser.pub_id,
                                                 'token': request.user.appuser.api_token}))
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
            return render(request, 'app_web_n/addorg_sel.html', context=return_data)
    else:
        request.session['message'] = _('Scanning objects error')
        return HttpResponseRedirect(
            reverse('app_index', kwargs={'user_id': request.user.appuser.pub_id,
                                         'token': request.user.appuser.api_token}))
    return render(request, 'app_web_n/scan_func.html', context=return_data)


@method_decorator(csrf_exempt)
@login_required2
def sel_scan(request, user_id, token):
    return_data = dict()

    qr_id = request.POST.get('qr_id')
    func_sel = request.POST.get('func_sel')
    # location = request.POST.get('location')

    longitude = request.POST.get('longitude')  # 網頁經度
    latitude = request.POST.get('latitude')   # 網頁緯度

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
                return render(request, 'app_web_n/health_code_sel.html', context=return_data)
            else:
                # TODO: 無此使用者
                request.session['message'] = _('Scanning objects error')
                return HttpResponseRedirect(
                    reverse('app_index', kwargs={'user_id': request.user.appuser.pub_id,
                                                 'token': request.user.appuser.api_token}))
        elif func_sel == 'scan_approach':
            scanned_app_user = AppUser.objects.filter(pub_id=qr_id)
            if scanned_app_user.exists():
                return_data['scanned_app_user'] = scanned_app_user.first()
                return render(request, 'app_web_n/approach_sel.html', context=return_data)
            else:
                # TODO: 無此使用者
                request.session['message'] = _('Scanning objects error')
                return HttpResponseRedirect(
                    reverse('app_index', kwargs={'user_id': request.user.appuser.pub_id,
                                                 'token': request.user.appuser.api_token}))
        elif func_sel == 'scan_visitor':
            scanned_app_user = AppUser.objects.filter(pub_id=qr_id)
            if not scanned_app_user.exists():
                # TODO: 無此使用者
                request.session['message'] = _('Scanning objects error')
                return HttpResponseRedirect(
                    reverse('app_index', kwargs={'user_id': request.user.appuser.pub_id,
                                                 'token': request.user.appuser.api_token}))
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
                    return HttpResponseRedirect(
                        reverse('app_index', kwargs={'user_id': request.user.appuser.pub_id,
                                                     'token': request.user.appuser.api_token}))
                return_data['scan_company_list'] = scan_company_list
                return_data['scanned_app_user'] = scanned_app_user
                return render(request, 'app_web_n/visitor_sel.html', context=return_data)
            else:
                # TODO: 掃描者無公司資料
                request.session['message'] = _('You currently have no company / school')
                return HttpResponseRedirect(
                    reverse('app_index', kwargs={'user_id': request.user.appuser.pub_id,
                                                 'token': request.user.appuser.api_token}))
        elif func_sel == 'scan_clock_in':
            # TODO:暫時不用
            status_dict = AttendanceStatus.return_status_dict()
            place = Place.objects.select_related('company').filter(pub_id=qr_id)
            if not place.exists():
                # TODO: 無此地點
                request.session['message'] = _('Scanning objects error')
                return HttpResponseRedirect(
                    reverse('app_index', kwargs={'user_id': request.user.appuser.pub_id,
                                                 'token': request.user.appuser.api_token}))
            else:
                place = place.first()
                return_data['company'] = place.company
                return_data['place'] = place
            app_user_attendance = request.app_user.attendancestatus_set.filter(company=place.company)
            if not app_user_attendance.exists():
                # TODO: 無此公司打卡資料
                request.session['message'] = _('You may no longer be in this company')
                return HttpResponseRedirect(
                    reverse('app_index', kwargs={'user_id': request.user.appuser.pub_id,
                                                 'token': request.user.appuser.api_token}))
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
            return render(request, 'app_web_n/work_sel.html', context=return_data)
        elif func_sel == 'scan_user_clock_in':
            status_dict = AttendanceStatus.return_status_dict()
            place = Place.objects.select_related('company').filter(pub_id=qr_id)
            if not place.exists():
                # TODO: 無此地點
                request.session['message'] = _('Scanning objects error')
                return HttpResponseRedirect(
                    reverse('app_index', kwargs={'user_id': request.user.appuser.pub_id,
                                                 'token': request.user.appuser.api_token}))
            else:
                place = place.first()
                return_data['company'] = place.company
                return_data['place'] = place
            app_user_attendance = request.app_user.attendancestatus_set.filter(company=place.company)
            if not app_user_attendance.exists():
                # TODO: 無此公司打卡資料
                request.session['message'] = _('You may no longer be in this company')
                return HttpResponseRedirect(
                    reverse('app_index', kwargs={'user_id': request.user.appuser.pub_id,
                                                 'token': request.user.appuser.api_token}))
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

            return render(request, 'app_web_n/scan_work_sel.html', context=return_data)
        elif func_sel == 'scan_place':
            place = Place.objects.select_related('company').filter(pub_id=qr_id)
            if not place.exists():
                # TODO: 無此地點
                request.session['message'] = _('Scanning objects error')
                return HttpResponseRedirect(
                    reverse('app_index', kwargs={'user_id': request.user.appuser.pub_id,
                                                 'token': request.user.appuser.api_token}))
            else:
                place = place.first()
                return_data['place'] = place

            return render(request, 'app_web_n/place_sel.html', context=return_data)
    else:
        request.session['message'] = _('Field missing')
        return HttpResponseRedirect(
            reverse('app_index', kwargs={'user_id': request.user.appuser.pub_id,
                                         'token': request.user.appuser.api_token}))


# TODO: 暫時關閉
@login_required2
def user_work_status(request, user_id, token):
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
            return HttpResponseRedirect(
                reverse('app_index', kwargs={'user_id': request.user.appuser.pub_id,
                                             'token': request.user.appuser.api_token}))
        else:
            place = place.first()
        app_user_attendance = request.app_user.attendancestatus_set.filter(company=place.company)
        if not app_user_attendance.exists():
            # TODO: 無此公司打卡資料
            request.session['message'] = _('You may no longer be in this company')
            return HttpResponseRedirect(
                reverse('app_index', kwargs={'user_id': request.user.appuser.pub_id,
                                             'token': request.user.appuser.api_token}))
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
        if location:
            location_dict = eval(location)
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
    return HttpResponseRedirect(
            reverse('app_index', kwargs={'user_id': request.user.appuser.pub_id,
                                         'token': request.user.appuser.api_token}))


@login_required2
def scan_user_work_status(request, user_id, token):
    company_id = request.POST.get('company_id')
    place_id = request.POST.get('place_id')
    location = request.POST.get('location')

    if company_id and place_id:
        place = Place.objects.select_related('company').filter(pub_id=place_id, company__pub_id=company_id)
        if not place.exists():
            # TODO: 無此地點
            request.session['message'] = _('Scanning objects error')
            return HttpResponseRedirect(
                reverse('app_index', kwargs={'user_id': request.user.appuser.pub_id,
                                             'token': request.user.appuser.api_token}))
        else:
            place = place.first()
        app_user_attendance = request.app_user.attendancestatus_set.filter(company=place.company)
        if not app_user_attendance.exists():
            # TODO: 無此公司打卡資料
            request.session['message'] = _('You may no longer be in this company')
            return HttpResponseRedirect(
                reverse('app_index', kwargs={'user_id': request.user.appuser.pub_id,
                                             'token': request.user.appuser.api_token}))
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
            return HttpResponseRedirect(
                reverse('app_index', kwargs={'user_id': request.user.appuser.pub_id,
                                             'token': request.user.appuser.api_token}))
        app_user_attendance.status = status
        app_user_attendance.save(update_fields=['status', 'remote_work', 'modified'])
        attendance_record = AttendanceRecord.objects.create(app_user=request.app_user, status=record_status,
                                                            attendance_status=status)
        attendance_record.approach_place = place
        place_entry = PlaceEntryRecord.objects.create(app_user=request.app_user, place_entry=place)
        # TODO: 之後強制加入地點
        if location:
            location_dict = eval(location)
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
    return HttpResponseRedirect(
            reverse('app_index', kwargs={'user_id': request.user.appuser.pub_id,
                                         'token': request.user.appuser.api_token}))


# 健康碼更新
@login_required2
def user_health_status(request, user_id, token):
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
            return HttpResponseRedirect(
                reverse('app_index', kwargs={'user_id': request.user.appuser.pub_id,
                                             'token': request.user.appuser.api_token}))
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
        if location:
            location_dict = eval(location)
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

    return HttpResponseRedirect(
            reverse('app_index', kwargs={'user_id': request.user.appuser.pub_id,
                                         'token': request.user.appuser.api_token}))


@login_required2
def user_approach_status(request, user_id, token):
    scanned_user_id = request.POST.get('scanned_user_id')
    location = request.POST.get('location')

    if scanned_user_id:
        scanned_app_user = AppUser.objects.filter(pub_id=scanned_user_id)
        if scanned_app_user.exists():
            scanned_app_user = scanned_app_user.first()
            approach_record = ApproachRecord.objects.create(app_user=scanned_app_user, scan_user=request.app_user,
                                                            type=ApproachRecord.APPROACH_CHECK)
            if location:
                location_dict = eval(location)
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
    return HttpResponseRedirect(
        reverse('app_index', kwargs={'user_id': request.user.appuser.pub_id,
                                     'token': request.user.appuser.api_token}))


@login_required2
def user_visitor_status(request, user_id, token):
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
                return HttpResponseRedirect(
                    reverse('app_index', kwargs={'user_id': request.user.appuser.pub_id,
                                                 'token': request.user.appuser.api_token}))
            else:
                company = company.first()
            scanned_app_user = AppUser.objects.filter(pub_id=scanned_user_id)
            if not scanned_app_user.exists():
                # TODO: 無此使用者
                request.session['message'] = _('Scanning objects error')
                return HttpResponseRedirect(
                    reverse('app_index', kwargs={'user_id': request.user.appuser.pub_id,
                                                 'token': request.user.appuser.api_token}))
            else:
                scanned_app_user = scanned_app_user.first()
            # 接觸紀錄
            approach_record = ApproachRecord.objects.create(app_user=scanned_app_user, scan_user=request.app_user,
                                                            type=ApproachRecord.VISITOR_CHECK)
            VisitorRegistration.objects.create(company=company, app_user=scanned_app_user,
                                               approach_record=approach_record, visitor=True)
            # place_entry = PlaceEntryRecord.objects.create(app_user=request.app_user, place_entry=place)
            if location:
                location_dict = eval(location)
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
        return HttpResponseRedirect(
            reverse('app_index', kwargs={'user_id': request.user.appuser.pub_id,
                                         'token': request.user.appuser.api_token}))
    else:
        # TODO: 欄位有缺
        request.session['message'] = _('Field missing')
    return HttpResponseRedirect(
        reverse('app_index', kwargs={'user_id': request.user.appuser.pub_id,
                                     'token': request.user.appuser.api_token}))


@login_required2
def user_place_entry(request, user_id, token):
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
            return HttpResponseRedirect(
                reverse('app_index', kwargs={'user_id': request.user.appuser.pub_id,
                                             'token': request.user.appuser.api_token}))
        else:
            place = place.first()
        if place.update_health_code:
            if request.app_user.healthcode.code in [HealthCode.DANGER, HealthCode.QUEST_DANGER]:
                request.session['message'] = _('You are currently a high-risk object, temporarily banned')
                return HttpResponseRedirect(
                    reverse('app_index', kwargs={'user_id': request.user.appuser.pub_id,
                                                 'token': request.user.appuser.api_token}))
            elif request.app_user.usercompanytable_set.filter(company__name='資訊工業策進會').exists():
                # TODO: 屬於資策會的人此生有填過By pass
                if not Questionnaire.objects.filter(field_name__type=QuestionnaireField.HEALTH,
                                                    app_user=request.app_user).exists():
                    request.session['message'] = _('Please filled out the declaration')
                    return HttpResponseRedirect(
                        reverse('app_index', kwargs={'user_id': request.user.appuser.pub_id,
                                                     'token': request.user.appuser.api_token}))
            else:
                stime, etime = get_utc_format_today()
                if not Questionnaire.objects.filter(
                        field_name__type=QuestionnaireField.HEALTH,
                        app_user=request.app_user, modified__range=(stime, etime)).exists():
                    request.session['message'] = _('Please filled out the declaration')
                    return HttpResponseRedirect(
                        reverse('app_index', kwargs={'user_id': request.user.appuser.pub_id,
                                                     'token': request.user.appuser.api_token}))
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
        if location:
            location_dict = eval(location)
            place_entry.location = location_dict
            try:
                location_address = GpsService.get_gps_location(location_dict['latlon_longitude'],
                                                               location_dict['latlon_latitude'])
            except Exception as e:
                pass
            else:
                if location_address:
                    place_entry.location['location_address'] = location_address
        if place.update_health_code:
            request.app_user.healthcode.code = HealthCode.NORMAL
            request.app_user.healthcode.save(update_fields=['code', 'modified'])
        # entry_note = dict()
        # if act_name:
        #     entry_note['act_name'] = act_name
        # if act_organizer:
        #     entry_note['act_organizer'] = act_organizer
        # if act_org_contact:
        #     entry_note['act_org_contact'] = act_org_contact
        # place_entry.note = entry_note
        place_entry.save(update_fields=['location', 'modified', 'note'])
    return HttpResponseRedirect(
        reverse('app_index', kwargs={'user_id': request.user.appuser.pub_id,
                                     'token': request.user.appuser.api_token}))


@method_decorator(csrf_exempt)
@login_required2
def user_add_company(request, user_id, token):
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
            return HttpResponseRedirect(
                reverse('app_index', kwargs={'user_id': request.user.appuser.pub_id,
                                             'token': request.user.appuser.api_token}))
        else:
            add_tag = AddCompanyTag.objects.filter(pub_id=tag_id, company__pub_id=company_id)
            if add_tag.exists():
                add_tag = add_tag.first()
                AddRequest.objects.create(add_tag=add_tag, add_user=request.app_user)
                request.session['message'] = _('Add request sent, pending review')
            else:
                request.session['message'] = _('Scanning objects error')
            return HttpResponseRedirect(
                reverse('app_index', kwargs={'user_id': request.user.appuser.pub_id,
                                             'token': request.user.appuser.api_token}))
    else:
        # TODO: 欄位有缺
        request.session['message'] = _('Field missing')
    return HttpResponseRedirect(
        reverse('app_index', kwargs={'user_id': request.user.appuser.pub_id,
                                     'token': request.user.appuser.api_token}))


@login_required2
def get_history(request, user_id, token):
    return_data = dict()
    health_field_all = QuestionnaireField.objects.filter(type=QuestionnaireField.HEALTH)
    if not health_field_all.exists():
        # TODO: 找不到此問券
        request.session['message'] = _('The health declaration form is not exists')
        return HttpResponseRedirect(
            reverse('app_index', kwargs={'user_id': request.user.appuser.pub_id,
                                         'token': request.user.appuser.api_token}))
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
    return render(request, 'app_web_n/history.html', context=return_data)


@login_required2
def user_profile(request, user_id, token):
    return_data = dict()
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
        user_company for user_company in request.app_user.usercompanytable_set.filter(employed=True)
    ]
    return render(request, 'app_web_n/user_profile.html', context=return_data)


@login_required2
def upload_user_img(request, user_id, token):
    user_img_file = request.FILES.copy()
    if 'upload_img' in user_img_file:
        img_file_obj = user_img_file['upload_img']
        file_path = f'media/{user_id}/user_image/{user_id}.{img_file_obj.name.split(".")[1]}'
        url = AppUserServices.upload_to_aws(file_path, user_img_file['upload_img'])
        request.app_user.user_picture_local = url
        request.app_user.save(update_fields=['modified', 'user_picture_local'])
    return HttpResponseRedirect(
        reverse('user_profile', kwargs={'user_id': request.user.appuser.pub_id,
                                        'token': request.user.appuser.api_token}))


@login_required2
def chick_in_record(request, user_id, token):
    return_data = dict()
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
            return HttpResponseRedirect(
                reverse('app_index', kwargs={'user_id': request.user.appuser.pub_id,
                                             'token': request.user.appuser.api_token}))
        else:
            # TODO: 無定位到
            return_data['message'] = _('Please wait locate')
    return render(request, 'app_web_n/location_check_in.html', context=return_data)


def privacy_file(request):
    return render(request, 'app_web_n/privacy_file.html', context={})


@login_required2
def scan_test(request, user_id, token):
    user_list = AppUser.objects.exclude(pub_id=user_id)
    place_list = Place.objects.all()
    return render(request, 'app_web/scan_test.html',
                  context={
                      'user_list': user_list,
                      'place_list': place_list,
                      'company_list': [
                          (company.name, company.addcompanytag.pub_id) for company in Company.objects.all()]
                  })


def enc_message(request):
    return render(request, 'app_web/encdata.html',
                  context={
                  })
