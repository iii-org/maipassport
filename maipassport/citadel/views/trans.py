import json

from django.http import Http404
from django.shortcuts import render
from django.utils.safestring import mark_safe
from django.http import HttpResponse
from django.views.decorators.csrf import csrf_protect

from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status

from maipassport.citadel.services import logger_writer, get_image
from maipassport.core.services import OtpService
from maipassport.core.exceptions import OtpSendTooClose, OtpNoTarget, RequestFail
from maipassport.core.serializers import OtpSendSerializer


def chat_index(request):
    return render(request, 'app_web/test.html', {})


def chat_room(request, room_name):
    return render(request, 'app_web/test2.html', {
        'room_name_json': mark_safe(json.dumps(room_name))
    })


@api_view(['POST'])
@csrf_protect
def web_otp_send(request):
    if request.META.get('HTTP_X_MAI_TOKEN') != 'DeviceUser 5c7e9f90fa2e23502cc121afed142a78d91eb81c373f9139df2d1adff' \
                                               '4412b1d852bef3257d4192554065ff8df2331eb9ffde930' \
                                               '915bdaaf4eb13f17aa2eeb1f':
    # if request.META.get('HTTP_X_MAI_TOKEN') != 'DeviceUser 3e7a7cd39e8eee324994498d0c99b3b2f5df1e894b23ff3abbbaec5' \
    #                                            '0fa2817403ed6286ae33e690be8b2a52c938a743d211a3e3671b96ead23afa' \
    #                                            'd260447e413':
        raise NotImplementedError
    if request.META.get('HTTP_X_CLIENT_ID') != '0M7jDJ07t-TQTn-XqV5S':
        raise NotImplementedError
    serializer = OtpSendSerializer(data=request.data, context={'request': request})
    serializer.is_valid(raise_exception=True)
    validated_data = serializer.validated_data

    device_id = request.data.get('device_id', None)
    if 'email' not in validated_data and 'phone' not in validated_data:
        raise OtpNoTarget
    if 'email' in validated_data:
        email = validated_data['email']
    else:
        email = None
    if 'phone' in validated_data:
        phone = validated_data['phone']
        logger_writer('SYSTEM', 'info', 'WEB OTP SEND', f'{phone}')
    else:
        phone = None
    if not email and not phone:
        raise OtpNoTarget
    if request.session.get('otp_id'):
        old_otp_id = request.session.pop('otp_id')
        try:
            otp_id = OtpService(old_otp_id).send(device_id=device_id, email=email, phone=phone,
                                                 sys_name=validated_data['otp_text_type'])
        except OtpSendTooClose:
            request.session['otp_id'] = old_otp_id
            raise OtpSendTooClose
        # else:
            # request.session['otp_id'] = otp_id
    else:
        logger_writer('SYSTEM', 'info', 'WEB OTP SEND', f'OtpService().send')
        otp_id = OtpService().send(device_id=device_id, email=email, phone=phone,
                                   sys_name=validated_data['otp_text_type'])
    request.session['otp_id'] = otp_id
    return Response(data={'otp_id': otp_id})


@api_view(['GET'])
def get_user_pic(request, source_from):
    if source_from:
        if source_from == 'iii':
            # from iii
            if request.user_object.user_picture:
                b64str = get_image(request.user_object.user_picture)
                return Response(data={'picture_str': b64str})
            else:
                return Response(data={})
        else:
            if request.user_object.user_picture_local:
                b64str = get_image(request.user_object.user_picture_local)
                return Response(data={'picture_str': b64str})
            else:
                return Response(data={})
    else:
        raise RequestFail


@api_view(['POST'])
@csrf_protect
def update_check_session(request):
    if not request.is_ajax() or not request.method == 'POST':
        return Response(status=status.HTTP_404_NOT_FOUND)
    place_id = request.data.get('place_id')
    all_place_id = request.data.get('all_place_id')
    if place_id:
        if request.session.get('check_place'):
            check_list = request.session.get('check_place')
            if place_id in check_list:
                check_list.remove(place_id)
                request.session['check_place'] = check_list
                request.session['check_place_num'] = len(check_list)
            else:
                check_list.append(place_id)
                request.session['check_place'] = check_list
                request.session['check_place_num'] = len(check_list)
        else:
            request.session['check_place'] = [place_id]
            request.session['check_place_num'] = 1
        return Response(data={'check_place_num': request.session['check_place_num']})
    elif all_place_id:
        all_place_id = all_place_id.split(',')[:-1]
        for place in all_place_id:
            if request.session.get('check_place'):
                check_list = request.session.get('check_place')
                if place in check_list:
                    check_list.remove(place)
                    request.session['check_place'] = check_list
                    request.session['check_place_num'] = len(check_list)
                else:
                    check_list.append(place)
                    request.session['check_place'] = check_list
                    request.session['check_place_num'] = len(check_list)
            else:
                request.session['check_place'] = [place]
                request.session['check_place_num'] = 1
        return Response(data={'check_place_num': request.session['check_place_num']})
    else:
        return Response(status=status.HTTP_404_NOT_FOUND)
