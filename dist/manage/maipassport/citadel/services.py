from django.conf import settings
import json
import requests
from PIL import Image, ExifTags
from io import BytesIO
from base64 import b64encode

from pyzbar.pyzbar import decode, ZBarSymbol
from PIL import Image, ImageEnhance
import cv2
import numpy as np

from maipassport.core.exceptions import GetUserImgFailed


def logger_writer(log_type, log_level, action_name, msg):
    if log_type.upper() == 'SYSTEM':
        logger = settings.SYSTEM_LOG
    # elif log_type.upper() == 'ADMIN_WEB':
    #     logger = settings.ADMIN_WEB_LOG
    # elif log_type.upper() == 'CELERY_TASK':
    #     logger = settings.CELERY_TASK_LOG
    else:
        logger = settings.SYSTEM_LOG

    if log_level == 'info':
        logger.info('[%s] %s' % (action_name, msg))
    elif log_level == 'warning':
        logger.warning('[%s] %s' % (action_name, msg))
    elif log_level == 'error':
        logger.error('[%s] %s' % (action_name, msg))
    else:
        logger.debug('[%s] %s' % (action_name, msg))


def get_image(url):
    try:
        response = requests.get(url)
        image = Image.open(BytesIO(response.content))
        # w, h = image.size
    except Exception as e:
        raise GetUserImgFailed
    else:
        try:
            for orientation in ExifTags.TAGS.keys():
                if ExifTags.TAGS[orientation] == 'Orientation':
                    break
            exif = dict(image._getexif().items())
            if exif[orientation] == 3:
                image = image.rotate(180, expand=True)
            elif exif[orientation] == 6:
                image = image.rotate(270, expand=True)
            elif exif[orientation] == 8:
                image = image.rotate(90, expand=True)
            # buf = BytesIO()
            # image.save(buf, format='JPEG')
            # return b64encode(buf.getvalue()).decode('ascii')
        except Exception as e:
            # cases: image don't have getexif
            pass

        w, h = image.size
        buf = BytesIO()
        img_type = url.split('.')
        if img_type[-1] in ['jpg', 'jpeg']:
            img_format = 'JPEG'
        elif img_type[-1] == 'png':
            img_format = 'PNG'
        else:
            img_format = 'JPEG'
        image.save(buf, format=img_format)
        # return b64encode(buf.getvalue()).decode('ascii')
        data = json.dumps({
            'img_data': 'data:image/' + img_format.lower() + ';base64,' + b64encode(buf.getvalue()).decode('ascii'),
            'img_width': w,
            'img_height': h,
        })
        return data


def read_qr_code_old(img_obj):
    # img = Image.open(img_obj)
    # # 灰度化
    # img = img.convert('L')
    # # 增亮
    # img = ImageEnhance.Brightness(img).enhance(3.0)
    # # 增加銳化
    # img = ImageEnhance.Sharpness(img).enhance(17.0)
    # # 增加對比度
    # img = ImageEnhance.Contrast(img).enhance(4.0)

    img = cv2.imdecode(np.fromstring(img_obj.read(), np.uint8), cv2.IMREAD_COLOR)
    # img = cv2.imdecode(np.fromstring(img_obj.read(), np.uint8), cv2.IMREAD_UNCHANGED)
    # 轉為灰階影像
    # img = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    # # 對圖像進行高斯模糊
    # img = cv2.GaussianBlur(img, (5, 5), 0)
    # # 檢測邊緣
    # edges = cv2.Canny(img, 100, 200)

    # barcodes = decode(img, symbols=[ZBarSymbol.QRCODE])
    # for barcode in barcodes:
    #     (x, y, w, h) = barcode.rect
    #     cv2.rectangle(img, (x, y), (x + w, y + h), (0, 0, 255), 2)
    #     barcodeData = barcode.data.decode("utf-8")

    detector = cv2.QRCodeDetector()
    barcodeData, bbox, straight_qrcode = detector.detectAndDecode(img)
    if barcodeData == '':
        return None
    else:
        return barcodeData


def read_qr_code(img_obj):
    img = cv2.imdecode(np.fromstring(img_obj.read(), np.uint8), cv2.IMREAD_COLOR)
    # 調整圖像大小
    scale = 0.3
    width = int(img.shape[1] * scale)
    height = int(img.shape[0] * scale)
    img = cv2.resize(img, (width, height))
    # 調整對比色 反白qr code 讓整張圖黑白反向
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    _, thresh = cv2.threshold(gray, 120, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    # 型態運算 將qr code 中間去除變為一個白色正方形
    kernel = np.ones((3, 3), np.uint8)
    thresh = cv2.dilate(thresh, kernel, iterations=1)
    contours, _ = cv2.findContours(thresh, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
    # 過濾 獲取邊框
    bboxes = []
    for cnt in contours:
        area = cv2.contourArea(cnt)
        xmin, ymin, width, height = cv2.boundingRect(cnt)
        # extent = area / (width * height)
        extent = min(width, height)/max(width, height)
        # filter non-rectangular objects and small objects
        if (extent > np.pi / 4) and (area > 100):
            bboxes.append((xmin, ymin, xmin + width, ymin + height))

    qrs = []
    # info = set()
    for xmin, ymin, xmax, ymax in bboxes:
        roi = img[ymin:ymax, xmin:xmax]
        detections = decode(roi, symbols=[ZBarSymbol.QRCODE])
        for barcode in detections:
            # info.add(barcode.data)
            # bounding box coordinates
            # x, y, w, h = barcode.rect
            # qrs.append((xmin + x, ymin + y, xmin + x + w, ymin + y + height))
            qrs.append(barcode.data.decode())
        # detector = cv2.QRCodeDetector()
        # barcodeData, bbox, straight_qrcode = detector.detectAndDecode(roi)
    if not qrs:
        return None
    else:
        return qrs[0]
