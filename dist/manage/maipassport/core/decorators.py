from threading import Thread
from functools import wraps

from django.urls import reverse, exceptions


def digital_signature_exempt(view_func):
    """Refer to django.views.decorators.csrf.csrf_exempt"""

    @wraps(view_func)
    def wrapped_view(*args, **kwargs):
        return view_func(*args, **kwargs)
    wrapped_view.digital_signature_exempt = True
    return wrapped_view


def django_admin_exempt(process_request):
    """
    For process_request method of middleware to exempt django_admin pages.
    """
    @wraps(process_request)
    def wrapped(middleware_instance, request):
        try:
            if request.path.startswith('/mainboard/'):
                return None
            elif request.path.startswith('/app/'):
                return None
            elif request.path.startswith('/passboard/'):
                return None
            elif request.path.startswith('/chat-test/'):
                return None
            elif request.path.startswith('/enc-test/'):
                return None
            elif request.path.startswith('/qr/trans/'):
                return None
            elif request.path.startswith('/line/'):
                return None
            elif request.path.startswith('/msg_api/'):
                return None
            elif request.path.startswith(reverse('admin:index')):
                return None
        except (KeyError, exceptions.NoReverseMatch):  # reverse() except when admin urls ware not loaded
            pass
        return process_request(middleware_instance, request)
    return wrapped


def postpone(func):
    """
    Refer to https://stackoverflow.com/questions/18420699/multithreading-for-python-django
    """
    def decorator(*args, **kwargs):
        t = Thread(target=func, args=args, kwargs=kwargs)
        t.daemon = True
        t.start()
    return decorator
