# this script can be added into records.service

import requests
from datetime import datetime
from maipassport.records.models import NTPCCalender

# get date from ntpc api
r = requests.get("https://data.ntpc.gov.tw/api/datasets/308DCD75-6434-45BC-A95F-584DA4FED251/json?page=2&size=500")
r = r.json()

# write into db
for record in r:
    date = record['date'].replace('/', '-')
    date = datetime.strptime(date, '%Y-%m-%d')
    if record['isHoliday'] == "是":
        check_holiday = True
    else:
        check_holiday = False
    if record['name'] != '':
        holiday_name = record['name']
    else:
        holiday_name = record['holidayCategory']
    if not NTPCCalender.objects.filter(date=date).exists():
        n = NTPCCalender.objects.create(date=date, isHoliday=check_holiday, description=holiday_name)
        n.save()