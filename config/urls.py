from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import path, include
from rest_framework import routers
# 前台
from maipassport.citadel.views import (app_login, app_logout, app_index, get_health_question_html, show_qr_code,
                                       get_health_code, get_announcement, scan_post, sel_scan, user_work_status,
                                       scan_user_work_status, user_health_status, user_approach_status,
                                       user_visitor_status, user_place_entry, get_history, user_profile, privacy_file,
                                       app_sign_up, app_sign_up_otc, forget_pass, reset_pass, chick_in_record,
                                       app_login_new, message_html, scan_test, enc_message, first_time_login,
                                       first_time_set_pwd, upload_user_img, user_add_company, edit_password_otp,
                                       edit_password, shop_qrcode, shop_qrcode_cancel, shop_qrcode_edit,
                                       user_create_open,
                                       description, health_check, upload_health_img,
                                       )
from maipassport.records.view import *
# 後台
from maipassport.citadel.views import (backend_login, backend_logout, user_verify, backend_reset_pwd,
                                       backend_index, user_management, get_user_detail,
                                       edit_user_manage_enable, place_management, edit_place, company_management,
                                       get_company_detail, verify_set_pwd, user_tract_old,  place_tract, user_tract,
                                       print_view, update_check_session, place_qrcode_print_setting,
                                       update_add_request, no_company_detail, del_staff, web_creat_company,
                                       web_creat_department, web_del_department, new_company_apply_req,
                                       update_new_company_apply_req, place_verify, place_create_open,
                                       place_checkin_open,

                                       backend_company_index, staff_management, get_staff_detail, edit_company_place,
                                       edit_staff_scan_enable, edit_staff_dep_manage_enable, get_company_place,
                                       company_tract, company_place_tract, company_place_tract_export,
                                       company_audit_add_req, company_update_add_request, department_management,
                                       department_detail, company_del_staff, manager_place_verify, checkin_tract,
                                       checkin_export)

from maipassport.citadel.views import (liff_router, liff_bind_user, liff_forget_pass, liff_reset_pass, liff_sign_up,
                                       liff_scan, liff_sign_up_otp, liff_qr_code, liff_history, liff_declaration,
                                       liff_scan_sel, liff_health_status, liff_approach_status, liff_visitor_status,
                                       liff_work_status, liff_scan_work_status, liff_place_entry, liff_add_company,
                                       liff_check_in, liff_personal_file, liff_upload_user_img, liff_edit_password,
                                       liff_edit_password_otp, line_func_description, liff_com_reg, liff_com_reg_cancel,
                                       liff_scan_test, msg_api, img_router)

# api
from maipassport.citadel.views import web_otp_send, get_user_pic

# socket
# from maipassport.core.consumers import AsChatConsumer, ChatConsumer
from maipassport.citadel.views import chat_index, chat_room


# handler404 = 'aniappserver.core.views.http404'  TODO: override handler404

app_web_url_patterns = [
    path('login/', app_login, name='app_login'),
    path('logout/', app_logout, name='app_logout'),
    path('sign_up/', app_sign_up, name='app_sign_up'),
    path('privacy/', privacy_file, name='privacy_file'),
    path('sign_up_otc/', app_sign_up_otc, name='app_sign_up_otc'),
    path('forget_pass/', forget_pass, name='forget_pass'),
    path('fst_login/', first_time_login, name='fst_login'),
    path('fst_set_pwd/', first_time_set_pwd, name='fst_set_pwd'),
    path('reset_pass/', reset_pass, name='reset_pass'),
    path('message/', message_html, name='message_html'),
    path('description/', description, name='description'),

    path('login_new/', app_login_new, name='app_login_new'),

    path('index/<slug:user_id>/<str:token>/', app_index, name='app_index'),
    path('health/<slug:user_id>/<str:token>/', get_health_question_html, name='health'),
    # path('health-code/<slug:user_id>/<slug:token>/', get_health_code, name='health-code'),
    path('announcement/<slug:user_id>/<str:token>/', get_announcement, name='announcement'),
    path('history/<slug:user_id>/<str:token>/', get_history, name='get_history'),
    # Alan_TODO: health-check function not complete
    # path('health-check/<slug:user_id>/<str:token>/', health_check, name='health_check'),
    # path('health-check/<slug:user_id>/<str:token>/img/', upload_health_img, name='upload_health_img'),
    path('profile/<slug:user_id>/<str:token>/', user_profile, name='user_profile'),
    path('profile/<slug:user_id>/<str:token>/img/', upload_user_img, name='upload_user_img'),
    path('chick-in/<slug:user_id>/<str:token>/', chick_in_record, name='chick_in_record'),
    path('edit-pwd-otp/<slug:user_id>/<str:token>/', edit_password_otp, name='edit_password_otp'),
    path('edit-pwd/<slug:user_id>/<str:token>/', edit_password, name='edit_password'),
    path('shop-qrcode/<slug:user_id>/<str:token>/', shop_qrcode, name='shop_qrcode'),
    path('shop-qrcode/cancel/<slug:user_id>/<str:token>/', shop_qrcode_cancel, name='shop_qrcode_cancel'),
    path('shop-qrcode/edit/<slug:user_id>/<str:token>/', shop_qrcode_edit, name='shop_qrcode_edit'),


    # 掃描相關
    path('scan/<slug:user_id>/<str:token>/', scan_post, name='scan_post'),
    path('sel-scan/<slug:user_id>/<str:token>/', sel_scan, name='sel_scan'),
    path('work-status/<slug:user_id>/<str:token>/', user_work_status, name='user_work_status'),
    path('scan-work-status/<slug:user_id>/<str:token>/', scan_user_work_status, name='scan_work_status'),
    path('health-status/<slug:user_id>/<str:token>/', user_health_status, name='user_health_status'),
    path('approach-status/<slug:user_id>/<str:token>/', user_approach_status, name='user_approach_status'),
    path('visitor-status/<slug:user_id>/<str:token>/', user_visitor_status, name='user_visitor_status'),
    path('place/<slug:user_id>/<str:token>/', user_place_entry, name='user_place_entry'),
    path('addorg/<slug:user_id>/<str:token>/', user_add_company, name='user_add_company'),

    # api
    path('qr_code/<str:color_type>/<str:data>/', show_qr_code, name="qr_code"),

    path('scan-test/<slug:user_id>/<str:token>/', scan_test, name='scan_test'),
]

line_web_url_patterns = [
    # path('', return_index, name='line-index'),
    # path('callback/', callback, name='line-callback'),
    # path('currency_exchange/', handle_currency_exchange, name='test'),

    path('router/', liff_router, name='liff_router'),
    path('bind/', liff_bind_user, name='liff_bind'),
    path('forget_pass/', liff_forget_pass, name='liff_forget_pass'),
    path('reset_pass/', liff_reset_pass, name='liff_reset_pass'),
    path('qr/', liff_qr_code, name='liff_qr_code'),
    path('history/', liff_history, name='liff_history'),
    path('declaration/', liff_declaration, name='liff_declaration'),
    path('check_in/', liff_check_in, name='liff_check_in'),
    path('sign_up/', liff_sign_up, name='liff_sign_up'),
    path('sign_up_otp/', liff_sign_up_otp, name='liff_sign_up_otp'),
    path('scan/', liff_scan, name='liff_scan'),
    path('scan_sel/', liff_scan_sel, name='liff_scan_sel'),
    path('scan_sel/health/', liff_health_status, name='liff_health_status'),
    path('scan_sel/approach/', liff_approach_status, name='liff_approach_status'),
    path('scan_sel/visitor/', liff_visitor_status, name='liff_visitor_status'),
    path('scan_sel/work/', liff_work_status, name='liff_work_status'),
    path('scan_sel/scan_work/', liff_scan_work_status, name='liff_scan_work_status'),
    path('scan_sel/place/', liff_place_entry, name='liff_place_entry'),
    path('scan_sel/add_req/', liff_add_company, name='liff_add_req'),
    path('user_profile/', liff_personal_file, name='liff_personal_file'),
    path('upload_user_img/', liff_upload_user_img, name='liff_upload_user_img'),
    path('edit-pwd-otp/', liff_edit_password_otp, name='liff_edit_password_otp'),
    path('edit-pwd/', liff_edit_password, name='liff_edit_password'),
    path('com-reg/', liff_com_reg, name='liff_com_reg'),
    path('com-reg/cancel/', liff_com_reg_cancel, name='liff_com_reg_cancel'),

    path('description/', line_func_description, name='line_func_des'),

    path('scan-test/', liff_scan_test, name='liff_scan_test'),
    path('img-router/<slug:file_name>/<slug:file_size>', img_router, name='img_router')
]


websocket_room_urlpatterns = [
    # path('', chat_index, name='chat-index'),
    # path('<str:room_name>/', chat_room, name='room'),
]

websocket_urlpatterns = [
    # path('qr/trans/<str:room_name>/', AsChatConsumer),
]


backend_url_patterns = [
    path('login/', backend_login, name='backend_login'),
    path('logout/', backend_logout, name='backend_logout'),
    path('user-verify/', user_verify, name='user_verify'),
    path('verify-set/', verify_set_pwd, name='verify_set_pwd'),
    path('reset-pwd/', backend_reset_pwd, name='backend_reset_pwd'),

    path('', backend_index, name='backend_index'),
    path('users/', user_management, name='user_management'),
    path('users/<slug:pub_id>/', get_user_detail, name='user_detail'),
    path('users/<slug:pub_id>/create_open/<slug:status>/', user_create_open, name='user_create_open'),
    path('manage-enable/<slug:user_id>/<slug:company_id>/<slug:staff_id>/<str:edit_flag>'
         '/<str:backpage>/<str:manage_type>/',
         edit_user_manage_enable, name='edit_user_manage_enable'),
    path('companies/', company_management, name='company_management'),
    path('companies-create/', web_creat_company, name='creat_company'),
    path('new-company/', new_company_apply_req, name='new_company_apply_req'),
    path('new-company/update/<str:update_type>/', update_new_company_apply_req,
         name='update_new_company_apply_req'),


    path('companies/<slug:pub_id>/', get_company_detail, name='company_detail'),
    path('companies/<slug:pub_id>/create_open/<slug:status>/', place_create_open, name='place_create_open'),
    path('companies/<slug:pub_id>/checkin_open/<slug:status>/', place_checkin_open, name='place_checkin_open'),
    path('companies/<slug:pub_id>/department-create/', web_creat_department, name='create_department'),
    path('companies/<slug:pub_id>/department-delete/', web_del_department, name='delete_department'),
    path('companies/<slug:pub_id>/del_staff/', del_staff, name='del_staff'),
    path('no-companies/', no_company_detail, name='no_company_detail'),
    path('place/', place_management, name='place_management'),
    path('place/<str:edit_type>/', edit_place, name='edit_place'),
    path('place-verify/', place_verify, name='place_verify'),
    path('tract/user/', user_tract, name='user_tract'),
    path('tract/place/', place_tract, name='place_tract'),
    path('tract/checkin/', checkin_tract, name='checkin_tract'),
    path('tract/checkin/checkin_export', checkin_export, name='checkin_export'),
    path('update_add_req/<str:update_type>/', update_add_request, name='update_add_request'),

    path('company-index/<slug:pub_id>/', backend_company_index, name='company_index'),
    path('company-index/<slug:pub_id>/staff/', staff_management, name='staff_management'),
    path('company-index/<slug:pub_id>/staff/<slug:staff_id>/', get_staff_detail, name='staff_detail'),
    path('company-index/<slug:pub_id>/staff/<slug:staff_id>/scan-manage/<str:edit_flag>/<str:back_page>/',
         edit_staff_scan_enable, name='edit_staff_scan_enable'),
    path('company-index/<slug:pub_id>/staff/<slug:staff_id>/dep-manage/<str:edit_flag>/<str:back_page>/',
         edit_staff_dep_manage_enable, name='edit_staff_dep_manage_enable'),
    path('company-index/<slug:pub_id>/department/', department_management, name='department_management'),
    path('company-index/<slug:pub_id>/department/<slug:department_id>/', department_detail,
         name='department_detail'),
    path('company-index/<slug:pub_id>/place/', get_company_place, name='company_place'),
    path('company-index/<slug:pub_id>/place/<str:edit_type>/edit/', edit_company_place, name='edit_company_place'),
    path('company-index/<slug:pub_id>/tract/staff/', company_tract, name='company_tract'),
    path('company-index/<slug:pub_id>/tract/place/', company_place_tract, name='company_place_tract'),
    path('company-index/<slug:pub_id>/tract/place/export', company_place_tract_export, name='company_place_tract_export'),
    path('company-index/<slug:pub_id>/place-setting/', place_qrcode_print_setting, name='place_qrcode_print_setting'),
    path('company-index/<slug:pub_id>/audit-req/', company_audit_add_req, name='audit_add_req'),
    path('company-index/<slug:pub_id>/update-req/<str:update_type>/', company_update_add_request,
         name='company_update_req'),
    path('company-index/<slug:pub_id>/del-staff/<slug:del_page>/', company_del_staff, name='company_del_staff'),
    path('print_view/<str:print_type>/<str:user_type>/', print_view, name='print_view'),
    path('company-index/<slug:pub_id>/manager-place-verify/', manager_place_verify, name='manager_place_verify'),

]


urlpatterns = [
    # Django Admin, use {% url 'admin:index' %}
    path('i18n/', include('django.conf.urls.i18n')),
    path(settings.ADMIN_URL, admin.site.urls),
    # # Citadel dashboard,
    # # Your stuff: custom urls includes go here
    path('app/', include(app_web_url_patterns)),
    path('passboard/', include(backend_url_patterns)),
    # line liff
    path('line/', include(line_web_url_patterns)),
    # line liff
    path('msg_api/', msg_api, name='msg_api'),

    # api
    path('web_otp_send/', web_otp_send, name='web_otp_send'),
    path('get_user_img/<str:source_from>/', get_user_pic, name='get_user_pic'),
    path('update_session/', update_check_session, name='update_check_session'),


    # path('chat-test/', include(websocket_room_urlpatterns)),
    path('enc-test/', enc_message, name='enc_message'),
]

if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)


# Admin site title
admin.site.site_header = 'MaiPocket Control Panel'
admin.site.site_title = 'MaiPocket Control Panel'

#  ViewSet register here
router = routers.SimpleRouter()
router.register('web-user-records', WebUserRecordViewSet, base_name='record')
# router.register('users/ec-point-wallet', EcPointWalletViewSet, base_name='platform')
# router.register('audit-docs', AuditDocViewSet, base_name='audit_doc')
# router.register('physical-docs', PhysicalDocViewSet, base_name='physical_doc')
# router.register('advs', BannerViewSet, base_name='adv')
# router.register('pretrans', PretransferViewSet, base_name='pre_transfer')
# router.register('trans/pre-cash-ins', PreCashInViewSet, base_name='pre_cash_in')
# router.register('trans/pre-cash-outs', PreCashOutViewSet, base_name='pre_cash_out')
# router.register('trans/cash-ins', CashInViewSet, base_name='cash_in')
# router.register('trans/cash-outs', CashOutViewSet, base_name='cash_out')
# router.register('trans/platform/cash-ins', PlatformCashInViewSet, base_name='platform_cash_in')
# router.register('trans/platform/cash-outs', PlatformCashOutViewSet, base_name='platform_cash_out')
# router.register('trans/point-exchange', PointExchangeViewSet, base_name='point-exchange')
# router.register('trans/activity-cash-outs', ActivityTransferViewSet, base_name='activity_cash_out')
# router.register('trans', TransferViewSet, base_name='transfer')
# router.register('payment-gateways', PaymentGatewayViewSet, base_name='payment_gateway')
# router.register('withdraw-gateways', WithdrawGatewayViewSet, base_name='withdraw_gateway')
# router.register('entities', EntityViewSet, base_name='entity')
# router.register('platform', EcPlatformViewSet, base_name='ecplatform')
# router.register('ec/cash-ins', EcCashInViewSet, base_name='Ec_CashIn')
# # router.register('vc-trans-create', VcTransferCreateSet, base_name='vc-trans-create')
# router.register('activity', ActivityViewSet, base_name='activity')
# router.register('activity-trans', ActivityTransViewSet, base_name='activity-trans')
urlpatterns += router.urls
