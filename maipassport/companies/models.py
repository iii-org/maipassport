import secrets
from decimal import Decimal

from django.utils.translation import gettext_lazy as _
from django.db import models
from django.conf import settings
from django.contrib.postgres.fields import JSONField

from maipassport.core.models import CreatedAndModifiedMixin, AutoPubIDField


class Company(CreatedAndModifiedMixin):

    pub_id = AutoPubIDField(
        _('Public Id'),
        db_index=True
    )

    name = models.CharField(
        max_length=100
    )

    tax_id_number = models.CharField(
        max_length=100,
        null=True
    )
    # client_id = models.CharField(
    #     max_length=100,
    #     null=True
    # )
    # client_secret = models.CharField(
    #     max_length=100,
    #     null=True
    # )
    place_create = models.BooleanField(
        default=False
    )
    verification_code = models.CharField(
        max_length=10,
        null=True
    )
    place_checkin = models.BooleanField(
        default=False
    )


class Department(CreatedAndModifiedMixin):

    pub_id = AutoPubIDField(
        _('Public Id'),
        db_index=True
    )

    name = models.CharField(
        max_length=100
    )

    company = models.ForeignKey(
        'companies.Company',
        on_delete=models.CASCADE
    )


class Title(models.Model):

    pub_id = AutoPubIDField(
        _('Public Id'),
        db_index=True
    )

    name = models.CharField(
        max_length=30
    )


class UserCompanyTable(CreatedAndModifiedMixin):

    pub_id = AutoPubIDField(
        _('Public Id'),
        db_index=True
    )

    company = models.ForeignKey(
        'companies.Company',
        on_delete=models.CASCADE
    )

    department = models.ForeignKey(
        'companies.Department',
        on_delete=models.CASCADE,
        null=True
    )

    title = models.ForeignKey(
        'companies.Title',
        on_delete=models.CASCADE,
        null=True
    )

    app_user = models.ForeignKey(
        'users.AppUser',
        on_delete=models.CASCADE
    )
    # 是否在職中，當升職或離職，此欄位改回False，做為在職紀錄
    employed = models.BooleanField(
        default=True
    )
    # 可掃描權限
    scan_enabled = models.BooleanField(
        default=False
    )
    # 預測顯示
    default_show = models.BooleanField(
        default=False
    )
    # 管理權限
    manage_enabled = models.BooleanField(
        default=False
    )
    # 部門管理權限
    department_manage_enabled = models.BooleanField(
        default=False
    )


# 在職紀錄
class UserCompanyHistory(CreatedAndModifiedMixin):

    pub_id = AutoPubIDField(
        _('Public Id'),
        db_index=True
    )

    user_company_table = models.ForeignKey(
        'companies.UserCompanyTable',
        on_delete=models.CASCADE
    )
    start_time = models.DateTimeField(

    )
    end_time = models.DateTimeField(
        null=True
    )


# models.model => CreatedAndModifiedMixin 20210520 by Alan Yang
class Place(CreatedAndModifiedMixin):

    pub_id = AutoPubIDField(
        _('Public Id'),
        db_index=True
    )

    name = models.CharField(
        max_length=100
    )

    company = models.ForeignKey(
        'companies.Company',
        on_delete=models.SET_NULL,
        null=True
    )

    # location = models.CharField(
    #     max_length=50,
    #     null=True
    # )
    location = JSONField(default=dict)

    # 可被掃描地點，目前尚未使用
    scan_enabled = models.BooleanField(
        default=False
    )

    serial_num = models.CharField(
        max_length=50,
        null=True
    )

    # 掃描更新健康碼
    update_health_code = models.BooleanField(
        default=False
    )

    # currently not used
    # address = models.TextField(null=True)

    # 公司審核
    NOT_VERIFY = 0
    VERIFY_PASS = 1
    VERIFY_NOT_PASS = 2
    VERIFY_CANCELLED = 3
    STATUS_CHOICE = (
        (NOT_VERIFY, _('Not Verify')),
        (VERIFY_PASS, _('Verify Pass')),
        (VERIFY_NOT_PASS, _('Verify Not Pass')),
        (VERIFY_CANCELLED, _('Verify Cancelled')),
    )

    company_verify = models.PositiveSmallIntegerField(
        choices=STATUS_CHOICE,
        default=NOT_VERIFY
    )
    # 預測顯示
    default_show = models.BooleanField(
        default=False
    )
    # 管理的使用者
    place_user = models.ForeignKey(
        'users.AppUser',
        on_delete=models.SET_NULL,
        null=True,
    )
    place_contact_phone = models.CharField(
        null=True,
        max_length=30
    )


class CompanyDefaultPrint(models.Model):

    pub_id = AutoPubIDField(
        _('Public Id'),
        db_index=True
    )

    company = models.ForeignKey(
        'companies.Company',
        on_delete=models.CASCADE
    )

    place_code = JSONField(default=dict)


# 使用在加入公司的id
class AddCompanyTag(models.Model):

    pub_id = AutoPubIDField(
        _('Public Id'),
        db_index=True
    )

    company = models.OneToOneField(
        'companies.Company',
        on_delete=models.CASCADE
    )

    qr_code_upload = models.BooleanField(
        default=False
    )


class AddRequest(CreatedAndModifiedMixin):

    pub_id = AutoPubIDField(
        _('Public Id'),
        db_index=True
    )

    WAIT_AUDIT = 0  # 待審核
    AGREE = 1  # 同意
    CANCEL = 2  # 取消

    STATUS_CHOICE = (
        (WAIT_AUDIT, _('Wait audit')),
        (AGREE, _('Agree')),
        (CANCEL, _('Cancel')),
    )

    status = models.PositiveSmallIntegerField(choices=STATUS_CHOICE, default=WAIT_AUDIT)

    add_user = models.ForeignKey(
        'users.AppUser',
        on_delete=models.CASCADE,
        related_name='add_user'
    )

    add_tag = models.ForeignKey(
        'companies.AddCompanyTag',
        on_delete=models.CASCADE
    )

    # agree = models.BooleanField(
    #     default=False
    # )

    agree_user = models.ForeignKey(
        'users.AppUser',
        on_delete=models.CASCADE,
        related_name='agree_user',
        null=True
    )
    note = JSONField(default=dict)


class NewCompanyApply(CreatedAndModifiedMixin):

    pub_id = AutoPubIDField(
        _('Public Id'),
        db_index=True
    )

    apply_user = models.ForeignKey(
        'users.AppUser',
        on_delete=models.CASCADE,
    )

    company_name = models.CharField(
        max_length=100,
    )

    tax_id_number = models.CharField(
        max_length=100,
    )

    WAIT_AUDIT = 0  # 待審核
    AGREE = 1  # 同意
    CANCEL = 2  # 取消

    STATUS_CHOICE = (
        (WAIT_AUDIT, _('Wait audit')),
        (AGREE, _('Agree')),
        (CANCEL, _('Cancel')),
    )

    status = models.PositiveSmallIntegerField(choices=STATUS_CHOICE, default=WAIT_AUDIT)


class ActionLog(CreatedAndModifiedMixin):
    pub_id = AutoPubIDField(
        _('Public Id'),
        db_index=True,
    )

    user_account = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='account'
    )

    USER_LOGIN = 'Backend_User_Login'  # 後台使用者登入
    USER_PRIVILEGE_CHANGE_MANAGER = 'User_Privilege_Changed_Manager'  # 使用者權限更變: Manager
    USER_PRIVILEGE_CHANGE_DEP_MANAGER = 'User_Privilege_Changed_Dep_Manager'  # 使用者權限更變: Department Manager
    USER_PRIVILEGE_CHANGE_HEALTHCODE = 'User_Privilege_Changed_Healthcode'  # 使用者權限更變: HealthCode
    PLACE_ADDED = 'Place_Add'  # 地點新增
    PLACE_PASS = 'Place_Pass'  # 地點審核通過
    PLACE_NOT_PASS = 'Place_Not_Pass'  # 地點審核不通過
    COMPANY_ADDED = 'Company_Add'  # 公司加入申請
    COMPANY_PASS = 'Company_Pass'  # 公司加入申請通過
    COMPANY_NOT_PASS = 'Company_Not_Pass'  # 公司加入申請未通過
    PLACE_PDF_DOWNLOAD = 'Place_PDF_Download'  # 地點管理下載pdf紀錄

    TYPE_CHOICE = (
        (USER_LOGIN, _('Backend User Login')),
        (USER_PRIVILEGE_CHANGE_MANAGER, _('User Privilege changed: Manager')),
        (USER_PRIVILEGE_CHANGE_DEP_MANAGER, _('User Privilege changes: Department Manager')),
        (USER_PRIVILEGE_CHANGE_HEALTHCODE, _('User Privilege changed: Healthcode')),
        (PLACE_ADDED, _('New Place Added')),
        (PLACE_PASS, _('Place Certification: PASS')),
        (PLACE_NOT_PASS, _('Place Certification: FAILED')),
        (COMPANY_ADDED, _('User Request: Company Join')),
        (COMPANY_PASS, _('User Request: Company Join PASS')),
        (COMPANY_NOT_PASS, _('User Request: Company Join FAILED')),
        (PLACE_PDF_DOWNLOAD, _('User Request: PDF Download')),
    )

    log_type = models.CharField(
        choices=TYPE_CHOICE,
        default=None,
        max_length=60
    )

