import secrets


def token_generator(token_num=None):
    if token_num:
        return secrets.token_hex(token_num)
    else:
        return secrets.token_hex(64)
