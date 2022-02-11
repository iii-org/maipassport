import logging
from collections import namedtuple

from django.core.cache import caches

# from aniappserver.users.models import (WalletUser, AppUser, ECUser, TYPE_WALLET_USER, TYPE_APP_USER, TYPE_EC_USER,
#                                        TYPE_MAI_USER)

from maipassport.users.models import AppUser, DeviceUser, TYPE_DEVICE_USER, TYPE_APP_USER

logger = logging.getLogger(__name__)


TokenCacheObject = namedtuple('TokenCacheObject', ['id', 'public_sign_key', 'uts'])
cluster_cache = caches['cluster']


def generate_token_cache_key(user_object):
    """
    :param user_object: WalletUser, AppUser or ECUser
    :return: cache_key
    """
    if isinstance(user_object, AppUser):
        cache_key = f"{TYPE_APP_USER}:{user_object.api_token}"
    elif isinstance(user_object, DeviceUser):
        cache_key = f"{TYPE_DEVICE_USER}:{user_object.api_token}"
    # elif isinstance(user_object, ECUser):
    #     if user_object.ec_name == 'mai_user':
    #         cache_key = f"{TYPE_MAI_USER}:{user_object.api_token}"
    #     else:
    #         cache_key = f"{TYPE_EC_USER}:{user_object.api_token}"
    # elif isinstance(user_object, ECUser):
    #     cache_key = f"{TYPE_EC_USER}:{user_object.api_token}"
    else:
        raise NotImplementedError
    return cache_key


def set_token_cache_object(user_object, uts=0):
    """
    Token cache structure:
    key -> token
    value -> [id, rsa_key_obj, uts]

    :param user_object: WalletUser, AppUser or ECUser
    :param uts: integer
    :return: TokenCacheObject
    """
    assert isinstance(uts, int), "Must be integer"
    assert user_object.api_token is not None
    assert user_object.public_sign_key is not None

    if not uts:   # when user is just created or refresh_cache
        old_cache = get_token_cache_object_by_user(user_object)
        uts = old_cache.uts if old_cache else 0

    cache_value = [user_object.id, user_object.public_sign_key, uts]

    # None is used to set cache without expired time
    cache_key = generate_token_cache_key(user_object)
    cluster_cache.set(cache_key, cache_value, None)

    return TokenCacheObject(*cache_value)


def get_token_cache_object_by_user(user_object):
    cache_key = generate_token_cache_key(user_object)
    token_cache = cluster_cache.get(cache_key)
    if token_cache:
        return TokenCacheObject(*token_cache)
    else:
        return None


# def get_token_cache_object(token: str, api_user_type=None, db_search=True):
#     """
#     Token cache structure:
#     key -> token
#     value -> [id, rsa_key_obj, uts]
#     """
#     if api_user_type == 'User':
#         user_type = TYPE_WALLET_USER
#     elif api_user_type == 'App':
#         user_type = TYPE_APP_USER
#     elif api_user_type == 'Ec':
#         user_type = TYPE_EC_USER
#     elif api_user_type == 'Mai':
#         user_type = TYPE_MAI_USER
#     else:
#         raise NotImplementedError
#
#     cache_key = f'{user_type}:{token}'
#     token_cache = cluster_cache.get(cache_key)
#     if token_cache:
#         return TokenCacheObject(*token_cache)
#     else:
#         if db_search:
#             if user_type is None:
#                 raise Exception('user_type is required.')
#
#             if user_type == TYPE_WALLET_USER:
#                 try:
#                     user = WalletUser.objects.get(api_token=token)
#                 except WalletUser.DoesNotExist:
#                     return None
#             elif user_type == TYPE_APP_USER:
#                 try:
#                     user = AppUser.objects.get(api_token=token)
#                 except AppUser.DoesNotExist:
#                     return None
#             elif user_type == TYPE_EC_USER:
#                 try:
#                     user = ECUser.objects.get(api_token=token)
#                 except ECUser.DoesNotExist:
#                     return None
#             elif user_type == TYPE_MAI_USER:
#                 try:
#                     user = ECUser.objects.get(api_token=token)
#                 except ECUser.DoesNotExist:
#                     return None
#             else:
#                 raise NotImplementedError
#
#             token_cache_object = set_token_cache_object(user, 0)
#             return token_cache_object
#         else:
#             return None


def delete_token_cache_object(user_object):
    cache_key = generate_token_cache_key(user_object)
    cluster_cache.delete(cache_key)
