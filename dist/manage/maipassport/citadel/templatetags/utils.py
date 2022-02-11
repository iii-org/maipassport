import re

from django import template

register = template.Library()


@register.filter
def change_page(url, page_num):
    if 'page=' in url:
        return re.sub('page=\d+', f'page={page_num}', url)
    elif '?' in url:
        return f'{url}&page={page_num}'
    else:
        return f'{url}?page={page_num}'


@register.filter
def change_page2(url, page_num):
    if 'page2=' in url:
        return re.sub('page2=\d+', f'page2={page_num}', url)
    elif '?' in url:
        return f'{url}&page2={page_num}'
    else:
        return f'{url}?page2={page_num}'


@register.filter
def change_page3(url, page_num):
    if 'page=' in url:
        return re.sub('page3=\d+', f'page3={page_num}', url)
    elif '?' in url:
        return f'{url}&page3={page_num}'
    else:
        return f'{url}?page3={page_num}'


@register.filter
def get_page_pub_id(url, group_list):
    return_str = str()
    list_len = len(group_list)
    for i in range(list_len):
        return_str += str(group_list[i].pub_id)
        if i != list_len - 1:
            return_str += ','
    return return_str


@register.filter(is_safe=False)
def divisibleby_in1(value, arg):
    """Return True if the value is divisible by the argument."""
    return int(value) % int(arg) == 1
