import secrets
from decimal import Decimal

from django.contrib.auth.models import AbstractBaseUser
from django.utils.translation import gettext_lazy as _
from django.db import models
from django.conf import settings
from django.contrib.postgres.fields import JSONField

from maipassport.core.models import CreatedAndModifiedMixin, AutoPubIDField


def token_generator(num=None):
    if num:
        return secrets.token_hex(num)
    else:
        return secrets.token_hex(64)


TYPE_DEVICE_USER = 'Device'
TYPE_APP_USER = 'App'


class DeviceUser(CreatedAndModifiedMixin):

    class Meta:
        verbose_name_plural = "app_users"
        verbose_name = "app_user"

    pub_id = AutoPubIDField(
        _("Public ID"),
        db_index=True
    )

    api_token = models.CharField(
        _("API Token"),
        unique=True,
        db_index=True,
        default=token_generator,
        max_length=255
    )
    public_sign_key = models.CharField(
        _("API Verify Key"),
        unique=True,
        max_length=511
    )

    name = models.CharField(
        _("Display Name"),
        max_length=32
    )

    def refresh_cache(self):
        from maipassport.core.cache_utils import set_token_cache_object
        cache = set_token_cache_object(self)
        return cache


class AppUser(CreatedAndModifiedMixin):

    pub_id = AutoPubIDField(
        _('Public Id'),
        db_index=True
    )

    api_token = models.CharField(
        _("API Token"),
        unique=True,
        db_index=True,
        max_length=255,
        null=True
    )
    public_sign_key = models.CharField(
        _("API Verify Key"),
        unique=True,
        max_length=511
    )

    auth_user = models.OneToOneField(
        'auth.User',
        on_delete=models.CASCADE
    )

    alias_id = models.CharField(
        _("Alias ID"),
        max_length=16,
        unique=True,
        blank=True,
        null=True
    )
    emp_no = models.CharField(
        max_length=100,
        null=True,
    )
    phone = models.CharField(
        max_length=64  ,
        unique=True,
        blank=True,
        null=True,
        db_index=True
    )
    email = models.EmailField(
        max_length=50,
        unique=True,
        blank=True,
        null=True,
        db_index=True
    )
    # 預留開啟掃描別人欄位
    scan_enabled = models.BooleanField(
        default=False
    )
    note = models.CharField(
        max_length=100,
        null=True,
        blank=True
    )
    token_expire_time = models.DateTimeField(
        null=True
    )
    user_picture = models.URLField(
        null=True
    )
    # user_picture_b64 = models.TextField(
    #     null=True,
    # )
    user_picture_local = models.URLField(
        null=True
    )
    user_detail = JSONField(default=dict)

    qr_code_upload = models.BooleanField(
        default=False
    )


class HealthCode(CreatedAndModifiedMixin):

    pub_id = AutoPubIDField(
        _('Public Id'),
        db_index=True
    )

    app_user = models.OneToOneField(
        'users.AppUser',
        on_delete=models.PROTECT
    )

    WAIT_MEASURE = 0
    NORMAL = 1
    DANGER = 2
    QUEST_DANGER = 3
    UNFILLED = 9

    CODE_CHOICE = (
        (WAIT_MEASURE, _('To be Measured')),
        (NORMAL, _('Normal')),
        (DANGER, _('Danger')),
        (QUEST_DANGER, _('High Risk')),
        (UNFILLED, _('Unfilled')),
    )

    code = models.PositiveSmallIntegerField(choices=CODE_CHOICE, default=UNFILLED)

    @staticmethod
    def code_list():
        return [HealthCode.WAIT_MEASURE, HealthCode.NORMAL, HealthCode.DANGER]

    @staticmethod
    def code_choice_detail():
        return {code_ch[0]: code_ch[1] for code_ch in HealthCode.CODE_CHOICE}

    # @property
    # def get_code_name(self):
    #     if self.code == self.WAIT_MEASURE:
    #         return 'EXCHANGE_IN'
    #     elif self.code == self.TYPE_EXCHANGE_OUT:
    #         return 'EXCHANGE_OUT'
    #     elif self.code == self.TYPE_CASH_IN:


class AttendanceStatus(CreatedAndModifiedMixin):

    pub_id = AutoPubIDField(
        _('Public Id'),
        db_index=True
    )

    app_user = models.ForeignKey(
        'users.AppUser',
        on_delete=models.PROTECT
    )
    # 上班
    ON_WORK = 0
    # 下班
    GET_OFF_WORK = 1
    # 請假
    LEAVE = 2
    # 外勤
    FIELDWORK = 3
    # 出差
    BUSINESS_TRIP = 4

    STATUS_CHOICE = (
        (ON_WORK, _('At Work')),
        (GET_OFF_WORK, _('Get off work')),
        (LEAVE, _('Leave')),
        (FIELDWORK, _('Fieldwork')),
        (BUSINESS_TRIP, _('Business trip'))
    )

    company = models.ForeignKey(
        'companies.Company',
        on_delete=models.PROTECT
    )

    status = models.PositiveSmallIntegerField(choices=STATUS_CHOICE, default=GET_OFF_WORK)

    # 是否為遠端工作
    remote_work = models.BooleanField(
        default=False
    )

    @staticmethod
    def status_list():
        return [AttendanceStatus.ON_WORK, AttendanceStatus.GET_OFF_WORK, AttendanceStatus.LEAVE,
                AttendanceStatus.FIELDWORK, AttendanceStatus.BUSINESS_TRIP]

    @staticmethod
    def return_status_dict():
        return {status[0]: status[1] for status in AttendanceStatus.STATUS_CHOICE}


# 暫時放棄
class AppUserPermission(CreatedAndModifiedMixin):

    pub_id = AutoPubIDField(
        _('Public Id'),
        db_index=True
    )

    APPROACH_CHECK = 0  # 接觸確認
    HEALTH_CHECK = 1  # 健康確認
    VISITOR_CHECK = 2  # 訪客確認
    TRANS_POINT = 3  # 交易

    PERMISSION_CHOICE = (
        (APPROACH_CHECK, 'Approach check'),
        (HEALTH_CHECK, 'Health check'),
        (VISITOR_CHECK, 'Visitor check'),
        (TRANS_POINT, 'Transfer point'),
    )

    permission = models.PositiveSmallIntegerField(choices=PERMISSION_CHOICE)

    app_user = models.ManyToManyField(
        'users.AppUser',
        verbose_name=_('app_users')
    )


class CompanyUser(CreatedAndModifiedMixin):

    class Meta:
        verbose_name_plural = "app_users"
        verbose_name = "app_user"

    pub_id = AutoPubIDField(
        _("Public ID"),
        db_index=True
    )

    api_token = models.CharField(
        _("API Token"),
        unique=True,
        db_index=True,
        default=token_generator,
        max_length=255
    )
    public_sign_key = models.CharField(
        _("API Verify Key"),
        unique=True,
        max_length=511
    )

    name = models.CharField(
        _("Display Name"),
        max_length=32
    )

    company = models.OneToOneField(
        'companies.Company',
        on_delete=models.CASCADE
    )

    def refresh_cache(self):
        from maipassport.core.cache_utils import set_token_cache_object
        cache = set_token_cache_object(self)
        return cache
