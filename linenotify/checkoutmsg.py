import requests
import datetime


def checkoutmsg():
    weekno = datetime.datetime.today().weekday()

    if weekno < 5:
        headers = {
            "Authorization": "Bearer A6SxQbHoirAUcFNxOZXILcDfRhxh5nmXqwCc6uvKTQf",
            "Content-Type": "application/x-www-form-urlencoded"
        }

        payload = {'message': '早上18:30下班打卡提醒'}
        r = requests.post("https://notify-api.line.me/api/notify", headers = headers, params = payload)
        return r.status_code



checkoutmsg()