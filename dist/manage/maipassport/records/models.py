import secrets
from decimal import Decimal

from django.utils.translation import gettext_lazy as _
from django.db import models
from django.conf import settings
from django.contrib.postgres.fields import JSONField

from maipassport.core.models import CreatedAndModifiedMixin, AutoPubIDField
from maipassport.users.models import HealthCode, AttendanceStatus


# 地點足跡紀錄表
class PlaceEntryRecord(CreatedAndModifiedMixin):

    pub_id = AutoPubIDField(
        _('Public Id'),
        db_index=True
    )

    app_user = models.ForeignKey(
        'users.AppUser',
        on_delete=models.PROTECT
    )
    # 是否為訪客
    visitor = models.BooleanField(
        default=False
    )

    # 進入的地點
    place_entry = models.ForeignKey(
        'companies.Place',
        on_delete=models.CASCADE,
        null=True
    )

    # 掃描地點
    # location = models.CharField(
    #     max_length=50,
    #     null=True,
    # )
    location = JSONField(default=dict)

    note = JSONField(default=dict)


# 接觸紀錄
class ApproachRecord(CreatedAndModifiedMixin):

    pub_id = AutoPubIDField(
        _('Public Id'),
        db_index=True
    )

    APPROACH_CHECK = 0  # 接觸確認
    HEALTH_CHECK = 1  # 健康確認
    VISITOR_CHECK = 2  # 訪客確認
    TRANS_POINT = 3

    PERMISSION_CHOICE = (
        (APPROACH_CHECK, 'Approach check'),
        (HEALTH_CHECK, 'Health check'),
        (VISITOR_CHECK, 'Visitor check'),
        (TRANS_POINT, 'Transfer point'),
    )

    type = models.PositiveSmallIntegerField(choices=PERMISSION_CHOICE)

    # 被紀錄者
    app_user = models.ForeignKey(
        'users.AppUser',
        on_delete=models.PROTECT,
        related_name='app_user'
    )

    # 掃描者
    scan_user = models.ForeignKey(
        'users.AppUser',
        on_delete=models.PROTECT,
        related_name='scan_user',
    )

    # # 地點足跡紀錄表
    # place_record = models.OneToOneField(
    #     'records.PlaceEntryRecord',
    #     models.SET_NULL,
    #     null=True
    # )

    # 接觸位置
    approach_place = models.ForeignKey(
        'companies.Place',
        on_delete=models.SET_NULL,
        null=True
    )

    # 掃描位置
    # location = models.CharField(
    #     max_length=50,
    #     null=True,
    # )
    location = JSONField(default=dict)


# 健康紀錄表
class HealthRecord(CreatedAndModifiedMixin):

    pub_id = AutoPubIDField(
        _('Public Id'),
        db_index=True
    )

    app_user = models.ForeignKey(
        'users.AppUser',
        on_delete=models.PROTECT,
    )

    # 接觸紀錄
    approach_record = models.OneToOneField(
        'records.ApproachRecord',
        on_delete=models.CASCADE,
        null=True
    )

    # 掃描時健康碼
    health_code = models.PositiveSmallIntegerField(choices=HealthCode.CODE_CHOICE, default=HealthCode.WAIT_MEASURE)

    content = JSONField(default=dict)

    # 溫度，預留
    temperature = models.CharField(
        max_length=20,
        null=True
    )

    SCAN_RECORD = 0
    QUESTIONNAIRE_RECORD = 1

    TYPE_CHOICE = (
        (SCAN_RECORD, _('Scan record')),
        (QUESTIONNAIRE_RECORD, _('Questionnaire record')),
    )

    record_type = models.PositiveSmallIntegerField(choices=HealthCode.CODE_CHOICE, default=SCAN_RECORD)

    # @property
    # def get_health_code_display


# 訪客登記表
class VisitorRegistration(CreatedAndModifiedMixin):

    pub_id = AutoPubIDField(
        _('Public Id'),
        db_index=True
    )

    app_user = models.ForeignKey(
        'users.AppUser',
        on_delete=models.PROTECT,
    )

    company = models.ForeignKey(
        'companies.Company',
        on_delete=models.PROTECT,
    )

    # 接觸紀錄
    approach_record = models.OneToOneField(
        'records.ApproachRecord',
        on_delete=models.CASCADE,
        null=True
    )

    # 已來訪
    visitor = models.BooleanField(
        default=False
    )


# 出勤表
class AttendanceRecord(CreatedAndModifiedMixin):

    pub_id = AutoPubIDField(
        _('Public Id'),
        db_index=True
    )

    # 掃描者
    app_user = models.ForeignKey(
        'users.AppUser',
        on_delete=models.PROTECT,
        null=True
    )

    ON_WORK = 0
    GET_OFF_WORK = 1

    STATUS_CHOICE = (
        (ON_WORK, 'On Work'),
        (GET_OFF_WORK, 'Get off work'),
    )

    status = models.PositiveSmallIntegerField(choices=STATUS_CHOICE, default=GET_OFF_WORK)

    # 填表地點
    approach_place = models.ForeignKey(
        'companies.Place',
        on_delete=models.SET_NULL,
        null=True
    )

    # 填表位置
    # location = models.CharField(
    #     max_length=50,
    #     null=True,
    # )
    location = JSONField(default=dict)

    attendance_status = models.PositiveSmallIntegerField(choices=AttendanceStatus.STATUS_CHOICE)


# 問券欄位
class QuestionnaireField(CreatedAndModifiedMixin):

    pub_id = AutoPubIDField(
        _('Public Id'),
        db_index=True
    )
    OTHER = 0  # 其他
    HEALTH = 1  # 健康聲明調查表
    VISITOR = 2  # 訪客登記表

    TYPE_CHOICE = (
        (OTHER, 'Other'),
        (HEALTH, 'Health Questionnaire'),
        (VISITOR, 'Visitor registration form')
    )
    # 問券類型
    type = models.PositiveSmallIntegerField(choices=TYPE_CHOICE, default=OTHER)

    # 問券名稱
    name = models.CharField(
        max_length=100
    )

    field_name = JSONField(default=dict)


# 商戶問券配對
class QuestionnaireCompany(CreatedAndModifiedMixin):

    pub_id = AutoPubIDField(
        _('Public Id'),
        db_index=True
    )
    # 問券類型
    type = models.PositiveSmallIntegerField(choices=QuestionnaireField.TYPE_CHOICE, default=QuestionnaireField.OTHER)

    company = models.ForeignKey(
        'companies.Company',
        on_delete=models.CASCADE
    )

    questionnaire = models.ForeignKey(
        'records.QuestionnaireField',
        on_delete=models.CASCADE
    )
    default = models.BooleanField(
        default=True
    )


# 問券內容
class Questionnaire(CreatedAndModifiedMixin):

    pub_id = AutoPubIDField(
        _('Public Id'),
        db_index=True
    )

    app_user = models.ForeignKey(
        'users.AppUser',
        on_delete=models.PROTECT
    )

    field_name = models.ForeignKey(
        'records.QuestionnaireField',
        on_delete=models.CASCADE
    )

    content = JSONField(default=dict)

    location = JSONField(default=dict)


# line flex message
class FlexContent(models.Model):

    pub_id = AutoPubIDField(
        _('Public Id'),
        db_index=True
    )

    name = models.CharField(
        max_length=100
    )

    content = JSONField(default=dict)

# 公告
# class Announcement(CreatedAndModifiedMixin):
#
#     pub_id = AutoPubIDField(
#         _('Public Id'),
#         db_index=True
#     )
#
#     title = models.CharField(
#         max_length=50,
#     )
#
#     content = models.CharField(
#         max_length=50,
#     )


# TODO: 未來加入
# 交易
# 請假表
# 會議室租借


