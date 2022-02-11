from base64 import b64decode, b64encode, urlsafe_b64decode, urlsafe_b64encode
from binascii import Error as binasciiError

from django.utils.translation import ugettext_lazy as _
from django.conf import settings

from pyDes import triple_des, CBC, PAD_PKCS5

from Crypto.PublicKey import RSA
from Crypto.Cipher import PKCS1_v1_5, PKCS1_OAEP, AES

from Crypto.Hash import SHA256
from Crypto.Signature import pkcs1_15
from Crypto.Hash import SHA
from Crypto import Random

import hashlib
import hmac


def generate_rsa_pem_files(file_prefix='maipassport', bits=1024):
    """
    Helper method to generate rsa pem file.
    """
    private_key = RSA.generate(bits)
    public_key = private_key.publickey()

    f = open(settings.RSA_KEYS_DIR.path(f'{file_prefix}_private_key.pem'), 'wb')
    f.write(private_key.export_key('PEM'))
    f.close()

    f = open(settings.RSA_KEYS_DIR.path(f'{file_prefix}_public_key.pem'), 'wb')
    f.write(public_key.export_key('PEM'))
    f.close()


def generate_rsa_key_pair(bits=1024, return_string=False):
    private_key = RSA.generate(bits)
    public_key = private_key.publickey()
    if return_string:
        private_sign_key_string = private_key.export_key().decode().replace('\n', '').split('-----')[2]
        public_sign_key_string = public_key.export_key().decode().replace('\n', '').split('-----')[2]
        return private_sign_key_string, public_sign_key_string
    else:
        return private_key, public_key


def rsa_import_key_string(rsa_key_string: str):
    rsa_key_object = RSA.import_key(
        f'-----BEGIN PUBLIC KEY-----\n{rsa_key_string}\n-----END PUBLIC KEY-----'
    )
    return rsa_key_object


def rsa_import_key_pem(file_path):
    rsa_object = RSA.import_key(open(file_path, 'r').read())
    return rsa_object


# rsa_decrypt_key = rsa_import_key_pem(settings.RSA_PRIVATE_KEY_PEM)
# rsa_encrypt_key = rsa_import_key_pem(settings.RSA_PUBLIC_KEY_PEM)
# rsa_sign_key = rsa_import_key_pem(settings.RSA_SIGN_KEY_PEM)

rsa_decrypt_key = None
rsa_encrypt_key = None
rsa_sign_key = None

# data_key = rsa_import_key_pem(settings.RSA_DATA_KEY_PEM)
# card_data_pub_key = rsa_import_key_pem(settings.RSA_CARD_DATA_KEY_PEM)


def rsa_decrypt_cipher_text(b64encode_cypher_text: str, key_name=None):
    # if key_name == 'bito':
    #     decrypt_key = rsa_import_key_pem(settings.RSA_KEYS_DIR.path('bito_data_private_key.pem'))
    # else:
    #     decrypt_key = rsa_decrypt_key
    decrypt_key = rsa_decrypt_key
    try:
        cipher_text = b64decode(b64encode_cypher_text)
    except binasciiError:
        return ''
    else:
        cipher = PKCS1_v1_5.new(decrypt_key)
        try:
            message = cipher.decrypt(cipher_text, None)
        except ValueError:
            return ''
        else:
            return message.decode() if message else ''


def rsa_encrypt_cipher_text(text: str, key_name=None):
    # if key_name == 'card':
    #     encrypt_key = card_data_pub_key
    # elif key_name == 'bito':
    #     encrypt_key = rsa_import_key_pem(settings.RSA_KEYS_DIR.path('block_data_public_key.pem'))
    # else:
    #     encrypt_key = rsa_decrypt_key
    encrypt_key = rsa_decrypt_key
    cipher = PKCS1_v1_5.new(encrypt_key)
    cipher_text = cipher.encrypt(text.encode())
    return b64encode(cipher_text).decode()


def rsa_oaep_decrypt_cypher_text(b64encode_cypher_text: str):
    """
    Not used.
    """
    try:
        cipher_text = b64decode(b64encode_cypher_text)
    except binasciiError:
        return None
    else:
        cipher = PKCS1_OAEP.new(rsa_decrypt_key)
        try:
            message = cipher.decrypt(cipher_text)
        except (ValueError, TypeError):
            return None
        else:
            return message


# def data_key_encrypt(text):
#     if len(text) > 240:
#         return False
#     cipher = PKCS1_v1_5.new(data_key)
#     cipher_text = cipher.encrypt(text.encode())
#     return urlsafe_b64encode(cipher_text).decode()


def rsa_sign(key, message):
    msg_hash = SHA256.new(b64encode(message))
    signature = b64encode(pkcs1_15.new(key).sign(msg_hash))

    return signature.decode()


def get_sha_hash(message):
    shavalue = hashlib.sha256()
    shavalue.update(message.encode())
    return shavalue.hexdigest()


def get_md5_hash(message):
    md5value = hashlib.md5()
    md5value.update(message.encode())
    return md5value.hexdigest()


des_key = '1234567887654321'


def des_enc_data(context, iv='\x00'*8):
    des_func = triple_des(des_key, CBC, iv, padmode=PAD_PKCS5)
    enc_value = des_func.encrypt(data=context)
    return urlsafe_b64encode(enc_value)


def des_dec_data(enc_value, iv='\x00'*8):
    des_func = triple_des(des_key, CBC, iv, padmode=PAD_PKCS5)
    context = des_func.decrypt(data=urlsafe_b64decode(enc_value))
    return context


aes_key = settings.III_ENC_TOKEN_KEY.encode()


def aes_zero_pad(context):
    text_length = len(context)
    amount_to_pad = AES.block_size - (text_length % AES.block_size)
    if amount_to_pad == 0:
        amount_to_pad = AES.block_size
    # pad = chr(amount_to_pad)
    return (context + '0' * amount_to_pad).encode()


def aes_crypto_js_zero_padding(context):
    text_length = len(context)
    amount_to_pad = AES.block_size - (text_length % AES.block_size)
    return (context + '\x00' * amount_to_pad).encode()


def aes_unpad(context):
    pad = ord(context[-1])
    return context[:-pad]


def aes_enc_data(context, iv='\x00'*16):
    aes_func = AES.new(aes_key, AES.MODE_CBC, iv)
    return aes_func.encrypt(context)


def aes_dec_data(enc, iv='\x00'*16):
    # enc = base64.b64decode(enc)
    cipher = AES.new(aes_key, AES.MODE_CBC, iv)
    return cipher.decrypt(enc)


def hmac_256(data, key):
    return b64encode(hmac.new(key.encode('utf-8'), data, hashlib.sha256).digest())



