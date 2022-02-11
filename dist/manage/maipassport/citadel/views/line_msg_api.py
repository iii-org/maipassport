import json

from django.http import Http404
from django.utils.translation import gettext_lazy as _
from django.shortcuts import render
from django.utils.safestring import mark_safe
from django.http import HttpResponse
from django.views.decorators.csrf import csrf_protect
from django.db.models import Q
from django.conf import settings
from django.utils.translation import activate

from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status

from maipassport.citadel.services import logger_writer, get_image
from maipassport.core.utils import (hmac_256, des_enc_data, login_flex_content, login_flex_content_eng,
                                    get_utc_format_today)
from maipassport.records.models import Questionnaire, QuestionnaireField
from maipassport.users.models import AppUser, HealthCode
from maipassport.users.services import AppUserServices

from linebot import (
    LineBotApi, WebhookHandler,
)

from linebot.models import (
    MessageEvent, TextMessage, TextSendMessage, TemplateSendMessage, URIAction, ButtonsTemplate, FlexSendMessage,
    ImageCarouselTemplate, ImageCarouselColumn, ImageSendMessage, ImagemapSendMessage, URIImagemapAction,
    ImagemapArea, BaseSize, MessageImagemapAction, PostbackTemplateAction
)

line_bot_api = LineBotApi(settings.MSG_API_CHANNEL_TOKEN)
handler = WebhookHandler(settings.MSG_API_CHANNEL_SEC)


def link_rich_menu(user_id, rich_menu_id):
    try:
        line_bot_api.link_rich_menu_to_user(user_id, rich_menu_id)
    except Exception as e:
        line_bot_api.link_rich_menu_to_user(user_id, settings.RH_DEFAULT_MENU)


@api_view(['POST'])
def msg_api(request):
    try:
        request_body = request.body
        verify_data = hmac_256(request.body, settings.MSG_API_CHANNEL_SEC)
        if verify_data.decode() != request.headers.get('X-Line-Signature'):
            return None
    except Exception as e:
        print()
        return None
    else:
        request_body = eval(request_body.decode())
        api_event = request_body['events']
        for event in api_event:
            if event['source']['type'] == 'user':
                event_user_id = event['source']['userId']
                enc_line_id = des_enc_data(event_user_id).decode()

                if 'replyToken' in event:
                    reply_token = event['replyToken']
                    # postback 點擊事件
                    if 'postback' in event:
                        postback_data_list = event['postback']['data'].split('&')
                        postback_data_dict = dict()
                        for postback_data in postback_data_list:
                            data_list = postback_data.split('=')
                            postback_data_dict[data_list[0]] = data_list[1]
                        if 'language' in postback_data_dict:
                            if postback_data_dict['language'] == 'en-us':
                                activate('en-us')
                            else:
                                activate('zh_Hant')
                        # postback 需有action
                        if 'action' in postback_data_dict:
                            if postback_data_dict['action'] == 'passcode_setting':
                                if postback_data_dict['data'] == 'next':
                                    # 其他
                                    if ('language' not in postback_data_dict or
                                            postback_data_dict['language'] == 'zh_Hant'):
                                        link_rich_menu(event_user_id, settings.RH_OTHER_NO_COM)
                                    else:
                                        link_rich_menu(event_user_id, settings.RH_OTHER_NO_COM_ENG)
                                    # if (hasattr(line_app_user, 'usercompanytable_set') and
                                    #         line_app_user.usercompanytable_set.filter(employed=True).exists()):
                                    #     link_rich_menu(event_user_id, settings.RH_OTHER)
                                    # else:
                                    #     link_rich_menu(event_user_id, settings.RH_OTHER_NO_COM)
                            elif postback_data_dict['action'] == 'index':
                                # 回首頁
                                if 'language' not in postback_data_dict or postback_data_dict['language'] == 'zh_Hant':
                                    # 中文版首頁
                                    link_rich_menu(event_user_id, settings.RH_DEFAULT_MENU)
                                else:
                                    # 英文版首頁
                                    link_rich_menu(event_user_id, settings.RH_DEFAULT_MENU_ENG)
                            elif postback_data_dict['action'] == 'relate_link':
                                # 相關連結
                                line_bot_api.reply_message(
                                    reply_token,
                                    TemplateSendMessage(
                                        alt_text=str(_('Related links')),
                                        template=ImageCarouselTemplate(
                                            columns=[
                                                ImageCarouselColumn(
                                                    image_url=
                                                    'https://iii.passcode.com.tw/static/app_web/img/roc_center.png',
                                                    action=URIAction(
                                                        label=str(_('CDC')),
                                                        uri='https://www.cdc.gov.tw/'
                                                    )
                                                ),
                                                ImageCarouselColumn(
                                                    image_url=
                                                    'https://iii.passcode.com.tw/static/app_web/img/mic.png',
                                                    action=URIAction(
                                                        label=str(_('MIC')),
                                                        uri='https://mic.iii.org.tw/AISP/NCP.aspx'
                                                    )
                                                )
                                            ]
                                        )
                                    )
                                )
                            elif postback_data_dict['action'] == 'func_description':
                                # 功能說明
                                if ('language' not in postback_data_dict or
                                        postback_data_dict['language'] == 'zh_Hant'):
                                    message = ImagemapSendMessage(
                                        base_url=
                                        "https://iii.passcode.com.tw/line/img-router/funcdescription2",
                                        alt_text=str(_('Please select your question category')),
                                        base_size=BaseSize(height=932, width=1040),
                                        actions=[
                                            URIImagemapAction(
                                                link_uri=
                                                "https://iii.passcode.com.tw/line/description/?func_type=des_group_1&language=zh_Hant",
                                                area=ImagemapArea(
                                                    x=0, y=0, width=520, height=466
                                                )
                                            ),
                                            URIImagemapAction(
                                                link_uri=
                                                "https://iii.passcode.com.tw/line/description/?func_type=des_group_2&language=zh_Hant",
                                                area=ImagemapArea(
                                                    x=520, y=0, width=520, height=466
                                                )
                                            ),
                                            URIImagemapAction(
                                                link_uri=
                                                "https://iii.passcode.com.tw/line/description/?func_type=des_group_3&language=zh_Hant",
                                                area=ImagemapArea(
                                                    x=0, y=466, width=346, height=466
                                                )
                                            ),
                                            URIImagemapAction(
                                                link_uri=
                                                "https://iii.passcode.com.tw/line/description/?func_type=des_group_4&language=zh_Hant",
                                                area=ImagemapArea(
                                                    x=346, y=466, width=346, height=466
                                                )
                                            ),
                                            URIImagemapAction(
                                                link_uri=
                                                "https://iii.passcode.com.tw/line/description/?func_type=des_group_5&language=zh_Hant",
                                                area=ImagemapArea(
                                                    x=692, y=466, width=346, height=466
                                                )
                                            ),
                                        ]
                                    )
                                else:
                                    message = ImagemapSendMessage(
                                        base_url=
                                        "https://iii.passcode.com.tw/line/img-router/funcdescription_eng",
                                        alt_text='Please select your question category',
                                        base_size=BaseSize(height=932, width=1040),
                                        actions=[
                                            URIImagemapAction(
                                                link_uri=
                                                "https://iii.passcode.com.tw/line/description/?func_type=des_group_1&language=en-us",
                                                area=ImagemapArea(
                                                    x=0, y=0, width=520, height=466
                                                )
                                            ),
                                            URIImagemapAction(
                                                link_uri=
                                                "https://iii.passcode.com.tw/line/description/?func_type=des_group_2&language=en-us",
                                                area=ImagemapArea(
                                                    x=520, y=0, width=520, height=466
                                                )
                                            ),
                                            URIImagemapAction(
                                                link_uri=
                                                "https://iii.passcode.com.tw/line/description/?func_type=des_group_3&language=en-us",
                                                area=ImagemapArea(
                                                    x=0, y=466, width=346, height=466
                                                )
                                            ),
                                            URIImagemapAction(
                                                link_uri=
                                                "https://iii.passcode.com.tw/line/description/?func_type=des_group_4&language=en-us",
                                                area=ImagemapArea(
                                                    x=346, y=466, width=346, height=466
                                                )
                                            ),
                                            URIImagemapAction(
                                                link_uri=
                                                "https://iii.passcode.com.tw/line/description/?func_type=des_group_5&language=en-us",
                                                area=ImagemapArea(
                                                    x=692, y=466, width=346, height=466
                                                )
                                            ),
                                        ]
                                    )
                                line_bot_api.reply_message(
                                    reply_token,
                                    message
                                )
                            else:
                                # 檢查綁定
                                line_app_user = AppUser.objects.filter(user_detail__line_id=enc_line_id)
                                if not line_app_user.exists():
                                    if reply_token not in [
                                        '00000000000000000000000000000000',
                                        'ffffffffffffffffffffffffffffffff'
                                    ]:
                                        # line_bot_api.push_message(
                                        #     event_user_id,
                                        #     TextSendMessage(
                                        #         text=str(_('You have not bound your account'))
                                        #     )
                                        # )
                                        if ('language' not in postback_data_dict or
                                                postback_data_dict['language'] == 'zh_Hant'):
                                            line_bot_api.reply_message(
                                                reply_token,
                                                FlexSendMessage(
                                                    alt_text=str(_('Please go to the account binding page first')),
                                                    contents=login_flex_content
                                                )
                                            )
                                        else:
                                            line_bot_api.reply_message(
                                                reply_token,
                                                FlexSendMessage(
                                                    alt_text='Please bind account first',
                                                    contents=login_flex_content_eng
                                                )
                                            )
                                else:
                                    line_app_user = line_app_user.first()
                                    if postback_data_dict['action'] == 'show_qr_code':
                                        # 顯示qrcode
                                        stime, etime = get_utc_format_today()

                                        if not Questionnaire.objects.filter(field_name__type=QuestionnaireField.HEALTH,
                                                                            app_user=line_app_user,
                                                                            modified__range=(stime, etime)).exists():
                                            health_code = HealthCode.UNFILLED
                                        else:
                                            health_code = line_app_user.healthcode.code

                                        if not line_app_user.qr_code_upload:
                                            result = AppUserServices.upload_user_qrcode(line_app_user.pub_id, 'USER')
                                            line_app_user.qr_code_upload = result
                                            line_app_user.save()
                                        qr_code_url = (
                                                    settings.QR_IMAGE_PATH +
                                                    f'{line_app_user.pub_id}/qr_code/{line_app_user.pub_id}')
                                        if health_code == HealthCode.WAIT_MEASURE:
                                            qr_code_url += '_orange.png'
                                        elif health_code == HealthCode.NORMAL:
                                            qr_code_url += '_green.png'
                                        elif health_code in [HealthCode.DANGER, HealthCode.QUEST_DANGER]:
                                            qr_code_url += '_red.png'
                                        else:
                                            qr_code_url += '_black.png'
                                        # 回應使用者
                                        line_bot_api.reply_message(
                                            reply_token,
                                            ImageSendMessage(
                                                original_content_url=qr_code_url,
                                                preview_image_url=qr_code_url
                                            )
                                        )
                                    elif postback_data_dict['action'] == 'com_mang':
                                        # 公司管理
                                        if ('language' not in postback_data_dict or
                                                postback_data_dict['language'] == 'zh_Hant'):
                                            message = ImagemapSendMessage(
                                                base_url=
                                                "https://iii.passcode.com.tw/line/img-router/companymang2",
                                                alt_text=str(_('Company management')),
                                                base_size=BaseSize(height=520, width=1040),
                                                actions=[
                                                    MessageImagemapAction(
                                                        text=str(_('Add Company QR Code')),
                                                        area=ImagemapArea(
                                                            x=0, y=0, width=346, height=520
                                                        )
                                                    ),
                                                    MessageImagemapAction(
                                                        text=str(_('Backstage Link')),
                                                        area=ImagemapArea(
                                                            x=346, y=0, width=346, height=520
                                                        )
                                                    ),
                                                    URIImagemapAction(
                                                        link_uri=
                                                        "https://liff.line.me/1654867456-yeP3wGLp",
                                                        area=ImagemapArea(
                                                            x=692, y=0, width=346, height=520
                                                        )
                                                    ),
                                                ]
                                            )
                                        else:
                                            message = ImagemapSendMessage(
                                                base_url=
                                                "https://iii.passcode.com.tw/line/img-router/companymang_eng",
                                                alt_text=str(_('Company management')),
                                                base_size=BaseSize(height=520, width=1040),
                                                actions=[
                                                    MessageImagemapAction(
                                                        text='Add Company QR Code',
                                                        area=ImagemapArea(
                                                            x=0, y=0, width=346, height=520
                                                        )
                                                    ),
                                                    MessageImagemapAction(
                                                        text='Backstage Link',
                                                        area=ImagemapArea(
                                                            x=346, y=0, width=346, height=520
                                                        )
                                                    ),
                                                    URIImagemapAction(
                                                        link_uri=
                                                        "https://liff.line.me/1654867456-neYzKO90",
                                                        area=ImagemapArea(
                                                            x=692, y=0, width=346, height=520
                                                        )
                                                    ),
                                                ]
                                            )
                                        # 回應使用者
                                        line_bot_api.reply_message(
                                            reply_token,
                                            message
                                        )
                                    else:
                                        # 無配對選項跳回首頁
                                        if ('language' not in postback_data_dict or
                                                postback_data_dict['language'] == 'zh_Hant'):
                                            link_rich_menu(event_user_id, settings.RH_DEFAULT_MENU)
                                        else:
                                            link_rich_menu(event_user_id, settings.RH_DEFAULT_MENU_ENG)

                    # message 回應事件
                    elif 'message' in event:
                        message = event['message']
                        if 'type' in message and message['type'] == 'text':
                            need_login_message = [str(_('Backstage Link')), str(_('Add Company QR Code'))]
                            need_login_message_eng = ['Backstage Link', 'Add Company QR Code']
                            if message['text'] in need_login_message or message['text'] in need_login_message_eng:
                                line_app_user = AppUser.objects.filter(user_detail__line_id=enc_line_id)
                                if not line_app_user.exists():
                                    if reply_token not in [
                                        '00000000000000000000000000000000',
                                        'ffffffffffffffffffffffffffffffff'
                                    ]:
                                        if message['text'] in need_login_message:
                                            reply_text = str(_('Please go to the account binding page first')),
                                        else:
                                            reply_text = 'Please bind account first'
                                        line_bot_api.reply_message(
                                            reply_token,
                                            FlexSendMessage(
                                                alt_text=reply_text,
                                                contents=login_flex_content_eng
                                            )
                                        )
                                else:
                                    line_app_user = line_app_user.first()
                                    if message['text'] in [str(_('Backstage Link')), 'Backstage Link']:
                                        if line_app_user.usercompanytable_set.filter(
                                                Q(manage_enabled=True) | Q(department_manage_enabled=True)).exists():
                                            line_bot_api.reply_message(
                                                reply_token,
                                                TextSendMessage(
                                                    text='https://iii.passcode.com.tw/passboard/'
                                                )
                                            )
                                        else:
                                            if message['text'] == str(_('Backstage Link')):
                                                reply_text = str(_("You don't have managing permission"))
                                            else:
                                                reply_text = "You don't have managing permission"
                                            line_bot_api.reply_message(
                                                reply_token,
                                                TextSendMessage(
                                                    text=reply_text,
                                                )

                                            )
                                    if message['text'] in [str(_('Add Company QR Code')), 'Add Company QR Code']:
                                        user_company = line_app_user.usercompanytable_set.filter(
                                                Q(manage_enabled=True) | Q(department_manage_enabled=True))
                                        if user_company.exists():
                                            def_com = user_company.filter(default_show=True)
                                            if def_com.exists():
                                                add_company_tag = def_com.first().company.addcompanytag
                                            else:
                                                add_company_tag = user_company.first().company.addcompanytag
                                            if not add_company_tag.qr_code_upload:
                                                result = AppUserServices.upload_user_qrcode(
                                                    add_company_tag.pub_id, 'ADDORG')
                                                add_company_tag.qr_code_upload = result
                                                add_company_tag.save()

                                            qr_code_url = (
                                                    settings.QR_IMAGE_PATH +
                                                    f'{add_company_tag.pub_id}/qr_code/{add_company_tag.pub_id}.png')
                                            line_bot_api.reply_message(
                                                reply_token,
                                                ImageSendMessage(
                                                    original_content_url=qr_code_url,
                                                    preview_image_url=qr_code_url
                                                )
                                            )
                                        else:
                                            if message['text'] == str(_('Add Company QR Code')):
                                                reply_text = str(_("You don't have managing permission"))
                                            else:
                                                reply_text = "You don't have managing permission"
                                            line_bot_api.reply_message(
                                                reply_token,
                                                TextSendMessage(
                                                    text=reply_text
                                                )
                                            )
                            else:
                                line_bot_api.reply_message(
                                    reply_token,
                                    TextSendMessage(
                                        text=str(_('Thanks for your message!')) + '\n\n' +
                                             str(_('Sorry, this account cannot individually reply to user messages.')) +
                                             '\n' + str(_('Please look forward to what we will send next time!'))
                                    )
                                )
                # rich_menu_id = line_bot_api.get_rich_menu_id_of_user(event_user_id)
        return Response(status=status.HTTP_200_OK)
