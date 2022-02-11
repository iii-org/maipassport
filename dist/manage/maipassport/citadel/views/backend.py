from datetime import datetime
from datetime import timedelta
import random, string

import xlwt
from django.shortcuts import render, reverse, HttpResponse
from django.core.paginator import InvalidPage
from django.http import HttpResponseRedirect
from django.utils import timezone
from django.db.models import Q
from django.utils.translation import gettext_lazy as _

from maipassport.citadel.services import logger_writer
from maipassport.core.utils import CachedPaginator, utc_time_to_local_time, local_time_to_utc_time
from maipassport.core.exceptions import CompanyAlreadyExists, DepartmentAlreadyExists
from maipassport.companies.models import (Company, UserCompanyTable, Place, CompanyDefaultPrint, AddRequest,
                                          Department, Title, UserCompanyHistory, NewCompanyApply, ActionLog)
from maipassport.companies.services import CompanyServices
from maipassport.citadel.views import login_required4
from maipassport.citadel.models import Role
from maipassport.records.models import ApproachRecord, PlaceEntryRecord
from maipassport.users.models import AppUser, HealthCode, AttendanceStatus


@login_required4
def user_management(request):
    return_data = dict()
    per_page_num = request.GET.get('per_page_num')
    if not per_page_num:
        per_page_num = 10
    page = request.GET.get('page')
    app_user_list = AppUser.objects.select_related('auth_user').all().order_by('-created')

    app_user_name_list = list()
    app_user_account_list = list()
    for app_user in app_user_list:
        if app_user.auth_user.first_name not in app_user_name_list:
            app_user_name_list.append(app_user.auth_user.first_name)
        app_user_account_list.append(app_user.auth_user.username)
    return_data['app_user_name_list'] = app_user_name_list
    return_data['app_user_account_list'] = app_user_account_list

    user_first_name = request.GET.get('user_first_name')
    user_account = request.GET.get('user_account')
    company_name = request.GET.get('company_name')
    department_name = request.GET.get('department_name')
    user_role = request.GET.get('user_role')
    created_at_min = request.GET.get('created_at_min')
    created_at_max = request.GET.get('created_at_max')

    if user_first_name:
        app_user_list = app_user_list.filter(auth_user__first_name=user_first_name)

    if user_account:
        app_user_list = app_user_list.filter(auth_user__username=user_account)

    if company_name:
        app_user_list = app_user_list.filter(usercompanytable__company__name=company_name)

    company_list = Company.objects.all()
    return_data['company_list'] = [company.name for company in company_list]

    if department_name:
        app_user_list = app_user_list.filter(usercompanytable__department__name=department_name)

    department_dict = dict()
    for company in company_list:
        department_dict[company.name] = [department.name for department in company.department_set.all()]
    return_data['department_dict'] = department_dict

    if user_role:
        if user_role == 'Scanner':
            app_user_list = app_user_list.filter(usercompanytable__scan_enabled=True)
        elif user_role == 'Department Management':
            app_user_list = app_user_list.filter(usercompanytable__department_manage_enabled=True)
        elif user_role == 'Company Management':
            app_user_list = app_user_list.filter(usercompanytable__manage_enabled=True)
        elif user_role == Role.APPUSER:
            app_user_list = app_user_list.filter(
                auth_user__role__name=user_role).exclude(auth_user__role__name=Role.MANAGEMENT)
        else:
            app_user_list = app_user_list.none()

    if created_at_min:
        try:
            create_at_min = datetime.strptime(created_at_min, '%Y-%m-%d %H:%M')
        except (TypeError, ValueError) as e:
            pass
        else:
            app_user_list = app_user_list.filter(created__gte=timezone.make_aware(create_at_min))

    if created_at_max:
        try:
            # Plus one day to cover whole day. Ex: 2018-10-10T00:00:00 -> 2018-10-11T00:00:00
            # and then we use less than expression to query
            create_at_max = datetime.strptime(created_at_max, '%Y-%m-%d %H:%M') + timedelta(days=1)
        except (TypeError, ValueError) as e:
            pass
        else:
            app_user_list = app_user_list.filter(created__lt=timezone.make_aware(create_at_max))

    return_data['user_length'] = len(app_user_list)

    paginator = CachedPaginator(app_user_list, per_page_num)
    try:
        app_user_list = paginator.get_page(page)
        page_range = paginator.page_range_list(page)
    except InvalidPage:
        # page error - log
        # request.session['return_msg'] = _('System Error')
        logger_writer('SYSTEM', 'error', 'USER MANAGEMENT', f'System error: redirect to backend index')
        return HttpResponseRedirect(reverse('backend_index'))

    for app_user in app_user_list:
        user_company = app_user.usercompanytable_set.all()
        default_user_company = user_company.filter(default_show=True)
        if default_user_company.exists():
            default_user_company = default_user_company.first()
            app_user.default_company = default_user_company.company
            app_user.default_department = default_user_company.department
        if user_company.filter(employed=True, scan_enabled=True).exists():
            app_user.scan_enabled = True
        else:
            app_user.scan_enabled = False
        if user_company.filter(employed=True, department_manage_enabled=True).exists():
            app_user.dep_manage = True
        else:
            app_user.dep_manage = False
        # if app_user.auth_user.role_set.filter(name=Role.MANAGEMENT).exists():
        if user_company.filter(employed=True, manage_enabled=True).exists():
            app_user.admin_flag = True
        else:
            app_user.admin_flag = False

    role_dict = Role.get_role_display_to_value_dict()
    return_data['user_role_list'] = [(Role.APPUSER, role_dict[Role.APPUSER]),
                                     ('Company Management', _('Company Management')),
                                     ('Department Management', _('Department Management')),
                                     ('Scanner', _('Scanner'))]
    return_data['page_range'] = page_range
    return_data['app_user_list'] = app_user_list
    return render(request, 'backend/user_management.html', context=return_data)


@login_required4
def get_user_detail(request, pub_id):
    return_data = dict()
    app_user = AppUser.objects.filter(pub_id=pub_id)
    if not app_user.exists():
        return HttpResponseRedirect(reverse('user_management'))
    else:
        app_user = app_user.first()

        # if request.method == 'POST':
        #     admin_flag_checkbox = request.POST.get('admin_flag_checkbox')
        #     if admin_flag_checkbox:
        #         if not app_user.auth_user.role_set.filter(name='Management').exists():
        #             app_user.auth_user.role_set.add(Role.objects.get(name='Management'))
        #     else:
        #         if app_user.auth_user.role_set.filter(name='Management').exists():
        #             app_user.auth_user.role_set.remove(Role.objects.get(name='Management'))

        return_data['app_user'] = app_user
        user_company_list = app_user.usercompanytable_set.all().order_by('created')
        if user_company_list.exists():
            return_data['user_company_list'] = user_company_list
        if app_user.auth_user.role_set.filter(name='Management').exists():
            return_data['admin_flag'] = True
        return_data['health_code'] = HealthCode.code_choice_detail()[app_user.healthcode.code]
        approach_record = (
                app_user.scan_user.select_related('healthrecord', 'visitorregistration').all() |
                app_user.app_user.select_related('healthrecord', 'visitorregistration').all()).order_by('-created')
        place_record = app_user.placeentryrecord_set.select_related('place_entry').all().order_by('-created')
        attendance_record = app_user.attendancerecord_set.select_related(
            'approach_place').all().order_by('-created')
        paginator = CachedPaginator(approach_record, 15)
        paginator2 = CachedPaginator(place_record, 15)
        paginator3 = CachedPaginator(attendance_record, 15)
        page = request.GET.get('page')
        page2 = request.GET.get('page2')
        page3 = request.GET.get('page3')
        if page or page or page3:
            return_data['nav_no_reset'] = 1
        try:
            approach_record = paginator.get_page(page)
            page_range = paginator.page_range_list(page)
            place_record = paginator2.get_page(page2)
            page_range2 = paginator2.page_range_list(page2)
            attendance_record = paginator3.get_page(page3)
            page_range3 = paginator3.page_range_list(page3)
        except InvalidPage:
            # page error - log
            # request.session['return_msg'] = _('System Error')
            logger_writer('SYSTEM', 'error', 'GET USER DETAIL', f'System error, redirect to backend index')
            return HttpResponseRedirect(reverse('backend_index'))
        for record in place_record:
            if 'location_address' in record.location:
                record.place_location = record.location['location_address']
            elif record.place_entry:
                record.place_location = record.place_entry.name
                record.place_tract = True
            elif 'latlon_latitude' in record.location and 'latlon_longitude' in record.location:
                record.place_location = 'latitude: {}, longitude: {}'.format(
                    record.location['latlon_latitude'], record.location['latlon_longitude'])
            else:
                record.place_location = _('Get Location Failed')
        return_data['approach_record'] = approach_record
        return_data['place_record'] = place_record
        return_data['attendance_record'] = attendance_record
        return_data['page_range'] = page_range
        return_data['page_range2'] = page_range2
        return_data['page_range3'] = page_range3
        return render(request, 'backend/user_detail.html', context=return_data)


@login_required4
def user_create_open(request, pub_id, status):
    user = AppUser.objects.filter(pub_id=pub_id)
    if user.exists():
        user = user.first()
        if status == 'ON':
            user.auth_user.is_active = True
        else:
            user.auth_user.is_active = False
        user.auth_user.save()
    return HttpResponseRedirect(reverse('user_detail', kwargs={'pub_id': pub_id}))


@login_required4
def edit_user_manage_enable(request, user_id, company_id, staff_id, edit_flag, backpage, manage_type):
    page_add = ''
    if backpage == 'MANAGEMENT':
        now_page = request.GET.get('page')
        if not now_page:
            now_page = ''
        now_page_range = request.GET.get('per_page_num')
        if not now_page_range:
            now_page_range = ''
        user_first_name = request.GET.get('user_first_name')
        if not user_first_name:
            user_first_name = ''
        user_account = request.GET.get('user_account')
        if not user_account:
            user_account = ''
        user_role = request.GET.get('user_role')
        if not user_role:
            user_role = ''
        company_name = request.GET.get('company_name')
        if not company_name:
            company_name = ''
        department_name = request.GET.get('department_name')
        if not department_name:
            department_name = ''
        created_at_min = request.GET.get('created_at_min')
        if not created_at_min:
            created_at_min = ''
        created_at_max = request.GET.get('created_at_max')
        if not created_at_max:
            created_at_max = ''
        page_add += f'?page={now_page}&per_page_num={now_page_range}&user_first_name={user_first_name}' \
                    f'&user_account={user_account}&user_role={user_role}&company_name={company_name}' \
                    f'&department_name={department_name}&created_at_min={created_at_min}' \
                    f'&created_at_max={created_at_max}'
    elif backpage == 'COMPANY_DETAIL':
        now_page = request.GET.get('page')
        if not now_page:
            now_page = ''
        page_add += f'?page={now_page}'

    app_user = AppUser.objects.filter(pub_id=user_id)
    if not app_user.exists():
        return HttpResponseRedirect(reverse('user_management') + page_add)
    else:
        app_user = app_user.first()
        if edit_flag == '1':
            # if not app_user.auth_user.role_set.filter(name=Role.MANAGEMENT).exists():
            #     app_user.auth_user.role_set.add(Role.objects.get(name='Management'))
            if staff_id == 'DEFAULT':
                user_company = UserCompanyTable.objects.filter(app_user=app_user, default_show=True)
            else:
                user_company = UserCompanyTable.objects.filter(app_user=app_user, pub_id=staff_id)
            if not user_company.exists():
                if backpage == 'DETAIL':
                    return HttpResponseRedirect(reverse('user_detail', kwargs={'pub_id': user_id}))
                elif backpage == 'COMPANY_DETAIL':
                    return HttpResponseRedirect(reverse(
                        'company_detail', kwargs={'pub_id': company_id}) + page_add)
                else:
                    return HttpResponseRedirect(reverse('user_management') + page_add)
            else:
                user_company = user_company.first()
                if manage_type == 'MANAGE':
                    user_company.manage_enabled = True
                    user_company.department_manage_enabled = False
                    user_company.save(update_fields=['manage_enabled', 'department_manage_enabled', 'modified'])
                    dep_manage_list = app_user.usercompanytable_set.filter(
                        company=user_company.company, department_manage_enabled=True)
                    if dep_manage_list.exists():
                        for dep_manage in dep_manage_list:
                            dep_manage.department_manage_enabled = False
                            dep_manage.save(update_fields=['department_manage_enabled', 'modified'])
                    if not app_user.auth_user.role_set.filter(name=Role.MANAGEMENT).exists():
                        app_user.auth_user.role_set.add(Role.objects.get(name='Management'))
                    ActionLog.objects.create(user_account=request.user, log_type='User_Privilege_Changed_Manager')
                elif manage_type == 'DEP_MANAGE':
                    manage_list = app_user.usercompanytable_set.filter(
                        company=user_company.company, manage_enabled=True)
                    if manage_list.exists():
                        for user_manage in manage_list:
                            user_manage.manage_enabled = False
                            user_manage.save(update_fields=['manage_enabled', 'modified'])
                    user_company.department_manage_enabled = True
                    user_company.save(update_fields=['department_manage_enabled', 'modified'])
                    if not app_user.auth_user.role_set.filter(name=Role.MANAGEMENT).exists():
                        app_user.auth_user.role_set.add(Role.objects.get(name='Management'))
                    ActionLog.objects.create(user_account=request.user, log_type='User_Privilege_Changed_Dep_Manager')
                elif manage_type == 'SCAN':
                    user_company.scan_enabled = True
                    user_company.save(update_fields=['scan_enabled', 'modified'])
                    ActionLog.objects.create(user_account=request.user, log_type='User_Privilege_Changed_Healthcode')
        else:
            if staff_id == 'DEFAULT':
                user_company = UserCompanyTable.objects.filter(app_user=app_user, default_show=True)
            else:
                user_company = UserCompanyTable.objects.filter(app_user=app_user, pub_id=staff_id)
            if not user_company.exists():
                return HttpResponseRedirect(reverse('user_detail', kwargs={'pub_id': user_id}))
            else:
                user_company = user_company.first()
                if manage_type == 'MANAGE':
                    user_company.manage_enabled = False
                    user_company.save(update_fields=['manage_enabled', 'modified'])
                    if (app_user.auth_user.role_set.filter(name=Role.MANAGEMENT).exists() and
                            not app_user.usercompanytable_set.filter(
                                Q(manage_enabled=True) | Q(department_manage_enabled=True)
                            ).exists()):
                        app_user.auth_user.role_set.remove(Role.objects.get(name='Management'))
                    ActionLog.objects.create(user_account=app_user.auth_user.username, status=1)
                elif manage_type == 'DEP_MANAGE':
                    user_company.department_manage_enabled = False
                    user_company.save(update_fields=['department_manage_enabled', 'modified'])
                    if (app_user.auth_user.role_set.filter(name=Role.MANAGEMENT).exists() and
                            not app_user.usercompanytable_set.filter(
                                Q(manage_enabled=True) | Q(department_manage_enabled=True)
                            ).exists()):
                        app_user.auth_user.role_set.remove(Role.objects.get(name='Department Management'))
                    ActionLog.objects.create(user_account=app_user.auth_user.username, status=2)
                elif manage_type == 'SCAN':
                    user_company.scan_enabled = False
                    user_company.save(update_fields=['scan_enabled', 'modified'])
                    ActionLog.objects.create(user_account=app_user.auth_user.username, status=3)

        request.session['nav_no_reset'] = 1
        if backpage == 'DETAIL':
            return HttpResponseRedirect(reverse('user_detail', kwargs={'pub_id': user_id}))
        elif backpage == 'COMPANY_DETAIL':
            return HttpResponseRedirect(reverse('company_detail', kwargs={'pub_id': company_id}) + page_add)
        else:
            return HttpResponseRedirect(reverse('user_management') + page_add)


@login_required4
def company_management(request):
    return_data = dict()
    no_company_user_num = AppUser.objects.filter(
        usercompanytable__isnull=True) | AppUser.objects.exclude(usercompanytable__employed=True)
    if no_company_user_num.exists():
        return_data['no_company_user_num'] = no_company_user_num.count()
    else:
        return_data['no_company_user_num'] = 0
    company_list = Company.objects.all()
    return_data['company_name_list'] = [company.name for company in company_list]

    company_name = request.GET.get('company_name')
    created_at_min = request.GET.get('created_at_min')
    created_at_max = request.GET.get('created_at_max')

    if company_name:
        company_list = company_list.filter(name=company_name)

    if created_at_min:
        try:
            create_at_min = datetime.strptime(created_at_min, '%Y-%m-%d %H:%M')
        except (TypeError, ValueError) as e:
            pass
        else:
            company_list = company_list.filter(created__gte=timezone.make_aware(create_at_min))

    if created_at_max:
        try:
            # Plus one day to cover whole day. Ex: 2018-10-10T00:00:00 -> 2018-10-11T00:00:00
            # and then we use less than expression to query
            create_at_max = datetime.strptime(created_at_max, '%Y-%m-%d %H:%M') + timedelta(days=1)
        except (TypeError, ValueError) as e:
            pass
        else:
            company_list = company_list.filter(created__lt=timezone.make_aware(create_at_max))
    return_data['user_length'] = len(company_list)
    page = request.GET.get('page')
    paginator = CachedPaginator(company_list, 15)
    try:
        company_list = paginator.get_page(page)
        page_range = paginator.page_range_list(page)
    except InvalidPage:
        # page error - log
        # request.session['return_msg'] = _('System Error')
        logger_writer('SYSTEM', 'error', 'COMPANY MANAGEMENT', f'System error: redirect to backend index')
        return HttpResponseRedirect(reverse('backend_index'))
    for company in company_list:
        company.department_num = company.department_set.all().count()
        company.staff_num = company.usercompanytable_set.filter(employed=True).distinct('app_user').count()
        add_req_list = company.addcompanytag.addrequest_set.filter(status=AddRequest.WAIT_AUDIT).values('id')
        if add_req_list.exists():
            company.add_req_num = add_req_list.count()
        else:
            company.add_req_num = 0
    return_data['page_range'] = page_range
    return_data['company_list'] = company_list
    if request.session.get('return_msg'):
        return_data['return_msg'] = request.session.pop('return_msg')
    return render(request, 'backend/admin_company_management.html', context=return_data)


@login_required4
def get_company_detail(request, pub_id):
    return_data = dict()
    company = Company.objects.filter(pub_id=pub_id)
    if not company.exists():
        return HttpResponseRedirect(reverse('company_management'))
    company = company.first()
    return_data['add_tag'] = company.addcompanytag.pub_id
    return_data['company'] = company
    return_data['department_num'] = company.department_set.all().count()
    # return_data['staff_num'] = company.usercompanytable_set.distinct('app_user').count()
    department_list = company.department_set.all()
    for department in department_list:
        department.staff_num = department.usercompanytable_set.filter(employed=True).distinct('app_user').count()
    return_data['department_list'] = department_list
    staff_list = company.usercompanytable_set.filter(employed=True).distinct('app_user')
    return_data['staff_num'] = staff_list.count()
    add_req_list = company.addcompanytag.addrequest_set.select_related(
        'add_user', 'agree_user', 'add_tag', 'add_tag__company').all().order_by('-modified')
    if add_req_list.filter(status=AddRequest.WAIT_AUDIT).count() > 0:
        return_data['new_add_req'] = True
    if request.session.get('page2'):
        page2 = request.session.pop('page2')
        if not page2.isdigit():
            page2 = None
        else:
            page2 = int(page2)
    else:
        page2 = request.GET.get('page2')

    page = request.GET.get('page')

    if page or page2:
        return_data['nav_no_reset'] = 1
    paginator = CachedPaginator(staff_list, 15)
    paginator2 = CachedPaginator(add_req_list, 15)
    try:
        staff_list = paginator.get_page(page)
        page_range = paginator.page_range_list(page)
        add_req_list = paginator2.get_page(page2)
        page_range2 = paginator2.page_range_list(page2)
    except InvalidPage:
        # page error - log
        # request.session['return_msg'] = _('System Error')
        return HttpResponseRedirect(reverse('backend_index'))
    for staff in staff_list:
        attendance_status = staff.app_user.attendancestatus_set.filter(company=staff.company)
        if attendance_status.exists():
            attendance_status = attendance_status.first()
            staff.attendance_status = attendance_status.get_status_display()
    for add_req in add_req_list:
        add_req.create_time = utc_time_to_local_time(add_req.modified)
        if 'cancel_user' in add_req.note:
            if add_req.note['cancel_user'] == 'ADMIN':
                add_req.update_user_name = _('Administrator')
                add_req.update_user_id = 'ADMIN'
            elif add_req.note['cancel_user'] == 'SELF':
                add_req.update_user_name = add_req.agree_user.auth_user.first_name
                add_req.update_user_id = add_req.agree_user.pub_id
        else:
            if add_req.agree_user:
                add_req.update_user_name = add_req.agree_user.auth_user.first_name
                add_req.update_user_id = add_req.agree_user.pub_id
    return_data['staff_list'] = staff_list
    return_data['page_range'] = page_range
    return_data['add_req_list'] = add_req_list
    return_data['page_range2'] = page_range2
    if request.session.get('nav_no_reset'):
        return_data['nav_no_reset'] = request.session.pop('nav_no_reset')
    if request.session.get('return_msg'):
        return_data['return_msg'] = request.session.pop('return_msg')
    return render(request, 'backend/admin_company_detail.html', context=return_data)


@login_required4
def no_company_detail(request):
    return_data = dict()
    per_page_num = request.GET.get('per_page_num')
    if not per_page_num:
        per_page_num = 10

    app_user_list = AppUser.objects.filter(
        usercompanytable__isnull=True) | AppUser.objects.exclude(usercompanytable__employed=True)

    app_user_name_list = list()
    app_user_account_list = list()
    for app_user in app_user_list:
        if app_user.auth_user.first_name not in app_user_name_list:
            app_user_name_list.append(app_user.auth_user.first_name)
        app_user_account_list.append(app_user.auth_user.username)
    return_data['app_user_name_list'] = app_user_name_list
    return_data['app_user_account_list'] = app_user_account_list

    user_first_name = request.GET.get('user_first_name')
    user_account = request.GET.get('user_account')
    created_at_min = request.GET.get('created_at_min')
    created_at_max = request.GET.get('created_at_max')

    if user_first_name:
        app_user_list = app_user_list.filter(auth_user__first_name=user_first_name)

    if user_account:
        app_user_list = app_user_list.filter(auth_user__username=user_account)

    if created_at_min:
        try:
            create_at_min = datetime.strptime(created_at_min, '%Y-%m-%d %H:%M')
        except (TypeError, ValueError) as e:
            pass
        else:
            app_user_list = app_user_list.filter(created__gte=timezone.make_aware(create_at_min))

    if created_at_max:
        try:
            # Plus one day to cover whole day. Ex: 2018-10-10T00:00:00 -> 2018-10-11T00:00:00
            # and then we use less than expression to query
            create_at_max = datetime.strptime(created_at_max, '%Y-%m-%d %H:%M') + timedelta(days=1)
        except (TypeError, ValueError) as e:
            pass
        else:
            app_user_list = app_user_list.filter(created__lt=timezone.make_aware(create_at_max))

    return_data['user_length'] = len(app_user_list)

    page = request.GET.get('page')
    paginator = CachedPaginator(app_user_list, per_page_num)
    try:
        app_user_list = paginator.get_page(page)
        page_range = paginator.page_range_list(page)
    except InvalidPage:
        # page error - log
        # request.session['return_msg'] = _('System Error')
        return HttpResponseRedirect(reverse('backend_index'))
    return_data['app_user_list'] = app_user_list
    return_data['page_range'] = page_range
    return render(request, 'backend/no_company_user_list.html', context=return_data)


@login_required4
def place_create_open(request, pub_id, status):
    company = Company.objects.filter(pub_id=pub_id)
    if company.exists():
        company = company.first()
        if status == 'ON':
            company.place_create = True
            serial_num = ''.join(random.choice(string.ascii_letters + string.digits) for x in range(6)).upper()
            while Company.objects.filter(verification_code=serial_num).exists():
                serial_num = ''.join(random.choice(string.ascii_letters + string.digits) for x in range(6)).upper()
            company.verification_code = serial_num
        else:
            company.place_create = False
        company.save()
    return HttpResponseRedirect(reverse('company_detail', kwargs={'pub_id': pub_id}))


@login_required4
def del_staff(request, pub_id):
    now_page = request.POST.get('del_now_page')
    if not now_page:
        now_page = ''
    staff_id = request.POST.get('staff_id')
    if staff_id:
        user_company = UserCompanyTable.objects.filter(company__pub_id=pub_id, pub_id=staff_id, employed=True)
        if user_company.exists():
            user_company = user_company.first()
            user_company.employed = False
            user_company.scan_enabled = False
            user_company.manage_enabled = False
            user_company.default_show = False
            user_company.save()
            staff_history = user_company.usercompanyhistory_set.filter(end_time__isnull=True).order_by('-created')
            if staff_history.exists():
                staff_history = staff_history.first()
                staff_history.end_time = local_time_to_utc_time(datetime.now())
                staff_history.save(update_fields=['modified', 'end_time'])

            other = UserCompanyTable.objects.filter(app_user=user_company.app_user).exclude(pub_id=staff_id)
            if other.exists():
                if not other.filter(default_show=True).exists():
                    other_user_company = other.first()
                    other_user_company.default_show = True
                    other_user_company.save(update_fields=['modified', 'default_show'])
    return HttpResponseRedirect(reverse('company_detail', kwargs={'pub_id': pub_id}) + f'?page={now_page}')


@login_required4
def web_creat_company(request):
    company_name = request.POST.get('add_company_name')
    if company_name:
        try:
            company = CompanyServices.create_company(company_name=company_name)
            # CompanyDefaultPrint.objects.create(
            #     company=company,
            #     place_code={
            #         "fst_line": "為防範嚴重特殊傳染性肺炎",
            #         "sec_line": "請以通行碼APP掃描此地點做地點紀錄",
            #         "last_line": "守護你我健康",
            #         "thd_line": "",
            #         "forth_line": "～來訪賓客也須配合填寫～"
            #     })
        except Exception as e:
            request.session['return_msg'] = CompanyAlreadyExists.msg
            logger_writer('SYSTEM', 'info', 'WEB CREATE COMPANY', f'company already exists')
    return HttpResponseRedirect(reverse('company_management'))


@login_required4
def web_creat_department(request, pub_id):
    department_name = request.POST.get('add_department_name')
    # manage_role = request.session.get('manage_role')
    # manage_id = request.session.get('manage_id')
    # if manage_role != 'COMPANY':
    #     return HttpResponseRedirect(reverse('company_index', kwargs={'pub_id': pub_id}))
    # manage_id = Company.objects.filter(pub_id=pub_id)
    # manage_id = manage_id.first()
    if department_name:
        try:
            CompanyServices.create_department(company_id=pub_id, department_name=department_name)
        except Exception as e:
            request.session['return_msg'] = DepartmentAlreadyExists.msg
            logger_writer('SYSTEM', 'info', 'WEB CREATE DEPARTMENT', f'department already exists')
    if request.user_role == 'ADMIN':
        return HttpResponseRedirect(reverse('company_detail', kwargs={'pub_id': pub_id}))
    else:
        return HttpResponseRedirect(reverse('department_management', kwargs={'pub_id': pub_id}))


@login_required4
def web_del_department(request, pub_id):
    department_id = request.POST.get('del_department_id')
    if department_id:
        try:
            department = Department.objects.get(pub_id=department_id)
        except Exception as e:
            request.session['return_msg'] = DepartmentAlreadyExists.msg
            logger_writer('SYSTEM', 'info', 'WEB DEL DEPARTMENT', f'department already exists')
        else:
            if department.usercompanytable_set.all().exists():
                request.session['return_msg'] = _('The department have staff')
                logger_writer('SYSTEM', 'info', 'WEB DEL DEPARTMENT', f'Department: {department.name}: have staff')
            else:
                request.session['return_msg'] = _('The department has been delete')
                logger_writer('SYSTEM', 'info', 'WEB DEL DEPARTMENT', f'Department: {department.name}: has been deleted')
                del department

    if request.user_role == 'ADMIN':
        return HttpResponseRedirect(reverse('company_detail', kwargs={'pub_id': pub_id}))
    else:
        return HttpResponseRedirect(reverse('department_management', kwargs={'pub_id': pub_id}))


@login_required4
def place_management(request):
    return_data = dict()
    per_page_num = request.GET.get('per_page_num')
    if not per_page_num:
        per_page_num = 10
    place_list = Place.objects.all().order_by('-id')
    place_name_list = list()
    place_address_list = list()
    for place in place_list:
        place_name_list.append(place.name)
        if 'location_address' in place.location:
            place_address_list.append(place.location['location_address'])
    return_data['place_name_list'] = place_name_list
    return_data['place_address_list'] = place_address_list

    place_name = request.GET.get('place_name')
    place_address = request.GET.get('place_address')
    company_name = request.GET.get('company_name')

    if place_name:
        place_list = place_list.filter(name__icontains=place_name)

    if place_address:
        place_list = place_list.filter(address__icontains=place_address)

    if company_name:
        place_list = place_list.filter(company__name=company_name)
    return_data['user_length'] = len(place_list)
    page = request.GET.get('page')
    if not page:
        if request.session.get('check_place'):
            request.session.pop('check_place')
        if request.session.get('check_place_num'):
            request.session.pop('check_place_num')
    paginator = CachedPaginator(place_list, per_page_num)
    try:
        place_list = paginator.get_page(page)
        page_range = paginator.page_range_list(page)
    except InvalidPage:
        # page error - log
        # request.session['return_msg'] = _('System Error')
        logger_writer('SYSTEM', 'error', 'PLACE MANAGEMENT', f'system error, redirected to backend index')
        return HttpResponseRedirect(reverse('backend_index'))
    return_data['place_list'] = place_list
    return_data['company_list'] = Company.objects.all()
    return_data['page_range'] = page_range
    return render(request, 'backend/place_management.html', context=return_data)


@login_required4
def edit_place(request, edit_type):
    back_page = reverse('place_management')
    if edit_type == 'ADD':
        add_place_name = request.POST.get('add_place_name')
        add_place_address = request.POST.get('add_place_address')
        company_id = request.POST.get('company_id')
        if add_place_name:
            if company_id:
                if not Place.objects.filter(company__pub_id=company_id, name=add_place_name).exists():
                    CompanyServices.create_place(place_name=add_place_name, address=add_place_address,
                                                 company_id=company_id)
                else:
                    # TODO: 重複地點提示
                    pass
            else:
                CompanyServices.create_place(place_name=add_place_name, address=add_place_address)
    elif edit_type == 'EDIT':
        now_page = request.POST.get('edit_now_page')
        if not now_page:
            now_page = ''
        now_page_range = request.POST.get('edit_now_page_range')
        if not now_page_range:
            now_page_range = ''
        place_name = request.POST.get('edit_search_place_name')
        if not place_name:
            place_name = ''
        place_address = request.POST.get('edit_search_place_address')
        if not place_address:
            place_address = ''
        company_name = request.POST.get('edit_search_company_name')
        if not company_name:
            company_name = ''
        edit_place_id = request.POST.get('edit_place_id')
        edit_place_name = request.POST.get('edit_place_name')
        edit_place_address = request.POST.get('edit_place_address')
        # edit_place_user = request.POST.get('edit_place_user')
        edit_place_contact_phone = request.POST.get('edit_place_contact_phone')
        edit_update_enabled = request.POST.get('edit_update_enabled')
        place = Place.objects.select_related('company').filter(pub_id=edit_place_id)
        if place.exists():
            place = place.first()
            if place.company:
                if not Place.objects.filter(company__pub_id=place.company.pub_id, name=edit_place_name).exists():
                    if edit_place_name != '':
                        place.name = edit_place_name
                    if edit_place_address:
                        location_dict = place.location
                        if type(location_dict) != dict:
                            location_dict = {'location_address': edit_place_address}
                        else:
                            location_dict['location_address'] = edit_place_address
                        place.location = location_dict
                    # if edit_place_user:
                    #     place.place_user = edit_place_user
                    if edit_place_contact_phone:
                        place.place_contact_phone = edit_place_contact_phone
                    place.save(update_fields=['name'])
                else:
                    # TODO: 重複地點提示
                    pass
                if edit_place_address:
                    location_dict = place.location
                    if type(location_dict) != dict:
                        location_dict = {'location_address': edit_place_address}
                    else:
                        location_dict['location_address'] = edit_place_address
                    place.location = location_dict
                # if edit_place_user:
                #     place.place_user = edit_place_user
                if edit_place_contact_phone:
                    place.place_contact_phone = edit_place_contact_phone
                if not edit_update_enabled:
                    place.update_health_code = False
                else:
                    place.update_health_code = True
                place.save(update_fields=['update_health_code', 'location', 'place_user', 'place_contact_phone'])
            else:
                if edit_place_name != '':
                    place.name = edit_place_name
                if edit_place_address:
                    location_dict = place.location
                    if type(location_dict) != dict:
                        location_dict = {'location_address': edit_place_address}
                    else:
                        location_dict['location_address'] = edit_place_address
                    place.location = location_dict
                # if edit_place_user:
                #     place.place_user.username = edit_place_user
                if edit_place_contact_phone:
                    place.place_contact_phone = edit_place_contact_phone
                if not edit_update_enabled:
                    place.update_health_code = False
                else:
                    place.update_health_code = True
                place.save(update_fields=['name', 'update_health_code', 'location', 'place_user', 'place_contact_phone'])
        back_page += f'?page={now_page}&place_address={place_address}&place_name={place_name}' \
                     f'&company_name={company_name}&per_page_num={now_page_range}'
    elif edit_type == 'DEL':
        now_page = request.POST.get('del_now_page')
        if not now_page:
            now_page = ''
        now_page_range = request.POST.get('del_now_page_range')
        if not now_page_range:
            now_page_range = ''
        place_name = request.POST.get('del_search_place_name')
        if not place_name:
            place_name = ''
        place_address = request.POST.get('edit_search_place_address')
        if not place_address:
            place_address = ''
        company_name = request.POST.get('del_search_company_name')
        if not company_name:
            company_name = ''
        del_place_id = request.POST.get('del_place_id')
        place = Place.objects.select_related('company').filter(pub_id=del_place_id)
        if place.exists():
            place.first().delete()
        back_page += f'?page={now_page}&place_name={place_name}&place_address={place_address}' \
                     f'&company_name={company_name}&per_page_num={now_page_range}'
    return HttpResponseRedirect(back_page)


@login_required4
def place_verify(request):
    back_page = reverse('place_management')
    verify_place_pub_id = request.POST.get('verify_place_pub_id')
    place = Place.objects.filter(pub_id=verify_place_pub_id, company_verify=Place.NOT_VERIFY)
    if place.exists():
        place = place.first()
        verify_status = request.POST.get('verify_status')
        if verify_status == 'YES':
            place.company_verify = 1
            user_account = request.POST.get('user_account')
            verify_place_name = request.POST.get('verify_place_name')
            if verify_place_name and place.name != verify_place_name:
                place.name = verify_place_name
            verify_place_address = request.POST.get('verify_place_address')
            if verify_place_address and place.address != verify_place_address:
                place.address = verify_place_address
            verify_place_phone = request.POST.get('verify_place_phone')
            if verify_place_phone and place.place_contact_phone != verify_place_phone:
                place.place_contact_phone = verify_place_phone
            ActionLog.objects.create(user_account=request.user, log_type='Place_Pass')
        else:
            place.company_verify = 2
            ActionLog.objects.create(user_account=request.user, log_type='Place_Not_Pass')
        place.save()

    now_page = request.POST.get('verify_now_page')
    if not now_page:
        now_page = ''
    now_page_range = request.POST.get('verify_now_page_range')
    if not now_page_range:
        now_page_range = ''
    place_name = request.POST.get('verify_search_place_name')
    if not place_name:
        place_name = ''
    place_address = request.POST.get('verify_search_place_address')
    if not place_address:
        place_address = ''
    company_name = request.POST.get('verify_search_company_name')
    if not company_name:
        company_name = ''
    back_page += f'?page={now_page}&place_name={place_name}&place_address={place_address}' \
                 f'&company_name={company_name}&per_page_num={now_page_range}'
    return HttpResponseRedirect(back_page)


@login_required4
def user_tract_old(request):
    return_data = dict()
    per_page_num = request.GET.get('per_page_num')
    if not per_page_num:
        per_page_num = 10
    approach_list = ApproachRecord.objects.select_related(
        'app_user', 'scan_user', 'app_user__auth_user', 'scan_user__auth_user').all()
    place_entry_list = PlaceEntryRecord.objects.select_related(
        'place_entry', 'app_user__auth_user', 'place_entry__company').all()

    user_first_name = request.GET.get('user_first_name')
    user_account = request.GET.get('user_account')
    company_name = request.GET.get('company_name')
    place_name = request.GET.get('place_name')
    created_at_min = request.GET.get('created_at_min')
    created_at_max = request.GET.get('created_at_max')

    search_list = ApproachRecord.objects.none()
    search_type = None

    if user_first_name:
        return_data['sel_type'] = 'fst_name'
        search_type = 'USER'
        search_list = approach_list.filter(
            Q(app_user__auth_user__first_name=user_first_name) |
            Q(scan_user__auth_user__first_name=user_first_name)).order_by('-created')

    if user_account:
        return_data['sel_type'] = 'account'
        search_type = 'USER'
        search_list = approach_list.filter(
            Q(app_user__auth_user__username=user_account) |
            Q(scan_user__auth_user__username=user_account)).order_by('-created')

    if company_name:
        return_data['sel_type'] = 'company'
        search_type = 'PLACE'
        search_list = place_entry_list.filter(place_entry__company__name=company_name).order_by('-created')

    if place_name:
        return_data['sel_type'] = 'place'
        search_type = 'PLACE'
        search_list = place_entry_list.filter(place_entry__name=place_name).order_by('-created')

    if created_at_min and search_type:
        try:
            create_at_min = datetime.strptime(created_at_min, '%Y-%m-%d %H:%M')
        except (TypeError, ValueError) as e:
            pass
        else:
            search_list = search_list.filter(created__gte=timezone.make_aware(create_at_min))

    if created_at_max and search_type:
        try:
            # Plus one day to cover whole day. Ex: 2018-10-10T00:00:00 -> 2018-10-11T00:00:00
            # and then we use less than expression to query
            create_at_max = datetime.strptime(created_at_max, '%Y-%m-%d %H:%M') + timedelta(days=1)
        except (TypeError, ValueError) as e:
            pass
        else:
            search_list = search_list.filter(created__lt=timezone.make_aware(create_at_max))
    search_list_result = list()
    if search_type:
        if search_type == 'USER':
            for search in search_list:
                if search.app_user.auth_user.first_name == user_first_name:
                    approach_user = search.scan_user
                else:
                    approach_user = search.app_user
                user_company = approach_user.usercompanytable_set.select_related(
                    'company', 'department').filter(default_show=True)
                if not user_company.exists():
                    company_name = ''
                    department_name = ''
                    company_id = ''
                else:
                    user_company_info = user_company.first()
                    company_name = user_company_info.company.name
                    department_name = user_company_info.department.name
                    company_id = user_company_info.company.pub_id
                search_list_result.append((
                    search.created,
                    approach_user.auth_user.first_name,
                    company_name,
                    department_name,
                    approach_user.pub_id,
                    company_id,
                    approach_user.auth_user.username
                ))
        else:
            for search in search_list:
                user_company = search.app_user.usercompanytable_set.select_related(
                    'company', 'department').filter(default_show=True)
                if not user_company.exists():
                    company_name = ''
                    department_name = ''
                    company_id = ''
                else:
                    user_company_info = user_company.first()
                    company_name = user_company_info.company.name
                    department_name = user_company_info.department.name
                    company_id = user_company_info.company.pub_id
                search_list_result.append((
                    search.created,
                    search.app_user.auth_user.first_name,
                    company_name,
                    department_name,
                    search.app_user.pub_id,
                    company_id,
                    search.app_user.auth_user.username,
                ))
        return_data['user_length'] = len(search_list_result)

    page = request.GET.get('page')
    paginator = CachedPaginator(search_list_result, per_page_num)
    try:
        search_list_result = paginator.get_page(page)
        page_range = paginator.page_range_list(page)
    except InvalidPage:
        # page error - log
        # request.session['return_msg'] = _('System Error')
        logger_writer('SYSTEM', 'error', 'USER TRACK', f'System error, redirect to backend index')
        return HttpResponseRedirect(reverse('backend_index'))
    return_data['search_list_result'] = search_list_result
    return_data['page_range'] = page_range
    app_user_name_list = list()
    app_user_account_list = list()
    for app_user in AppUser.objects.all():
        if app_user.auth_user.first_name not in app_user_name_list:
            app_user_name_list.append(app_user.auth_user.first_name)
        app_user_account_list.append(app_user.auth_user.username)
    return_data['app_user_name_list'] = app_user_name_list
    return_data['app_user_account_list'] = app_user_account_list
    return_data['company_list'] = Company.objects.all()
    return_data['place_list'] = Place.objects.all()

    return render(request, 'backend/all_approach_track.html', context=return_data)


@login_required4
def user_tract(request):
    return_data = dict()
    per_page_num = request.GET.get('per_page_num')
    if not per_page_num:
        per_page_num = 10
    approach_list = ApproachRecord.objects.select_related(
        'app_user', 'scan_user', 'app_user__auth_user', 'scan_user__auth_user').all()

    user_first_name = request.GET.get('user_first_name')
    user_account = request.GET.get('user_account')
    created_at_min = request.GET.get('created_at_min')
    created_at_max = request.GET.get('created_at_max')

    approach_record_list = ApproachRecord.objects.none()

    if user_first_name:
        return_data['sel_type'] = 'fst_name'
        approach_record_list = approach_list.filter(
            Q(app_user__auth_user__first_name=user_first_name) |
            Q(scan_user__auth_user__first_name=user_first_name)).order_by('-created')

    if user_account:
        return_data['sel_type'] = 'account'
        approach_record_list = approach_list.filter(
            Q(app_user__auth_user__username=user_account) |
            Q(scan_user__auth_user__username=user_account)).order_by('-created')

    if created_at_min:
        try:
            create_at_min = datetime.strptime(created_at_min, '%Y-%m-%d %H:%M')
        except (TypeError, ValueError) as e:
            pass
        else:
            approach_record_list = approach_record_list.filter(created__gte=timezone.make_aware(create_at_min))

    if created_at_max:
        try:
            # Plus one day to cover whole day. Ex: 2018-10-10T00:00:00 -> 2018-10-11T00:00:00
            # and then we use less than expression to query
            create_at_max = datetime.strptime(created_at_max, '%Y-%m-%d %H:%M') + timedelta(days=1)
        except (TypeError, ValueError) as e:
            pass
        else:
            approach_record_list = approach_record_list.filter(created__lt=timezone.make_aware(create_at_max))

    return_data['user_length'] = len(approach_record_list)
    page = request.GET.get('page')
    paginator = CachedPaginator(approach_record_list, per_page_num)
    try:
        approach_record_list = paginator.get_page(page)
        page_range = paginator.page_range_list(page)
    except InvalidPage:
        # page error - log
        # request.session['return_msg'] = _('System Error')
        logger_writer('SYSTEM', 'error', 'USER TRACT', f'System error, redirect to backend index')
        return HttpResponseRedirect(reverse('backend_index'))
    for record in approach_record_list:
        if user_first_name:
            if record.app_user.auth_user.first_name == user_first_name:
                record.approach_user = record.scan_user
            else:
                record.approach_user = record.app_user
        if user_account:
            if record.app_user.auth_user.username == user_account:
                record.approach_user = record.scan_user
            else:
                record.approach_user = record.app_user
        user_company = record.approach_user.usercompanytable_set.select_related(
            'company', 'department').filter(default_show=True)
        if not user_company.exists():
            company_name = ''
            department_name = ''
            company_id = ''
        else:
            user_company_info = user_company.first()
            company_name = user_company_info.company.name
            if user_company_info.department:
                department_name = user_company_info.department.name
            else:
                department_name = ''
            company_id = user_company_info.company.pub_id
        record.create_time = utc_time_to_local_time(record.created)
        record.company_id = company_id
        record.company_name = company_name
        record.department_name = department_name
    return_data['approach_record_list'] = approach_record_list
    return_data['page_range'] = page_range
    app_user_name_list = list()
    app_user_account_list = list()
    for app_user in AppUser.objects.all():
        if app_user.auth_user.first_name not in app_user_name_list:
            app_user_name_list.append(app_user.auth_user.first_name)
        app_user_account_list.append(app_user.auth_user.username)
    return_data['app_user_name_list'] = app_user_name_list
    return_data['app_user_account_list'] = app_user_account_list
    return render(request, 'backend/user_approach_track.html', context=return_data)


@login_required4
def place_tract(request):
    return_data = dict()

    per_page_num = request.GET.get('per_page_num')
    if not per_page_num:
        per_page_num = 10
    place_entry_list = PlaceEntryRecord.objects.select_related(
        'place_entry', 'app_user__auth_user', 'place_entry__company').filter(place_entry__isnull=False)

    company_name = request.GET.get('company_name')
    place_name = request.GET.get('place_name')
    created_at_min = request.GET.get('created_at_min')
    created_at_max = request.GET.get('created_at_max')

    if company_name:
        return_data['sel_type'] = 'company'
        place_entry_list = place_entry_list.filter(place_entry__company__name=company_name).order_by('-created')

    if place_name:
        return_data['sel_type'] = 'place'
        place_entry_list = place_entry_list.filter(place_entry__name=place_name).order_by('-created')

    if created_at_min:
        try:
            create_at_min = datetime.strptime(created_at_min, '%Y-%m-%d %H:%M')
        except (TypeError, ValueError) as e:
            pass
        else:
            place_entry_list = place_entry_list.filter(created__gte=timezone.make_aware(create_at_min))

    if created_at_max:
        try:
            # Plus one day to cover whole day. Ex: 2018-10-10T00:00:00 -> 2018-10-11T00:00:00
            # and then we use less than expression to query
            create_at_max = datetime.strptime(created_at_max, '%Y-%m-%d %H:%M') + timedelta(days=1)
        except (TypeError, ValueError) as e:
            pass
        else:
            place_entry_list = place_entry_list.filter(created__lt=timezone.make_aware(create_at_max))

    return_data['user_length'] = len(place_entry_list)
    page = request.GET.get('page')
    paginator = CachedPaginator(place_entry_list, per_page_num)
    try:
        place_entry_list = paginator.get_page(page)
        page_range = paginator.page_range_list(page)
    except InvalidPage:
        # page error - log
        # request.session['return_msg'] = _('System Error')
        logger_writer('SYSTEM', 'error', 'PLACE TRACT', f'System error: redirect to backend index')
        return HttpResponseRedirect(reverse('backend_index'))
    for record in place_entry_list:
        user_company = record.app_user.usercompanytable_set.select_related(
            'company', 'department').filter(default_show=True)
        if not user_company.exists():
            company_name = ''
            department_name = ''
            company_id = ''
        else:
            user_company_info = user_company.first()
            company_name = user_company_info.company.name
            if user_company_info.department:
                department_name = user_company_info.department.name
            else:
                department_name = ''
            company_id = user_company_info.company.pub_id
        record.create_time = utc_time_to_local_time(record.created)
        record.company_id = company_id
        record.company_name = company_name
        record.department_name = department_name

    return_data['place_entry_list'] = place_entry_list
    return_data['page_range'] = page_range
    return_data['company_list'] = Company.objects.all()
    return_data['place_list'] = Place.objects.all()
    return render(request, 'backend/place_track.html', context=return_data)


@login_required4
def new_company_apply_req(request):
    return_data = dict()
    per_page_num = request.GET.get('per_page_num')
    if not per_page_num:
        per_page_num = 10
    new_company_apply_list = NewCompanyApply.objects.all().order_by('-created')

    company_name = request.GET.get('company_name')
    tax_id_num = request.GET.get('tax_id_num')
    created_at_min = request.GET.get('created_at_min')
    created_at_max = request.GET.get('created_at_max')

    if company_name:
        new_company_apply_list = new_company_apply_list.filter(company_name=company_name)

    if tax_id_num:
        new_company_apply_list = new_company_apply_list.filter(tax_id_number=tax_id_num)

    if created_at_min:
        try:
            create_at_min = datetime.strptime(created_at_min, '%Y-%m-%d %H:%M')
        except (TypeError, ValueError) as e:
            pass
        else:
            new_company_apply_list = new_company_apply_list.filter(created__gte=timezone.make_aware(create_at_min))

    if created_at_max:
        try:
            # Plus one day to cover whole day. Ex: 2018-10-10T00:00:00 -> 2018-10-11T00:00:00
            # and then we use less than expression to query
            create_at_max = datetime.strptime(created_at_max, '%Y-%m-%d %H:%M') + timedelta(days=1)
        except (TypeError, ValueError) as e:
            pass
        else:
            new_company_apply_list = new_company_apply_list.filter(created__lt=timezone.make_aware(create_at_max))

    page = request.GET.get('page')
    paginator = CachedPaginator(new_company_apply_list, per_page_num)
    try:
        new_company_apply_list = paginator.get_page(page)
        page_range = paginator.page_range_list(page)
    except InvalidPage:
        # page error - log
        # request.session['return_msg'] = _('System Error')
        logger_writer('SYSTEM', 'error', 'NEW COMPANY APPLY', f'System error: redirect to backend index')
        return HttpResponseRedirect(reverse('backend_index'))
    if request.session.get('return_msg'):
        return_data['return_msg'] = request.session.pop('return_msg')
    return_data['add_req_list'] = new_company_apply_list
    return render(request, 'backend/new_company_apply.html', context=return_data)


@login_required4
def update_new_company_apply_req(request, update_type):
    apply_id = request.POST.get('apply_id')
    if not apply_id:
        request.session['return_msg'] = _('Application does not exist')
        logger_writer('SYSTEM', 'info', 'UPDATE NEW COMPANY APPLY', f'Application: {apply_id} does not exist')
    else:
        com_req = NewCompanyApply.objects.filter(pub_id=apply_id, status=NewCompanyApply.WAIT_AUDIT)
        if com_req.exists():
            com_req = com_req.first()
            if update_type == 'AGREE':
                com_req.status = NewCompanyApply.AGREE
                com_req.save(update_fields=['modified', 'status'])

                company = CompanyServices.create_company(company_name=com_req.company_name)
                company.tax_id_number = com_req.tax_id_number
                company.save()
                AttendanceStatus.objects.create(company=company, app_user=com_req.apply_user)
                user_company = UserCompanyTable.objects.create(app_user=com_req.apply_user, company=company)
                UserCompanyHistory.objects.create(user_company_table=user_company,
                                                  start_time=user_company.created)
            else:
                com_req.status = NewCompanyApply.CANCEL
                com_req.save(update_fields=['modified', 'status'])
        else:
            request.session['return_msg'] = _('Application does not exist')
    return HttpResponseRedirect(reverse('new_company_apply_req'))


# company
@login_required4
def staff_management(request, pub_id):
    return_data = dict()
    manage_role = request.session.get('manage_role')
    manage_id = request.session.get('manage_id')

    per_page_num = request.GET.get('per_page_num')
    if not per_page_num:
        per_page_num = 10
    page = request.GET.get('page')
    if manage_role == 'COMPANY':
        company = Company.objects.filter(pub_id=manage_id)
        if not company.exists():
            return HttpResponseRedirect(reverse('backend_logout'))
        else:
            company = company.first()
        app_user_list = company.usercompanytable_set.select_related(
            'app_user', 'department').filter(employed=True).distinct('app_user')
        return_data['department_list'] = company.department_set.all()
    else:
        department = Department.objects.filter(pub_id=manage_id)
        if not department.exists():
            return HttpResponseRedirect(reverse('backend_logout'))
        else:
            department = department.first()
        app_user_list = department.usercompanytable_set.select_related(
            'app_user', 'department').filter(employed=True).distinct('app_user')

    app_user_name_list = list()
    app_user_account_list = list()
    for app_user in app_user_list:
        if app_user.app_user.auth_user.first_name not in app_user_name_list:
            app_user_name_list.append(app_user.app_user.auth_user.first_name)
        app_user_account_list.append(app_user.app_user.auth_user.username)
    return_data['app_user_name_list'] = app_user_name_list
    return_data['app_user_account_list'] = app_user_account_list

    user_first_name = request.GET.get('user_first_name')
    user_account = request.GET.get('user_account')
    department_name = request.GET.get('department_name')
    user_role = request.GET.get('user_role')
    created_at_min = request.GET.get('created_at_min')
    created_at_max = request.GET.get('created_at_max')

    if user_first_name:
        app_user_list = app_user_list.filter(app_user__auth_user__first_name=user_first_name)

    if user_account:
        app_user_list = app_user_list.filter(app_user__auth_user__username=user_account)

    if department_name:
        app_user_list = app_user_list.filter(department__name=department_name)

    if user_role:
        if user_role == 'Scanner':
            app_user_list = app_user_list.filter(scan_enabled=True)
        elif user_role == 'Department Management':
            app_user_list = app_user_list.filter(department_manage_enabled=True)
        elif user_role == 'Company Management':
            app_user_list = app_user_list.filter(manage_enabled=True)
        elif user_role == Role.APPUSER:
            app_user_list = app_user_list.filter(
                manage_enabled=False,
                app_user__auth_user__role__name=user_role).exclude(app_user__auth_user__role__name=Role.MANAGEMENT)
        else:
            app_user_list = app_user_list.none()

    if created_at_min:
        try:
            create_at_min = datetime.strptime(created_at_min, '%Y-%m-%d %H:%M')
        except (TypeError, ValueError) as e:
            pass
        else:
            app_user_list = app_user_list.filter(created__gte=timezone.make_aware(create_at_min))

    if created_at_max:
        try:
            # Plus one day to cover whole day. Ex: 2018-10-10T00:00:00 -> 2018-10-11T00:00:00
            # and then we use less than expression to query
            create_at_max = datetime.strptime(created_at_max, '%Y-%m-%d %H:%M') + timedelta(days=1)
        except (TypeError, ValueError) as e:
            pass
        else:
            app_user_list = app_user_list.filter(created__lt=timezone.make_aware(create_at_max))

    return_data['user_length'] = len(app_user_list)
    paginator = CachedPaginator(app_user_list, per_page_num)
    try:
        app_user_list = paginator.get_page(page)
        page_range = paginator.page_range_list(page)
    except InvalidPage:
        # page error - log
        # request.session['return_msg'] = _('System Error')
        return HttpResponseRedirect(reverse('company_index', kwargs={'pub_id': pub_id}))

    for app_user in app_user_list:
        work_status = app_user.app_user.attendancestatus_set.filter(company__pub_id=pub_id)
        if work_status.exists():
            app_user.work_status = work_status.first().get_status_display()

    role_dict = Role.get_role_display_to_value_dict()
    return_data['user_role_list'] = [(Role.APPUSER, role_dict[Role.APPUSER]),
                                     ('Company Management', _('Company Management')),
                                     ('Department Management', _('Department Management')),
                                     ('Scanner', _('Scanner'))]
    return_data['page_range'] = page_range
    return_data['app_user_list'] = app_user_list

    return render(request, 'backend/staff_management.html', context=return_data)


@login_required4
def get_staff_detail(request, pub_id, staff_id):
    return_data = dict()
    manage_role = request.session.get('manage_role')
    manage_id = request.session.get('manage_id')
    if manage_role == 'COMPANY':
        app_user = AppUser.objects.filter(pub_id=staff_id, usercompanytable__company__pub_id=manage_id)
    else:
        app_user = AppUser.objects.filter(pub_id=staff_id, usercompanytable__department__pub_id=manage_id)
    if not app_user.exists():
        return HttpResponseRedirect(reverse('staff_management', kwargs={'pub_id': pub_id}))
    else:
        app_user = app_user.first()
        return_data['app_user'] = app_user
        if manage_role == 'COMPANY':
            return_data['user_company_list'] = app_user.usercompanytable_set.filter(company__pub_id=manage_id)
        return_data['health_code'] = app_user.healthcode.get_code_display()
        attendance_record = app_user.attendancerecord_set.select_related('approach_place').filter(
            approach_place__company__pub_id=pub_id).order_by('-created')
        approach_record = (
                app_user.scan_user.select_related('healthrecord', 'visitorregistration').all() |
                app_user.app_user.select_related('healthrecord', 'visitorregistration').all()
        ).order_by('-created')
        place_record = app_user.placeentryrecord_set.select_related('place_entry').all().order_by('-created')
        page = request.GET.get('page')
        paginator = CachedPaginator(attendance_record, 15)
        page2 = request.GET.get('page2')
        paginator2 = CachedPaginator(approach_record, 15)
        page3 = request.GET.get('page3')
        paginator3 = CachedPaginator(place_record, 15)
        if page or page2 or page3:
            return_data['nav_no_reset'] = 1
        try:
            attendance_record = paginator.get_page(page)
            page_range = paginator.page_range_list(page)
            approach_record = paginator2.get_page(page2)
            page_range2 = paginator2.page_range_list(page2)
            place_record = paginator3.get_page(page3)
            page_range3 = paginator3.page_range_list(page3)
        except InvalidPage:
            # page error - log
            # request.session['return_msg'] = _('System Error')
            return HttpResponseRedirect(reverse('staff_management', kwargs={'pub_id': pub_id}))

        for record in place_record:
            if 'location_address' in record.location:
                record.place_location = record.location['location_address']
            elif record.place_entry:
                if record.place_entry.company.pub_id == manage_id:
                    record.place_tract = True
                record.place_location = record.place_entry.name
            elif 'latlon_latitude' in record.location and 'latlon_longitude' in record.location:
                record.place_location = 'latitude: {}, longitude: {}'.format(
                    record.location['latlon_latitude'], record.location['latlon_longitude'])
            else:
                record.place_location = _('Get Location Failed')
        for record in approach_record:
            if manage_role == 'COMPANY':
                staff = record.app_user.usercompanytable_set.filter(company__pub_id=manage_id, employed=True)
            else:
                staff = record.app_user.usercompanytable_set.filter(department__pub_id=manage_id, employed=True)
            if staff.exists():
                record.staff_id = staff.first().pub_id
                record.app_user_link = True
            if manage_role == 'COMPANY':
                scan_staff = record.scan_user.usercompanytable_set.filter(company__pub_id=manage_id, employed=True)
            else:
                scan_staff = record.scan_user.usercompanytable_set.filter(department__pub_id=manage_id, employed=True)
            if scan_staff.exists():
                record.scan_staff_id = scan_staff.first().pub_id
                record.scan_user_link = True
        return_data['attendance_record'] = attendance_record
        return_data['approach_record'] = approach_record
        return_data['place_record'] = place_record
        return_data['page_range'] = page_range
        return_data['page_range2'] = page_range2
        return_data['page_range3'] = page_range3
        return render(request, 'backend/staff_detail.html', context=return_data)


@login_required4
def edit_staff_scan_enable(request, pub_id, staff_id, edit_flag, back_page):
    staff = UserCompanyTable.objects.filter(pub_id=staff_id)
    if not staff.exists():
        return HttpResponseRedirect(reverse('staff_management', kwargs={'pub_id': pub_id}))
    else:
        staff = staff.first()
        if back_page == 'DETAIL':
            page_add = reverse('staff_detail', kwargs={'pub_id': pub_id, 'staff_id': staff.app_user.pub_id})
        else:
            if back_page[0:4] == 'DEP_':
                dep_id = back_page[4:]
                page_add = reverse('department_detail', kwargs={'pub_id': pub_id, 'department_id': dep_id})
                now_page = request.GET.get('page')
                if not now_page:
                    now_page = ''
                now_page_range = request.GET.get('per_page_num')
                if not now_page_range:
                    now_page_range = ''
                user_first_name = request.GET.get('user_first_name')
                if not user_first_name:
                    user_first_name = ''
                user_account = request.GET.get('user_account')
                if not user_account:
                    user_account = ''
                created_at_min = request.GET.get('created_at_min')
                if not created_at_min:
                    created_at_min = ''
                created_at_max = request.GET.get('created_at_max')
                if not created_at_max:
                    created_at_max = ''
                page_add += f'?page={now_page}&per_page_num={now_page_range}&user_first_name={user_first_name}' \
                            f'&user_account={user_account}&created_at_min={created_at_min}' \
                            f'&created_at_max={created_at_max}'
            else:
                page_add = reverse('staff_management', kwargs={'pub_id': pub_id})
                now_page = request.GET.get('page')
                if not now_page:
                    now_page = ''
                now_page_range = request.GET.get('per_page_num')
                if not now_page_range:
                    now_page_range = ''
                user_first_name = request.GET.get('user_first_name')
                if not user_first_name:
                    user_first_name = ''
                user_account = request.GET.get('user_account')
                if not user_account:
                    user_account = ''
                user_role = request.GET.get('user_role')
                if not user_role:
                    user_role = ''
                department_name = request.GET.get('department_name')
                if not department_name:
                    department_name = ''
                created_at_min = request.GET.get('created_at_min')
                if not created_at_min:
                    created_at_min = ''
                created_at_max = request.GET.get('created_at_max')
                if not created_at_max:
                    created_at_max = ''
                page_add += f'?page={now_page}&per_page_num={now_page_range}&user_first_name={user_first_name}' \
                            f'&user_account={user_account}&user_role={user_role}&department_name={department_name}' \
                            f'&created_at_min={created_at_min}&created_at_max={created_at_max}'

        if edit_flag == '1':
            staff.scan_enabled = True
        else:
            staff.scan_enabled = False
        staff.save(update_fields=['scan_enabled', 'modified'])
        staff.refresh_from_db(fields=['scan_enabled'])

        return HttpResponseRedirect(page_add)


@login_required4
def edit_staff_dep_manage_enable(request, pub_id, staff_id, edit_flag, back_page):
    staff = UserCompanyTable.objects.filter(pub_id=staff_id, manage_enabled=False)
    if not staff.exists():
        return HttpResponseRedirect(reverse('staff_management', kwargs={'pub_id': pub_id}))
    else:
        staff = staff.first()
        if back_page == 'DETAIL':
            page_add = reverse('staff_detail', kwargs={'pub_id': pub_id, 'staff_id': staff.app_user.pub_id})
        else:
            if back_page[0:4] == 'DEP_':
                dep_id = back_page[4:]
                page_add = reverse('department_detail', kwargs={'pub_id': pub_id, 'department_id': dep_id})
                now_page = request.GET.get('page')
                if not now_page:
                    now_page = ''
                now_page_range = request.GET.get('per_page_num')
                if not now_page_range:
                    now_page_range = ''
                user_first_name = request.GET.get('user_first_name')
                if not user_first_name:
                    user_first_name = ''
                user_account = request.GET.get('user_account')
                if not user_account:
                    user_account = ''
                created_at_min = request.GET.get('created_at_min')
                if not created_at_min:
                    created_at_min = ''
                created_at_max = request.GET.get('created_at_max')
                if not created_at_max:
                    created_at_max = ''
                page_add += f'?page={now_page}&per_page_num={now_page_range}&user_first_name={user_first_name}' \
                            f'&user_account={user_account}&created_at_min={created_at_min}' \
                            f'&created_at_max={created_at_max}'
            else:
                page_add = reverse('staff_management', kwargs={'pub_id': pub_id})
                now_page = request.GET.get('page')
                if not now_page:
                    now_page = ''
                now_page_range = request.GET.get('per_page_num')
                if not now_page_range:
                    now_page_range = ''
                user_first_name = request.GET.get('user_first_name')
                if not user_first_name:
                    user_first_name = ''
                user_account = request.GET.get('user_account')
                if not user_account:
                    user_account = ''
                user_role = request.GET.get('user_role')
                if not user_role:
                    user_role = ''
                department_name = request.GET.get('department_name')
                if not department_name:
                    department_name = ''
                created_at_min = request.GET.get('created_at_min')
                if not created_at_min:
                    created_at_min = ''
                created_at_max = request.GET.get('created_at_max')
                if not created_at_max:
                    created_at_max = ''
                page_add += f'?page={now_page}&per_page_num={now_page_range}&user_first_name={user_first_name}' \
                            f'&user_account={user_account}&user_role={user_role}&department_name={department_name}' \
                            f'&created_at_min={created_at_min}&created_at_max={created_at_max}'
        if edit_flag == '1':
            staff.department_manage_enabled = True
            staff.save(update_fields=['department_manage_enabled', 'modified'])
            staff.refresh_from_db(fields=['department_manage_enabled'])
            if not staff.app_user.auth_user.role_set.filter(name=Role.MANAGEMENT).exists():
                staff.app_user.auth_user.role_set.add(Role.objects.get(name='Management'))
        else:
            staff.department_manage_enabled = False
            staff.save(update_fields=['department_manage_enabled', 'modified'])
            staff.refresh_from_db(fields=['department_manage_enabled'])
            if (staff.app_user.auth_user.role_set.filter(name=Role.MANAGEMENT).exists() and
                    not staff.app_user.usercompanytable_set.filter(
                        Q(department_manage_enabled=True) | Q(manage_enabled=True)).exists()):
                staff.app_user.auth_user.role_set.remove(Role.objects.get(name='Management'))
        return HttpResponseRedirect(page_add)


@login_required4
def get_company_place(request, pub_id):
    return_data = dict()
    per_page_num = request.GET.get('per_page_num')
    if not per_page_num:
        per_page_num = 10
    manage_role = request.session.get('manage_role')
    manage_id = request.session.get('manage_id')
    if manage_role == 'COMPANY':
        company = Company.objects.filter(pub_id=manage_id)
    else:
        return HttpResponseRedirect(reverse('company_index', kwargs={'pub_id': pub_id}))
    if not company.exists():
        return HttpResponseRedirect(reverse('backend_logout'))
    else:
        company = company.first()
        place_list = company.place_set.all().order_by('-id')
        return_data['place_name_list'] = [company.name for company in company.place_set.all()]
        place_name = request.GET.get('place_name')
        place_address = request.GET.get('place_address')

        if place_name:
            place_list = place_list.filter(name__icontains=place_name)

        if place_address:
            place_list = place_list.filter(address__icontains=place_address)
        return_data['user_length'] = len(place_list)
        page = request.GET.get('page')
        if not page:
            if request.session.get('check_place'):
                request.session.pop('check_place')
            if request.session.get('check_place_num'):
                request.session.pop('check_place_num')
        paginator = CachedPaginator(place_list, per_page_num)
        try:
            place_list = paginator.get_page(page)
            page_range = paginator.page_range_list(page)
        except InvalidPage:
            # page error - log
            # request.session['return_msg'] = _('System Error')
            return HttpResponseRedirect(reverse('company_index', kwargs={'pub_id': pub_id}))
        return_data['place_list'] = place_list
        return_data['page_range'] = page_range
        return render(request, 'backend/company_place_management.html', context=return_data)


@login_required4
def manager_place_verify(request, pub_id):
    # pub_id = request.POST.get('now_pub_id')
    back_page = reverse('company_place', kwargs={'pub_id': pub_id})
    verify_place_pub_id = request.POST.get('verify_place_pub_id')
    user_account = request.POST.get('user_account')
    place = Place.objects.filter(pub_id=verify_place_pub_id, company_verify=Place.NOT_VERIFY)
    if place.exists():
        place = place.first()
        verify_status = request.POST.get('verify_status')
        if verify_status == 'YES':
            place.company_verify = 1
            verify_place_name = request.POST.get('verify_place_name')
            if verify_place_name and place.name != verify_place_name:
                place.name = verify_place_name
            verify_place_address = request.POST.get('verify_place_address')
            if verify_place_address and place.location['location_address'] != verify_place_address:
                place.location['location_address'] = verify_place_address
            verify_place_phone = request.POST.get('verify_place_phone')
            if verify_place_phone and place.place_contact_phone != verify_place_phone:
                place.place_contact_phone = verify_place_phone
            ActionLog.objects.create(user_account=request.user, log_type='Place_Pass')
        else:
            place.company_verify = 2
            ActionLog.objects.create(user_account=request.user, log_type='Place_Not_Pass')
        place.save()

    now_page = request.POST.get('verify_now_page')
    if not now_page:
        now_page = ''
    now_page_range = request.POST.get('verify_now_page_range')
    if not now_page_range:
        now_page_range = ''
    place_name = request.POST.get('verify_search_place_name')
    if not place_name:
        place_name = ''
    place_address = request.POST.get('verify_search_place_address')
    if not place_address:
        place_address = ''
    company_name = request.POST.get('verify_search_company_name')
    if not company_name:
        company_name = ''
    back_page += f'?page={now_page}&place_name={place_name}&place_address={place_address}' \
                 f'&company_name={company_name}&per_page_num={now_page_range}'
    return HttpResponseRedirect(back_page)


@login_required4
def edit_company_place(request, pub_id, edit_type):
    back_page = reverse('company_place', kwargs={'pub_id': pub_id})
    company_id = request.session.get('manage_id')
    if edit_type == 'ADD':
        add_place_name = request.POST.get('add_place_name')
        add_place_address = request.POST.get('add_place_address')
        if add_place_name:
            if not Place.objects.filter(name=add_place_name).exists():
                CompanyServices.create_place(place_name=add_place_name, address=add_place_address,
                                             company_id=company_id)
            else:
                # TODO: 重複地點提示
                pass
    elif edit_type == 'EDIT':
        now_page = request.POST.get('edit_now_page')
        if not now_page:
            now_page = ''
        now_page_range = request.POST.get('edit_now_page_range')
        if not now_page_range:
            now_page_range = ''
        place_name = request.POST.get('edit_search_place_name')
        if not place_name:
            place_name = ''
        place_address = request.POST.get('edit_search_place_address')
        if not place_address:
            place_address = ''
        edit_place_id = request.POST.get('edit_place_id')
        edit_place_name = request.POST.get('edit_place_name')
        edit_place_address = request.POST.get('edit_place_address')
        edit_update_enabled = request.POST.get('edit_update_enabled')
        place = Place.objects.select_related('company').filter(pub_id=edit_place_id, company__pub_id=company_id)
        if place.exists():
            place = place.first()
            if not Place.objects.filter(company__pub_id=company_id, name=edit_place_name).exists():
                if edit_place_name != '':
                    place.name = edit_place_name
                place.save(update_fields=['name'])
            else:
                # TODO: 重複地點提示
                pass
            if edit_place_address:
                location_dict = place.location
                if type(location_dict) != dict:
                    location_dict = {'location_address': edit_place_address}
                else:
                    location_dict['location_address'] = edit_place_address
                place.location = location_dict
            if not edit_update_enabled:
                place.update_health_code = False
            else:
                place.update_health_code = True
            place.save(update_fields=['update_health_code', 'location'])
        back_page += f'?page={now_page}&place_name={place_name}&place_address={place_address}' \
                     f'&per_page_num={now_page_range}'
    elif edit_type == 'DEL':
        now_page = request.POST.get('del_now_page')
        if not now_page:
            now_page = ''
        now_page_range = request.POST.get('del_now_page_range')
        if not now_page_range:
            now_page_range = ''
        place_name = request.POST.get('del_search_place_name')
        if not place_name:
            place_name = ''
        place_address = request.POST.get('del_search_place_address')
        if not place_address:
            place_address = ''
        del_place_id = request.POST.get('del_place_id')
        place = Place.objects.select_related('company').filter(pub_id=del_place_id, company__pub_id=company_id)
        if place.exists():
            place.first().delete()
        back_page += f'?page={now_page}&place_name={place_name}&place_address={place_address}' \
                     f'&per_page_num={now_page_range}'
    return HttpResponseRedirect(back_page)


@login_required4
def department_management(request, pub_id):
    return_data = dict()
    manage_role = request.session.get('manage_role')
    manage_id = request.session.get('manage_id')
    if manage_role != 'COMPANY':
        return HttpResponseRedirect(reverse('company_index', kwargs={'pub_id': pub_id}))
    # per_page_num = request.GET.get('per_page_num')
    # if not per_page_num:
    #     per_page_num = 10
    department_list = Department.objects.filter(company__pub_id=manage_id).order_by('-modified')
    return_data['user_length'] = len(department_list)

    page = request.GET.get('page')
    paginator = CachedPaginator(department_list, 15)
    try:
        department_list = paginator.get_page(page)
        page_range = paginator.page_range_list(page)
    except InvalidPage:
        # page error - log
        # request.session['return_msg'] = _('System Error')
        return HttpResponseRedirect(reverse('company_index', kwargs={'pub_id': pub_id}))
    for department in department_list:
        department.staff_num = department.usercompanytable_set.filter(employed=True).count()
    return_data['company_id'] = pub_id
    return_data['department_list'] = department_list
    return_data['page_range'] = page_range
    return render(request, 'backend/department_management.html', context=return_data)


@login_required4
def department_detail(request, pub_id, department_id):
    return_data = dict()
    page = request.GET.get('page')
    department = Department.objects.filter(pub_id=department_id).order_by('-modified')
    if not department.exists():
        return HttpResponseRedirect(reverse('department_management', kwargs={'pub_id': pub_id}))
    else:
        department = department.first()
        app_user_list = department.usercompanytable_set.filter(employed=True)

        app_user_name_list = list()
        app_user_account_list = list()
        for app_user in app_user_list:
            if app_user.app_user.auth_user.first_name not in app_user_name_list:
                app_user_name_list.append(app_user.app_user.auth_user.first_name)
            app_user_account_list.append(app_user.app_user.auth_user.username)
        return_data['app_user_name_list'] = app_user_name_list
        return_data['app_user_account_list'] = app_user_account_list

        user_first_name = request.GET.get('user_first_name')
        user_account = request.GET.get('user_account')
        created_at_min = request.GET.get('created_at_min')
        created_at_max = request.GET.get('created_at_max')

        if user_first_name:
            app_user_list = app_user_list.filter(app_user__auth_user__first_name=user_first_name)

        if user_account:
            app_user_list = app_user_list.filter(app_user__auth_user__username=user_account)

        if created_at_min:
            try:
                create_at_min = datetime.strptime(created_at_min, '%Y-%m-%d %H:%M')
            except (TypeError, ValueError) as e:
                pass
            else:
                app_user_list = app_user_list.filter(created__gte=timezone.make_aware(create_at_min))

        if created_at_max:
            try:
                # Plus one day to cover whole day. Ex: 2018-10-10T00:00:00 -> 2018-10-11T00:00:00
                # and then we use less than expression to query
                create_at_max = datetime.strptime(created_at_max, '%Y-%m-%d %H:%M') + timedelta(days=1)
            except (TypeError, ValueError) as e:
                pass
            else:
                app_user_list = app_user_list.filter(created__lt=timezone.make_aware(create_at_max))

        paginator = CachedPaginator(app_user_list, 15)
        try:
            app_user_list = paginator.get_page(page)
            page_range = paginator.page_range_list(page)
        except InvalidPage:
            # page error - log
            # request.session['return_msg'] = _('System Error')
            return HttpResponseRedirect(reverse('company_index', kwargs={'pub_id': pub_id}))
        return_data['department_id'] = department_id
        return_data['department_name'] = department.name
        return_data['app_user_list'] = app_user_list
        return_data['page_range'] = page_range
        return render(request, 'backend/department_detail.html', context=return_data)


@login_required4
def company_del_staff(request, pub_id, del_page):
    now_page = request.POST.get('del_now_page')
    staff_id = request.POST.get('del_staff_id')
    company_id = request.session.get('manage_id')
    department_id = request.POST.get('department_id')
    if staff_id:
        if del_page != 'DEP_STAFF':
            user_company = UserCompanyTable.objects.filter(pub_id=staff_id)
            if user_company.exists():
                user_company = user_company.first()
                user_company_list = UserCompanyTable.objects.filter(
                    app_user=user_company.app_user, company__pub_id=company_id)
                for staff_detail in user_company_list:
                    staff_detail.employed = False
                    staff_detail.default_show = False
                    staff_detail.save()
                not_yet_default_set = user_company.app_user.usercompanytable_set.filter(employed=True)
                if not_yet_default_set.exists():
                    not_yet_default = not_yet_default_set.first()
                    not_yet_default.default_show = True
                    not_yet_default.save()
        else:
            user_company = UserCompanyTable.objects.filter(pub_id=staff_id)
            if user_company.exists():
                user_company = user_company.first()
                user_company.employed = False
                user_company.default_show = False
                user_company.save()
                not_yet_default_set = user_company.app_user.usercompanytable_set.filter(employed=True)
                if not_yet_default_set.exists():
                    not_yet_default = not_yet_default_set.first()
                    not_yet_default.default_show = True
                    not_yet_default.save()
        if del_page == 'DEP_STAFF' and department_id:
            return HttpResponseRedirect(
                reverse('department_detail', kwargs={'pub_id': pub_id, 'department_id': department_id}))
        else:
            return HttpResponseRedirect(reverse('staff_management', kwargs={'pub_id': pub_id}) + f'?page={now_page}')
    else:
        return HttpResponseRedirect(reverse('company_index', kwargs={'pub_id': pub_id}))


@login_required4
def company_tract_old(request, pub_id):
    return_data = dict()
    per_page_num = request.GET.get('per_page_num')
    if not per_page_num:
        per_page_num = 10
    approach_list = ApproachRecord.objects.filter(
        Q(app_user__usercompanytable__company__pub_id=pub_id) |
        Q(scan_user__usercompanytable__company__pub_id=pub_id)).order_by('-created')
    place_entry_list = PlaceEntryRecord.objects.filter(place_entry__company__pub_id=pub_id).order_by('-created')

    user_first_name = request.GET.get('user_first_name')
    user_account = request.GET.get('user_account')
    place_name = request.GET.get('place_name')
    created_at_min = request.GET.get('created_at_min')
    created_at_max = request.GET.get('created_at_max')

    search_list = ApproachRecord.objects.none()
    search_type = None

    if user_first_name:
        search_type = 'USER'
        search_list = approach_list.filter(
            Q(app_user__auth_user__first_name=user_first_name) | Q(scan_user__auth_user__first_name=user_first_name))

    if user_account:
        search_type = 'USER'
        search_list = approach_list.filter(
            Q(app_user__auth_user__username=user_account) | Q(scan_user__auth_user__username=user_account))

    if place_name:
        search_type = 'PLACE'
        search_list = place_entry_list.filter(place_entry__name=place_name)

    if created_at_min and search_type:
        try:
            create_at_min = datetime.strptime(created_at_min, '%Y-%m-%d %H:%M')
        except (TypeError, ValueError) as e:
            pass
        else:
            search_list = search_list.filter(created__gte=timezone.make_aware(create_at_min))

    if created_at_max and search_type:
        try:
            # Plus one day to cover whole day. Ex: 2018-10-10T00:00:00 -> 2018-10-11T00:00:00
            # and then we use less than expression to query
            create_at_max = datetime.strptime(created_at_max, '%Y-%m-%d %H:%M') + timedelta(days=1)
        except (TypeError, ValueError) as e:
            pass
        else:
            search_list = search_list.filter(created__lt=timezone.make_aware(create_at_max))
    search_list_result = list()
    if search_type:
        if search_type == 'USER':
            for search in search_list:
                if search.app_user.auth_user.first_name == user_first_name:
                    approach_user = search.scan_user
                else:
                    approach_user = search.app_user
                user_company = approach_user.usercompanytable_set.select_related(
                    'company', 'department').filter(company__pub_id=pub_id)
                if not user_company.exists():
                    user_company = approach_user.usercompanytable_set.select_related(
                        'company', 'department').filter(default_show=True)
                    if not user_company.exists():
                        company_name = ''
                        department_name = ''
                        staff_pub_id = ''
                    else:
                        company_name = user_company.first().company.name
                        department_name = user_company.first().department.name
                        staff_pub_id = ''
                else:
                    user_company_info = user_company.first()
                    company_name = user_company_info.company.name
                    department_name = user_company_info.department.name
                    staff_pub_id = user_company_info.pub_id
                search_list_result.append((
                    search.created,
                    approach_user.auth_user.first_name,
                    company_name,
                    department_name,
                    search.app_user.auth_user.username,
                    staff_pub_id
                ))
        else:
            for search in search_list:
                user_company = search.app_user.usercompanytable_set.select_related(
                    'company', 'department').filter(company__pub_id=pub_id)
                if not user_company.exists():
                    user_company = search.app_user.usercompanytable_set.select_related(
                        'company', 'department').filter(default_show=True)
                    if not user_company.exists():
                        company_name = ''
                        department_name = ''
                        staff_pub_id = ''
                    else:
                        company_name = user_company.first().company.name
                        department_name = user_company.first().department.name
                        staff_pub_id = ''
                else:
                    user_company_info = user_company.first()
                    staff_pub_id = user_company_info.pub_id
                    company_name = user_company_info.company.name
                    department_name = user_company_info.department.name
                search_list_result.append((
                    search.created,
                    search.app_user.auth_user.first_name,
                    company_name,
                    department_name,
                    search.app_user.auth_user.username,
                    staff_pub_id
                ))
        return_data['user_length'] = len(search_list_result)

    page = request.GET.get('page')
    paginator = CachedPaginator(search_list_result, per_page_num)
    try:
        search_list_result = paginator.get_page(page)
        page_range = paginator.page_range_list(page)
    except InvalidPage:
        # page error - log
        # request.session['return_msg'] = _('System Error')
        return HttpResponseRedirect(reverse('company_index', kwargs={'pub_id': pub_id}))
    app_user_list = UserCompanyTable.objects.select_related(
        'app_user').filter(company__pub_id=pub_id).distinct('app_user')
    app_user_name_list = list()
    app_user_account_list = list()
    for app_user in app_user_list:
        if app_user.app_user.auth_user.first_name not in app_user_name_list:
            app_user_name_list.append(app_user.app_user.auth_user.first_name)
        app_user_account_list.append(app_user.app_user.auth_user.username)
    return_data['app_user_name_list'] = app_user_name_list
    return_data['app_user_account_list'] = app_user_account_list
    return_data['search_list_result'] = search_list_result
    return_data['page_range'] = page_range
    return_data['place_list'] = Place.objects.filter(company__pub_id=pub_id)

    return render(request, 'backend/approach_track.html', context=return_data)


@login_required4
def company_tract(request, pub_id):
    return_data = dict()
    per_page_num = request.GET.get('per_page_num')
    if not per_page_num:
        per_page_num = 10

    manage_role = request.session.get('manage_role')
    manage_id = request.session.get('manage_id')
    if manage_role == 'COMPANY':
        approach_list = ApproachRecord.objects.filter(
            Q(app_user__usercompanytable__company__pub_id=manage_id) |
            Q(scan_user__usercompanytable__company__pub_id=manage_id)).order_by('-created')
    else:
        approach_list = ApproachRecord.objects.filter(
            Q(app_user__usercompanytable__department__pub_id=manage_id) |
            Q(scan_user__usercompanytable__department__pub_id=manage_id)).order_by('-created')

    user_first_name = request.GET.get('user_first_name')
    user_account = request.GET.get('user_account')
    created_at_min = request.GET.get('created_at_min')
    created_at_max = request.GET.get('created_at_max')

    approach_record_list = ApproachRecord.objects.none()

    if user_first_name:
        approach_record_list = approach_list.filter(
            Q(app_user__auth_user__first_name=user_first_name) | Q(scan_user__auth_user__first_name=user_first_name))

    if user_account:
        approach_record_list = approach_list.filter(
            Q(app_user__auth_user__username=user_account) | Q(scan_user__auth_user__username=user_account))

    if created_at_min:
        try:
            create_at_min = datetime.strptime(created_at_min, '%Y-%m-%d %H:%M')
        except (TypeError, ValueError) as e:
            pass
        else:
            approach_record_list = approach_record_list.filter(created__gte=timezone.make_aware(create_at_min))

    if created_at_max:
        try:
            # Plus one day to cover whole day. Ex: 2018-10-10T00:00:00 -> 2018-10-11T00:00:00
            # and then we use less than expression to query
            create_at_max = datetime.strptime(created_at_max, '%Y-%m-%d %H:%M') + timedelta(days=1)
        except (TypeError, ValueError) as e:
            pass
        else:
            approach_record_list = approach_record_list.filter(created__lt=timezone.make_aware(create_at_max))

    page = request.GET.get('page')
    paginator = CachedPaginator(approach_record_list, per_page_num)
    try:
        approach_record_list = paginator.get_page(page)
        page_range = paginator.page_range_list(page)
    except InvalidPage:
        # page error - log
        # request.session['return_msg'] = _('System Error')
        return HttpResponseRedirect(reverse('company_index', kwargs={'pub_id': pub_id}))
    for record in approach_record_list:
        if user_first_name:
            if record.app_user.auth_user.first_name == user_first_name:
                record.approach_user = record.scan_user
            else:
                record.approach_user = record.app_user
        if user_account:
            if record.app_user.auth_user.username == user_account:
                record.approach_user = record.scan_user
            else:
                record.approach_user = record.app_user
        user_company = record.approach_user.usercompanytable_set.select_related(
            'company', 'department').filter(default_show=True, employed=True)
        if not user_company.exists():
            company_name = ''
            department_name = ''
            record.staff_id = ''
        else:
            user_company_info = user_company.first()
            company_name = user_company_info.company.name
            department_name = user_company_info.department.name
            if manage_role == 'COMPANY':
                if user_company_info.company.pub_id == manage_id:
                    record.staff_id = user_company_info.pub_id
            else:
                if user_company_info.department.pub_id == manage_id:
                    record.staff_id = user_company_info.pub_id
        record.create_time = utc_time_to_local_time(record.created)
        record.company_name = company_name
        record.department_name = department_name
    if manage_role == 'COMPANY':
        app_user_list = UserCompanyTable.objects.select_related(
            'app_user').filter(company__pub_id=manage_id, employed=True).distinct('app_user')
    else:
        app_user_list = UserCompanyTable.objects.select_related(
            'app_user').filter(department__pub_id=manage_id, employed=True).distinct('app_user')
    app_user_name_list = list()
    app_user_account_list = list()
    for app_user in app_user_list:
        if app_user.app_user.auth_user.first_name not in app_user_name_list:
            app_user_name_list.append(app_user.app_user.auth_user.first_name)
        app_user_account_list.append(app_user.app_user.auth_user.username)
    return_data['app_user_name_list'] = app_user_name_list
    return_data['app_user_account_list'] = app_user_account_list
    return_data['approach_record_list'] = approach_record_list
    return_data['page_range'] = page_range

    return render(request, 'backend/approach_track.html', context=return_data)


@login_required4
def company_place_tract(request, pub_id):
    return_data = dict()
    per_page_num = request.GET.get('per_page_num')
    if not per_page_num:
        per_page_num = 10
    manage_role = request.session.get('manage_role')
    manage_id = request.session.get('manage_id')
    if manage_role == 'COMPANY':
        place_entry_list = PlaceEntryRecord.objects.filter(place_entry__company__pub_id=manage_id).order_by('-created')
    else:
        # place_entry_list = PlaceEntryRecord.objects.filter(
        #     place_entry__company__department__pub_id=manage_id,
        #     app_user__usercompanytable__department__pub_id=manage_id).order_by('-created')
        return HttpResponseRedirect(reverse('company_index', kwargs={'pub_id': pub_id}))

    place_name = request.GET.get('place_name')
    created_at_min = request.GET.get('created_at_min')
    created_at_max = request.GET.get('created_at_max')

    if place_name:
        request.session['place_name'] = place_name
        place_entry_list = place_entry_list.filter(place_entry__name=place_name)
    else:
        request.session['place_name'] = ''
    if created_at_min:
        request.session['created_at_min'] = created_at_min
        try:
            create_at_min = datetime.strptime(created_at_min, '%Y-%m-%d %H:%M')
        except (TypeError, ValueError) as e:
            pass
        else:
            place_entry_list = place_entry_list.filter(created__gte=timezone.make_aware(create_at_min))
    else:
        request.session['created_at_min'] = ''

    if created_at_max:
        request.session['created_at_max'] = created_at_max
        try:
            # Plus one day to cover whole day. Ex: 2018-10-10T00:00:00 -> 2018-10-11T00:00:00
            # and then we use less than expression to query
            create_at_max = datetime.strptime(created_at_max, '%Y-%m-%d %H:%M') + timedelta(days=1)
        except (TypeError, ValueError) as e:
            pass
        else:
            place_entry_list = place_entry_list.filter(created__lt=timezone.make_aware(create_at_max))
    else:
        request.session['created_at_max'] = ''
    return_data['user_length'] = len(place_entry_list)
    page = request.GET.get('page')
    paginator = CachedPaginator(place_entry_list, per_page_num)
    try:
        place_entry_list = paginator.get_page(page)
        page_range = paginator.page_range_list(page)
    except InvalidPage:
        # page error - log
        # request.session['return_msg'] = _('System Error')
        return HttpResponseRedirect(reverse('company_index', kwargs={'pub_id': pub_id}))
    for record in place_entry_list:
        user_company = record.app_user.usercompanytable_set.select_related(
            'company', 'department').filter(default_show=True)
        if not user_company.exists():
            company_name = ''
            department_name = ''
            record.staff_id = ''
        else:
            user_company_info = user_company.first()
            if user_company_info.company.pub_id != manage_id:
                record.staff_id = ''
            else:
                record.staff_id = user_company_info.pub_id
            company_name = user_company_info.company.name
            if user_company_info.department:
                department_name = user_company_info.department.name
                if user_company_info.company.pub_id == manage_id:
                    record.department_link = user_company_info.department.pub_id
            else:
                department_name = ''
                record.department_link = ''
        record.create_time = utc_time_to_local_time(record.created)
        record.company_name = company_name
        record.department_name = department_name
    return_data['place_entry_list'] = place_entry_list
    return_data['page_range'] = page_range
    return_data['place_list'] = Place.objects.filter(company__pub_id=manage_id)
    return render(request, 'backend/company_place_track.html', context=return_data)


@login_required4
def company_place_tract_export(request, pub_id):
    return_data = dict()
    place_name = request.session.get('place_name')
    created_at_min = request.session.get('created_at_min')
    created_at_max = request.session.get('created_at_max')

    manage_role = request.session.get('manage_role')
    manage_id = request.session.get('manage_id')
    if manage_role == 'COMPANY':
        place_entry_list = PlaceEntryRecord.objects.filter(place_entry__company__pub_id=manage_id).order_by('-created')
    else:
        # place_entry_list = PlaceEntryRecord.objects.filter(
        #     place_entry__company__department__pub_id=manage_id,
        #     app_user__usercompanytable__department__pub_id=manage_id).order_by('-created')
        return HttpResponseRedirect(reverse('company_index', kwargs={'pub_id': pub_id}))
    if place_name:
        place_entry_list = place_entry_list.filter(place_entry__name=place_name)

    if created_at_min:
        try:
            create_at_min = datetime.strptime(created_at_min, '%Y-%m-%d %H:%M')
        except (TypeError, ValueError) as e:
            pass
        else:
            place_entry_list = place_entry_list.filter(created__gte=timezone.make_aware(create_at_min))

    if created_at_max:
        try:
            # Plus one day to cover whole day. Ex: 2018-10-10T00:00:00 -> 2018-10-11T00:00:00
            # and then we use less than expression to query
            create_at_max = datetime.strptime(created_at_max, '%Y-%m-%d %H:%M') + timedelta(days=1)
        except (TypeError, ValueError) as e:
            pass
        else:
            place_entry_list = place_entry_list.filter(created__lt=timezone.make_aware(create_at_max))

    response = HttpResponse(content_type='application/ms-excel')
    response['Content-Disposition'] = ('attachment; filename="%s.xls"' %
                                       'Place_tract_list')

    wb = xlwt.Workbook(encoding='utf-8')
    ws = wb.add_sheet('Place tract list')

    pattern = xlwt.Pattern()
    pattern.pattern = xlwt.Pattern.SOLID_PATTERN
    pattern.pattern_fore_colour = xlwt.Style.colour_map['ocean_blue']

    pattern2 = xlwt.Pattern()
    pattern2.pattern = xlwt.Pattern.SOLID_PATTERN
    pattern2.pattern_fore_colour = xlwt.Style.colour_map['white']

    font = xlwt.Font()
    font.colour_index = xlwt.Style.colour_map['white']

    borders = xlwt.Borders()
    borders.top = 2
    borders.top_colour = xlwt.Style.colour_map['dark_blue']
    borders.left = 2
    borders.left_colour = xlwt.Style.colour_map['dark_blue']
    borders.bottom = 2
    borders.bottom_colour = xlwt.Style.colour_map['dark_blue']
    borders.right = 2
    borders.right_colour = xlwt.Style.colour_map['dark_blue']

    borders2 = xlwt.Borders()
    borders2.top = 1
    borders2.left = 1
    borders2.bottom = 1
    borders2.right = 1

    style = xlwt.XFStyle()
    style.font = font
    style.pattern = pattern
    style.borders = borders

    ws.write(0, 0, str('日期'), style)
    ws.write(0, 1, str('地點'), style)
    ws.write(0, 2, str('使用者名稱'), style)
    ws.write(0, 3, str('使用者帳號'), style)
    ws.write(0, 4, str('公司/學校'), style)
    ws.write(0, 5, str('部門'), style)

    style2 = xlwt.XFStyle()
    style2.pattern = pattern2
    style2.borders = borders2

    i = 1
    for record in place_entry_list:
        ws.write(i, 0, str(utc_time_to_local_time(record.created).strftime('%Y-%m-%d %H:%M:%S')), style2)
        ws.write(i, 1, str(record.place_entry.name), style2)
        record_app_user = record.app_user
        ws.write(i, 2, str(record_app_user.auth_user.first_name), style2)
        ws.write(i, 3, str(record_app_user.auth_user.username), style2)
        user_company = record_app_user.usercompanytable_set.select_related(
            'company', 'department').filter(default_show=True)
        if not user_company.exists():
            company_name = ''
            department_name = ''
        else:
            user_company_info = user_company.first()
            company_name = user_company_info.company.name
            if user_company_info.department:
                department_name = user_company_info.department.name
            else:
                department_name = ''
        ws.write(i, 4, str(company_name), style2)
        ws.write(i, 5, str(department_name), style2)
        i += 1
    wb.save(response)

    return response


@login_required4
def company_audit_add_req(request, pub_id):
    return_data = dict()
    manage_role = request.session.get('manage_role')
    manage_id = request.session.get('manage_id')
    if manage_role == 'COMPANY':
        add_req_list = AddRequest.objects.select_related(
            'add_tag', 'add_tag__company', 'add_user', 'agree_user').filter(
            add_tag__company__pub_id=manage_id).order_by('-modified')
    else:
        return HttpResponseRedirect(reverse('company_index', kwargs={'pub_id': pub_id}))

    app_user_name_list = list()
    app_user_account_list = list()
    for add_req in add_req_list:
        if add_req.add_user.auth_user.first_name not in app_user_name_list:
            app_user_name_list.append(add_req.add_user.auth_user.first_name)
        if add_req.add_user.auth_user.username not in app_user_account_list:
            app_user_account_list.append(add_req.add_user.auth_user.username)
    return_data['app_user_name_list'] = app_user_name_list
    return_data['app_user_account_list'] = app_user_account_list

    user_first_name = request.GET.get('user_first_name')
    user_account = request.GET.get('user_account')

    if user_first_name:
        add_req_list = add_req_list.filter(add_user__auth_user__first_name=user_first_name)

    if user_account:
        add_req_list = add_req_list.filter(add_user__auth_user__first_name=user_first_name)

    return_data['user_length'] = len(add_req_list)
    page = request.GET.get('page')
    paginator = CachedPaginator(add_req_list, 15)
    try:
        add_req_list = paginator.get_page(page)
        page_range = paginator.page_range_list(page)
    except InvalidPage:
        # page error - log
        # request.session['return_msg'] = _('System Error')
        logger_writer('SYSTEM', 'error', 'COMPANY AUDIT ADD REQ', f'System error: redirect to backend index')
        return HttpResponseRedirect(reverse('backend_index'))
    for add_req in add_req_list:
        add_req.create_time = utc_time_to_local_time(add_req.modified)
        if 'cancel_user' in add_req.note:
            if add_req.note['cancel_user'] == 'ADMIN':
                add_req.update_user_name = _('Administrator')
                add_req.update_user_id = 'ADMIN'
            elif add_req.note['cancel_user'] == 'SELF':
                add_req.update_user_name = add_req.agree_user.auth_user.first_name
                add_req.update_user_id = add_req.agree_user.pub_id
        else:
            if add_req.agree_user:
                add_req.update_user_name = add_req.agree_user.auth_user.first_name
                add_req.update_user_id = add_req.agree_user.pub_id
                user_company = add_req.agree_user.usercompanytable_set.filter(company__pub_id=manage_id, employed=True)
                if user_company.exists():
                    add_req.update_user_id = user_company.first().pub_id
                    add_req.user_link = True
    return_data['department_list'] = Department.objects.filter(company__pub_id=manage_id)
    return_data['add_req_list'] = add_req_list
    return_data['page_range'] = page_range
    return render(request, 'backend/company_add_req.html', context=return_data)


@login_required4
def place_qrcode_print_setting(request, pub_id):
    return_data = dict()
    company_default = CompanyDefaultPrint.objects.filter(company__pub_id=pub_id)
    if company_default.exists():
        company_default = company_default.first()

        if request.method == 'POST':
            fst_line = request.POST.get('fst_line')
            sec_line = request.POST.get('sec_line')
            thd_line = request.POST.get('thd_line')
            forth_line = request.POST.get('forth_line')
            last_line = request.POST.get('last_line')
            print_dict = dict()
            if fst_line:
                print_dict['fst_line'] = fst_line
            if sec_line:
                print_dict['sec_line'] = sec_line
            if thd_line:
                print_dict['thd_line'] = thd_line
            if forth_line:
                print_dict['forth_line'] = forth_line
            if last_line:
                print_dict['last_line'] = last_line
            company_default.place_code = print_dict
            company_default.save()
        print_dict = company_default.place_code
        if 'fst_line' in print_dict:
            return_data['fst_line'] = print_dict['fst_line']
        if 'sec_line' in print_dict:
            return_data['sec_line'] = print_dict['sec_line']
        if 'thd_line' in print_dict:
            return_data['thd_line'] = print_dict['thd_line']
        if 'forth_line' in print_dict:
            return_data['forth_line'] = print_dict['forth_line']
        if 'last_line' in print_dict:
            return_data['last_line'] = print_dict['last_line']

    return render(request, 'backend/place_qrcode_print_setting.html', context=return_data)


@login_required4
def update_add_request(request, update_type):
    req_id = request.POST.get('req_id')
    company_id = request.POST.get('company_id')
    department_id = request.POST.get('department_id')
    title_id = request.POST.get('title_id')
    if company_id and update_type:
        add_req = AddRequest.objects.select_related('add_user').filter(
            pub_id=req_id, add_tag__company__pub_id=company_id, status=AddRequest.WAIT_AUDIT)
        if add_req.exists():
            add_req = add_req.first()
            if update_type == 'AGREE' and department_id:
                # 檢查有沒有在此公司內
                check_user = UserCompanyTable.objects.filter(app_user=add_req.add_user, company=add_req.add_tag.company)
                if check_user.exists():
                    check_user = check_user.first()
                    # 檢查和所要設定部門是否相同
                    if check_user.department.pub_id == department_id:
                        check_user.employed = True
                        # 檢查是否沒有預設，沒有就將此員工標記設為預設
                        if not check_user.app_user.usercompanytable_set.filter(
                                employed=True, default_show=True).exclude(pub_id=check_user.pub_id).exists():
                            check_user.default_show = True
                        check_user.save()
                        UserCompanyHistory.objects.create(user_company_table=check_user,
                                                          start_time=local_time_to_utc_time(datetime.now()))
                        add_req.status = AddRequest.AGREE
                        if request.user_role == 'ADMIN':
                            add_req.note = {'cancel_user': 'ADMIN'}
                        elif request.user_role == 'MANAGEMENT':
                            add_req.agree_user = request.user.appuser
                        add_req.save()
                        request.session['return_msg'] = _('Update Success')
                    else:
                        # 沒有所要設定支部門則新員工標記
                        try:
                            AttendanceStatus.objects.create(company=add_req.add_tag.company, app_user=add_req.add_user)
                            user_company = UserCompanyTable.objects.create(
                                app_user=add_req.add_user, company=add_req.add_tag.company)
                            UserCompanyHistory.objects.create(user_company_table=user_company,
                                                              start_time=user_company.created)
                        except Exception as e:
                            # TODO: log
                            request.session['return_msg'] = _('Update failed')
                            logger_writer('SYSTEM', 'info', 'UPDATE ADD REQUEST', f'Update Failed')
                        else:
                            try:
                                if department_id:
                                    user_company.department = Department.objects.get(pub_id=department_id)
                                if title_id:
                                    user_company.title = Title.objects.get(pub_id=title_id)
                                # 檢查是否沒有預設，沒有就將此員工標記設為預設
                                if not add_req.add_user.usercompanytable_set.filter(
                                        employed=True, default_show=True).exclude(pub_id=user_company.pub_id).exists():
                                    user_company.default_show = True
                                user_company.save()
                            except Exception as e:
                                pass
                            add_req.status = AddRequest.AGREE
                            if request.user_role == 'ADMIN':
                                add_req.note = {'cancel_user': 'ADMIN'}
                            elif request.user_role == 'MANAGEMENT':
                                add_req.agree_user = request.user.appuser
                            add_req.save()
                            request.session['return_msg'] = _('Update Success')
                else:
                    # 不在此公司內，新增員工標記
                    try:
                        AttendanceStatus.objects.create(company=add_req.add_tag.company, app_user=add_req.add_user)
                        user_company = UserCompanyTable.objects.create(
                            app_user=add_req.add_user, company=add_req.add_tag.company)
                        UserCompanyHistory.objects.create(user_company_table=user_company,
                                                          start_time=user_company.created)
                    except Exception as e:
                        # TODO: log
                        request.session['return_msg'] = _('Update failed')
                        logger_writer('SYSTEM', 'info', 'UPDATE ADD REQUEST', f'Update Failed')
                    else:
                        try:
                            if department_id:
                                user_company.department = Department.objects.get(pub_id=department_id)
                            if title_id:
                                user_company.title = Title.objects.get(pub_id=title_id)
                            # 檢查是否沒有預設，沒有就將此員工標記設為預設
                            if not add_req.add_user.usercompanytable_set.filter(
                                    default_show=True).exclude(pub_id=user_company.pub_id).exists():
                                user_company.default_show = True
                            user_company.save()
                        except Exception as e:
                            pass
                        add_req.status = AddRequest.AGREE
                        if request.user_role == 'ADMIN':
                            add_req.note = {'cancel_user': 'ADMIN'}
                        elif request.user_role == 'MANAGEMENT':
                            add_req.agree_user = request.user.appuser
                        add_req.save()
                        request.session['return_msg'] = _('Update Success')
                ActionLog.objects.create(user_account=request.user, log_type='Company_Pass')
                logger_writer('SYSTEM', 'info', 'UPDATE ADD REQUEST', f'Update Success: Company Pass')
            else:
                if request.user_role == 'ADMIN':
                    add_req.note = {'cancel_user': 'ADMIN'}
                elif request.user_role == 'MANAGEMENT':
                    add_req.agree_user = request.user.appuser
                add_req.status = AddRequest.CANCEL
                add_req.save()
                request.session['return_msg'] = _('Update Success')
                logger_writer('SYSTEM', 'info', 'UPDATE ADD REQUEST', f'Update Success: Company Not Pass')
                ActionLog.objects.create(user_account=request.user, log_type='Compnay_Not_Pass')
    request.session['nav_no_reset'] = 1
    request.session['page2'] = request.POST.get('page2')
    return HttpResponseRedirect(reverse('company_detail', kwargs={'pub_id': company_id}))


@login_required4
def company_update_add_request(request, pub_id, update_type):
    req_id = request.POST.get('req_id')
    department_id = request.POST.get('department_id')
    title_id = request.POST.get('title_id')
    manage_role = request.session.get('manage_role')
    manage_id = request.session.get('manage_id')
    if manage_role != 'COMPANY':
        return HttpResponseRedirect(reverse('company_index', kwargs={'pub_id': pub_id}))
    if update_type:
        add_req = AddRequest.objects.select_related('add_user').filter(
            pub_id=req_id, add_tag__company__pub_id=manage_id, status=AddRequest.WAIT_AUDIT)
        if add_req.exists():
            add_req = add_req.first()
            if update_type == 'AGREE':
                if not department_id:
                    request.session['return_msg'] = _('Field missing')
                    return HttpResponseRedirect(reverse('audit_add_req', kwargs={'pub_id': pub_id}))
                check_user = UserCompanyTable.objects.filter(app_user=add_req.add_user, company=add_req.add_tag.company)
                if check_user.exists():
                    check_user = check_user.first()
                    if check_user.department.pub_id == department_id:
                        check_user.employed = True
                        if not check_user.app_user.usercompanytable_set.filter(
                                employed=True, default_show=True).exclude(pub_id=check_user.pub_id).exists():
                            check_user.default_show = True
                        check_user.save()
                        add_req.status = AddRequest.AGREE
                        if request.user_role == 'ADMIN':
                            add_req.note = {'cancel_user': 'ADMIN'}
                        elif request.user_role == 'MANAGEMENT':
                            add_req.agree_user = request.user.appuser
                        add_req.save()
                        request.session['return_msg'] = _('Update Success')
                        logger_writer('SYSTEM', 'info', 'COMPANY UPDATE ADD REQUEST', f'Update Success')
                    else:
                        try:
                            AttendanceStatus.objects.create(company=add_req.add_tag.company, app_user=add_req.add_user)
                            user_company = UserCompanyTable.objects.create(
                                app_user=add_req.add_user, company=add_req.add_tag.company)
                        except Exception as e:
                            # TODO: log
                            request.session['return_msg'] = _('Update failed')
                            logger_writer('SYSTEM', 'info', 'COMPANY UPDATE ADD REQUEST', f'Update Failed')
                        else:
                            try:
                                if department_id:
                                    user_company.department = Department.objects.get(pub_id=department_id)
                                if title_id:
                                    user_company.title = Title.objects.get(pub_id=title_id)
                                if not add_req.add_user.usercompanytable_set.filter(
                                        employed=True, default_show=True).exclude(pub_id=user_company.pub_id).exists():
                                    user_company.default_show = True
                                user_company.save()
                            except Exception as e:
                                pass
                            add_req.status = AddRequest.AGREE
                            if request.user_role == 'ADMIN':
                                add_req.note = {'cancel_user': 'ADMIN'}
                            elif request.user_role == 'MANAGEMENT':
                                add_req.agree_user = request.user.appuser
                            add_req.save()
                            request.session['return_msg'] = _('Update Success')
                            logger_writer('SYSTEM', 'info', 'COMPANY UPDATE ADD REQUEST', f'Update Success')
                else:
                    try:
                        AttendanceStatus.objects.create(company=add_req.add_tag.company, app_user=add_req.add_user)
                        user_company = UserCompanyTable.objects.create(
                            app_user=add_req.add_user, company=add_req.add_tag.company)
                    except Exception as e:
                        # TODO: log
                        request.session['return_msg'] = _('Update failed')
                        logger_writer('SYSTEM', 'info', 'COMPANY UPDATE ADD REQUEST', f'Update Failed')
                    else:
                        try:
                            if department_id:
                                user_company.department = Department.objects.get(pub_id=department_id)
                            if title_id:
                                user_company.title = Title.objects.get(pub_id=title_id)
                            if not add_req.add_user.usercompanytable_set.filter(
                                    employed=True, default_show=True).exclude(pub_id=user_company.pub_id).exists():
                                user_company.default_show = True
                            user_company.save()
                        except Exception as e:
                            pass
                        add_req.status = AddRequest.AGREE
                        if request.user_role == 'ADMIN':
                            add_req.note = {'cancel_user': 'ADMIN'}
                        elif request.user_role == 'MANAGEMENT':
                            add_req.agree_user = request.user.appuser
                        add_req.save()
                        request.session['return_msg'] = _('Update Success')
                        logger_writer('SYSTEM', 'info', 'COMPANY UPDATE ADD REQUEST', f'Update Success')
            else:
                if request.user_role == 'ADMIN':
                    add_req.note = {'cancel_user': 'ADMIN'}
                elif request.user_role == 'MANAGEMENT':
                    add_req.agree_user = request.user.appuser
                add_req.status = AddRequest.CANCEL
                add_req.save()
                request.session['return_msg'] = _('Update Success')
                logger_writer('SYSTEM', 'info', 'COMPANY UPDATE ADD REQUEST', f'Update Success')

    return HttpResponseRedirect(reverse('audit_add_req', kwargs={'pub_id': pub_id}))
