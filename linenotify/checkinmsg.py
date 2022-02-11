from maipassport.records.models import NTPCCalender
import requests
from datetime import datetime


def checkinmsg():

    today = datetime.today()
    check_holiday = NTPCCalender.objects.filter(date=datetime.strftime(today, '%Y-%m-%d'))

    headers = {
        "Authorization": "Bearer A6SxQbHoirAUcFNxOZXILcDfRhxh5nmXqwCc6uvKTQf",
        "Content-Type": "application/x-www-form-urlencoded"
    }
    payload = {'message': '早上09:30上班打卡提醒\n' + 'https://line.me/R/ti/p/%40310ebhze' + '\n點擊連結打卡'}
    if not check_holiday.exists() or (check_holiday.exists() and check_holiday.first().isHoliday == False):
        r = requests.post("https://notify-api.line.me/api/notify", headers=headers, params=payload)

    return r.status_code



checkinmsg()