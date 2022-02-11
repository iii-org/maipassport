from decimal import Decimal

from django.conf import settings

from maipassport.citadel.models import Permission, Role, User
from maipassport.companies.models import Title
from maipassport.records.models import QuestionnaireField
from maipassport.companies.models import Place, Company, AddCompanyTag
from maipassport.users.models import DeviceUser, token_generator


admin_role = Role.objects.filter(name=Role.ADMIN)
if not admin_role.exists():
    print(f'Create Role "{Role.ADMIN}"')
    admin_role = Role.objects.create(name=Role.ADMIN)
else:
    admin_role = admin_role.first()

if not Role.objects.filter(name=Role.MANAGEMENT).exists():
    print(f'Create Role "{Role.MANAGEMENT}"')
    man_role = Role.objects.create(name=Role.MANAGEMENT)

# if not Role.objects.filter(name=Role.DEP_MANAGEMENT).exists():
#     print(f'Create Role "{Role.DEP_MANAGEMENT}"')
#     dep_man_role = Role.objects.create(name=Role.DEP_MANAGEMENT)

if not Role.objects.filter(name=Role.APPUSER).exists():
    print(f'Create Role "{Role.APPUSER}"')
    user_role = Role.objects.create(name=Role.APPUSER)


admin = User.objects.filter(username='admin')
if not admin.exists():
    admin = User.objects.create_user(username="admin", password='Maipassport@01')
    admin.role_set.add(admin_role)
    print(f'Create Administrator successfully')
else:
    admin = admin.first()

if not Title.objects.filter(name='主管').exists():
    Title.objects.create(name='主管')
    print(f'Create Title 主管')
if not Title.objects.filter(name='警衛').exists():
    Title.objects.create(name='警衛')
    print(f'Create Title 警衛')
if not Title.objects.filter(name='職員').exists():
    Title.objects.create(name='職員')
    print(f'Create Title 職員')

if not QuestionnaireField.objects.filter(name='健康聲明調查表', type=QuestionnaireField.HEALTH).exists():
    QuestionnaireField.objects.create(
        name='健康聲明調查表', type=QuestionnaireField.HEALTH,
        field_name={
            "field": ["", ["無", "本人", "同居人"], ["無", "本人", "同居人"], ["無", "本人", "同居人"], ["無", "本人", "同居人"],
                      ["無", "本人", "同居人"], ["無", "本人", "同居人"], ["無", "本人", "同居人"]],
            "field_type": ["Number", "Checkbox", "Checkbox", "Checkbox", "Checkbox", "Checkbox", "Checkbox", "Checkbox"],
            "field_trans_name":
                ["今日額溫(填寫至小數點第1位)", "確診或疑似新冠肺炎", "居家隔離通知書", "居家檢疫通知書", "目前在境外或14天內有出國旅遊者",
                 "檢驗為陰性解除隔離者", "社區監測通報採檢個案", "身體不適"]
        })
if not QuestionnaireField.objects.filter(name='HEALTH_QUESTIONNAIRE_EN', type=QuestionnaireField.HEALTH).exists():
    QuestionnaireField.objects.create(
        name='HEALTH_QUESTIONNAIRE_EN', type=QuestionnaireField.HEALTH,
        field_name={
            "field": ["", ["None", "本人", "Cohabitant"], ["None", "本人", "Cohabitant"], ["None", "本人", "Cohabitant"],
                      ["None", "本人", "Cohabitant"], ["None", "本人", "Cohabitant"], ["None", "本人", "Cohabitant"],
                      ["None", "本人", "Cohabitant"]],
            "field_type": ["Number", "Checkbox", "Checkbox", "Checkbox", "Checkbox", "Checkbox", "Checkbox", "Checkbox"],
            "field_trans_name":
                ["today's forehead temperature(Fill in to the first decimal place)", "確診或疑似新冠肺炎", "居家隔離通知書",
                 "居家檢疫通知書", "目前在境外或14天內有出國旅遊者", "檢驗為陰性解除隔離者", "社區監測通報採檢個案", "身體不適"]
        })
if not DeviceUser.objects.filter(name='BACKEND').exists():
    DeviceUser.objects.create(name='BACKEND', api_token=token_generator(), public_sign_key=token_generator(8))


iii_comp = Company.objects.filter(name='資訊工業策進會')
if iii_comp.exists():
    iii_comp = iii_comp.first()
else:
    iii_comp = Company.objects.create(name='資訊工業策進會')
    place_file = open(settings.ROOT_DIR.path('place.txt'), mode='r')
    place_list = place_file.readlines()
    for place in place_list:
        place = place.replace('\n', '')
        place_str = place.split('////////')
        if not Place.objects.filter(name=place_str[0]).exists():
            Place.objects.create(name=place_str[0], location={'location_address': place_str[1]}, company=iii_comp)
            print(f'create {place_str[0]}')

if not AddCompanyTag.objects.filter(company_id=1).exists():
    AddCompanyTag.objects.create(company_id=1)

