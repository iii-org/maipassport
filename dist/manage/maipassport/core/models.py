import json
import random
import time
import numpy
from datetime import datetime

from django.utils import timezone
from django.utils.translation import ugettext_lazy as _
from django.db import models
from django.conf import settings

from maipassport.core.utils import get_timestamp

from memoize import memoize


class CountryCode:
    """
    IS0-3166-1 country code
    """

    @staticmethod
    @memoize(timeout=60 * 60 * 24)
    def country_code_dict_list():
        country_code_json_file = settings.ROOT_DIR.path('config/utils/country_code.json')
        with open(country_code_json_file) as f:
            country_code_dict_list = json.loads(f.read())
        return country_code_dict_list

    @classmethod
    def COUNTRY_CODE_CHOICE(cls):
        country_code_dict_list = cls.country_code_dict_list()
        choices = [(d['code'], d['name']) for d in country_code_dict_list]
        return choices

    @classmethod
    def dial_code_list(cls):
        return [d['dial_code'] for d in cls.country_code_dict_list()]


class CurrencyCode:
    """
    ISO-4217 currency code
    """
    AgriNurtureIncPoint = 'ANP'  # Wallet points
    PhilippinePiso = 'PHP'


class LanguageCode:
    """
    ISO 639-1 language code
    """
    English = 'en'


class CreatedAndModifiedMixin(models.Model):

    # change id to BigAutoField
    id = models.BigAutoField(primary_key=True)

    created = models.DateTimeField(
        auto_now_add=True,
        db_index=True
    )
    modified = models.DateTimeField(
        auto_now=True,
        db_index=True
    )

    class Meta:
        abstract = True

    @property
    def modified_timestamp(self):
        """
        uts timestamp for api usage.
        """
        return get_timestamp(self.modified, return_milliseconds=False)


# Modeled after base64 web-safe chars, but ordered by ASCII.
ID_CHARS = ('0123456789-'
            'ABCDEFGHIJKLMNOPQRSTUVWXYZ'
            '_abcdefghijklmnopqrstuvwxyz')


class AutoPubIDField(models.CharField):
    description = 'Auto public ID field'
    empty_strings_allowed = False

    def __init__(self, *args, **kwargs):
        kwargs['blank'] = True
        kwargs['unique'] = True
        kwargs['editable'] = False
        kwargs['max_length'] = 20
        # Timestamp of last push, used to prevent local collisions
        # if you push twice in one ms.
        self.last_push_time = 0
        # Generating 72-bits of randomness which get turned into 12
        # characters and appended to the timestamp to prevent
        # collisions with other clients.  We store the last characters
        # we generated because in the event of a collision, we'll use
        # those same characters except "incremented" by one.
        self.last_rand_chars = numpy.empty(12, dtype=int)

        super().__init__(*args, **kwargs)

    def get_internal_type(self):
        return "CharField"

    def pre_save(self, model_instance, add):
        if add:
            value = self.create_pushid()
            setattr(model_instance, self.attname, value)
            return value
        else:
            return super().pre_save(model_instance, add)

    def db_type(self, connection):
        return 'char(20)'

    def create_pushid(self):
        # Implement a sortable, shorter is better, unpredictable, universal unique ID
        # currently use Firebase push algorithm:
        # https://firebase.googleblog.com/2015/02/the-2120-ways-to-ensure-unique_68.html
        now = int(time.time() * 1000)
        duplicate_time = (now == self.last_push_time)
        self.last_push_time = now
        timestamp_chars = numpy.empty(8, dtype=str)

        for i in range(7, -1, -1):
            timestamp_chars[i] = ID_CHARS[now % 64]
            now = int(now / 64)

        if (now != 0):
            raise ValueError('We should have converted the entire timestamp.')

        uid = ''.join(timestamp_chars)

        if not duplicate_time:
            for i in range(12):
                self.last_rand_chars[i] = int(random.random() * 64)
        else:
            # If the timestamp hasn't changed since last push, use the
            # same random number, except incremented by 1.
            for i in range(11, -1, -1):
                if self.last_rand_chars[i] == 63:
                    self.last_rand_chars[i] = 0
                else:
                    break
            self.last_rand_chars[i] += 1

        for i in range(12):
            uid += ID_CHARS[self.last_rand_chars[i]]

        if len(uid) != 20:
            raise ValueError('Length should be 20.')
        return uid
