from django.db import models
from django.utils.translation import gettext_lazy as _

from maipassport.core.models import CreatedAndModifiedMixin, AutoPubIDField


class PreUserQRTrans(CreatedAndModifiedMixin):

    pub_id = AutoPubIDField(
        _('Public Id'),
        db_index=True
    )

    app_user = models.ForeignKey(
        'users.AppUser',
        on_delete=models.CASCADE
    )

    expire_time = models.DateTimeField(
        null=True
    )

    NO_SCAN = 0
    PASS = 1
    NO_PASS = 2
    NO_HEALTH_QU = 3

    RETURN_CHOICE = (
        (PASS, 'PASS'),
        (NO_PASS, 'NO_PASS'),
        (NO_HEALTH_QU, 'NO_HEALTH_QU'),
    )

    return_code = models.PositiveSmallIntegerField(choices=RETURN_CHOICE, default=NO_SCAN)
