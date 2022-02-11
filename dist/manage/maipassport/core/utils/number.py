from decimal import Decimal
import math


def decimal_to_string(decimal: Decimal, digits_num: int = 2) -> str:
    digits_place = -decimal.as_tuple().exponent
    if digits_place > digits_num:
        raise ValueError('The digits place of decimal could not be bigger than digits_num')
    else:
        return f'{decimal:.{digits_num}f}'


# 無條件進位
def carry_float_num(num, decimal_point):
    if type(num) != float:
        num = float(num)
    if decimal_point == 0:
        carry_num = math.ceil(num)
    else:
        decimal_point = int(math.pow(10, decimal_point))
        carry_num = math.ceil(num * decimal_point) / decimal_point
    return carry_num


# 無條件捨去
def chop_float_num(num, decimal_point):
    if type(num) != float:
        num = float(num)
    if decimal_point == 0:
        chop_num = math.floor(num)
    else:
        decimal_point = int(math.pow(10, decimal_point))
        chop_num = math.floor(num * decimal_point) / decimal_point
    return chop_num
