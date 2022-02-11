from django.db import models
from django.conf import settings
from django.contrib.auth import get_user_model
from django.utils.translation import gettext_lazy as _

User = get_user_model()


class Permission(models.Model):
    """
    Note that permission is hard-code which created by script(DatabaseInitialService).
    """
    VIEW_ADMIN = 'View Admin Account'
    EDIT_ADMIN = 'Edit Admin Account'

    VIEW_USER = 'View User Account'
    EDIT_USER = 'Edit User Account'

    EDIT_SYSTEM = 'Edit System Parameters'

    EDIT_TRANSFER = 'Edit Transfer'
    VIEW_EXCHANGE = 'View Exchange'

    name = models.CharField(_('name'), max_length=80, unique=True)

    def __str__(self):
        return self.name


class Role(models.Model):

    ADMIN = 'Administrator'
    MANAGEMENT = 'Management'
    # DEP_MANAGEMENT = 'Department Management'
    APPUSER = 'User'

    ROLE_CHOICE = (
        (ADMIN, _("Administrator")),
        (MANAGEMENT, _("Management")),
        # (DEP_MANAGEMENT, _("Department Management")),
        (APPUSER, _("User")),
    )

    name = models.CharField(_('name'), max_length=80, unique=True)

    users = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        verbose_name=_('users')
    )

    permissions = models.ManyToManyField(
        Permission,
        verbose_name=_('permissions')
    )

    def __str__(self):
        return self.name

    @staticmethod
    def get_role_display_to_value_dict():
        return {role[0]: role[1] for role in Role.ROLE_CHOICE}
